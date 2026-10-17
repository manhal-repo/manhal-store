#!/usr/bin/env python3
"""store_meta.py - يملأ الوصف والأيقونة لكل تطبيق في متجر manhal.

شغّله من جذر مستودع المتجر (~/projects/myrepo-store):
    python3 store_meta.py                 # يملأ الناقص فقط
    python3 store_meta.py --force-icons   # يستبدل الأيقونات الموجودة أيضاً
    python3 store_meta.py --seed-readme   # يضيف قسم "وصف التطبيق" إلى README المشاريع التي ينقصها
    python3 store_meta.py --verify        # يفحص الفهرس المنشور ويعرض التطبيقات بلا أيقونة/وصف
    python3 store_meta.py --dry-run       # يعرض ما سيفعله دون كتابة

من أين يأخذ الوصف (بالترتيب):
  1) قسم README الذي عنوانه  "## وصف التطبيق"  (أو "App description" / "Store description")
     - سطر "الملخص: ..."  (أو "Summary: ...") داخل القسم = الوصف القصير (حتى 80 حرفاً)
     - بقية القسم = الوصف الكامل.   إن لم يوجد سطر الملخص فأول فقرة هي الملخص.
  2) الوصف الموجود حالياً في المتجر (لا يُمحى)
  3) نص احتياطي مدمج لتطبيقاتك المعروفة
  4) أول فقرة في README، ثم اسم التطبيق

الأيقونة: من ملف APK نفسه (الحزمة والاسم والإصدار تُقرأ من الـAPK بـ aapt)، ثم من مصدر المشروع،
ثم أيقونة بديلة ملوّنة حتى لا تبقى فارغة.

المتطلبات في Termux:  pkg install aapt     (اختياري للتحويل: pkg install python-pillow)
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import urllib.request
import zipfile
import zlib

HEAD_RE = re.compile(
    r'^[ \t]{0,3}(#{1,6})[ \t]*(?:وصف[ \t]+التطبيق|وصف[ \t]+المتجر|app[ \t]+description|store[ \t]+description)'
    r'[ \t]*[:：]?[ \t]*#*[ \t]*$', re.I | re.M)
SUMMARY_RE = re.compile(r'^[ \t]*(?:الملخص|ملخص|summary)[ \t]*[:：][ \t]*(.+?)[ \t]*$', re.I | re.M)
LOCALES = ('ar', 'en-US')
README_NAMES = ('README.md', 'readme.md', 'README.MD', 'Readme.md')

# أسماء مجلدات المشاريع المعتمدة (تُفضَّل عند وجود أكثر من مجلد بنفس الحزمة)
PREFERRED = ['universalprint-full-project', 'universalprint', 'completeproject', 'android-app', 'aliaffiliateapp',
             'hikmah-kotlin', 'android-offers-app', 'mystore-complete', 'almanhal-cleaner', 'mediahubapp',
             'quranicparents', 'shwiya', 'mobilecodestudio', 'manhalstore', 'manhal-dev-android']

# نص احتياطي (يُستعمل فقط إذا لم يوجد README ولا وصف سابق)
SEED = {
    'com.devbelmel.universalprinter': ('Universal Printer',
        'اطبع من أندرويد إلى أي طابعة: شبكة أو USB أو بلوتوث أو حاسوب ويندوز',
        'خدمة طباعة لأندرويد تدعم بروتوكولات IPP وLPR وRAW وFTP وSMB، والاتصال عبر USB وبلوتوث وWi-Fi Direct، '
        'مع اكتشاف الطابعات تلقائياً في الشبكة وصفحة اختبار وسجل للطباعة.\n\n'
        'يمكن ربطه ببرنامج UniversalPrintServer على ويندوز لتحويل الحاسوب إلى خادم طباعة.'),
    'com.devbelmel.manhal_app': ('المنهل',
        'دليل توافق قطع غيار الهواتف مع متجر منتجات وسلة طلبات',
        'اختر نوع القطعة ثم الشركة ثم الموديل لتعرف الأجهزة المتوافقة معها.\n\n'
        'يتضمن متجراً لعرض المنتجات بالصور وإضافتها إلى السلة وإرسال الطلب، إضافة إلى أدوات وبرامج الصيانة.'),
    'com.prodm.app': ('Pro Download Manager',
        'متصفح ومدير تحميلات سريع يكتشف الفيديوهات ويحمّلها بأجزاء',
        'مدير تحميلات بمتصفح مدمج: يكتشف الفيديوهات والملفات في الصفحات ويحمّلها بتقنية التحميل المجزّأ '
        'لسرعة أعلى، مع صفحة بداية مصنّفة وإعدادات لمهلات الاتصال.'),
    'com.aliaffiliate.app': ('المنهال',
        'منتجات وكوبونات وعروض مع اختيار الدولة والعملة وتتبع المشتريات',
        'تصفح المنتجات والكوبونات والعروض مع تحويل الأسعار حسب الدولة والعملة، وتتبع المشتريات والمحفظة داخل التطبيق.'),
    'com.hikmah.app': ('كشف الشبهات',
        'قراءة القرآن والاستماع للقرّاء ومتابعة الحفظ مع اختبار تسميع',
        'قراءة القرآن والاستماع لعدد من القرّاء، ومتابعة تقدّم حفظ كل سورة بتقييم ذاتي، '
        'واختبار تسميع يستمع للمستخدم عبر الميكروفون.'),
    'com.devbelmel.offers_app': ('Operator Offers',
        'عروض متعاملي الاتصالات وأكواد USSD وتعبئة الأنترنت',
        'اختر المتعامل لتصفح عروضه وإرسال أكواد USSD وإلغاء الخدمات، مع سجل للطلبات وصفحة لتعبئة الأنترنت.'),
    'com.devbelmel.mystore': ('متجر المنهل',
        'متجر تطبيقات المنهل: تصفح وحمّل وثبّت تطبيقاتنا',
        'عميل أندرويد لمتجر المنهل: تصفح التطبيقات وحمّلها وثبّتها مباشرة من المستودع.'),
    'com.devbelmel.cleaner': ('Al-Manhal Cleaner',
        'تنظيف وتحليل التطبيقات ومراقبة البطارية مع حماية من الإعلانات',
        'أداة لتحليل التطبيقات المثبّتة وتنظيفها، وشاشة للبطارية، وخدمة حماية من الإعلانات المزعجة.'),
    'com.mediahub.app': ('ميديا المنهل',
        'صوتيات وفيديوهات وصور وكتب: أناشيد وقرآن وفتاوى ودروس',
        'مكتبة وسائط مصنّفة (أناشيد، قرآن، فتاوى، دروس) يمكن أن تحتوي كل بطاقة على عدة أجزاء، مع التقييم وتسجيل المشاهدات.'),
    'com.quranicschool.parents': ('أولياء الأمور - المدارس القرآنية',
        'تطبيق لأولياء أمور طلاب المدارس القرآنية لمتابعة أبنائهم',
        'تطبيق مخصص لأولياء أمور طلاب المدارس القرآنية لمتابعة أبنائهم.'),
    'com.devbelmel.shwiya_app': ('Shwiya',
        'تطبيق فيديوهات قصيرة: تصفح ورفع وتعليقات واستكشاف',
        'تطبيق فيديوهات قصيرة بتغذية عمودية مع رفع المقاطع والتعليقات وصفحة استكشاف.'),
    'com.devbelmel.manhaldev': ('المنهل للمطورين',
        'ارفع تطبيقاتك وأدرها في متجر المنهل',
        'تطبيق للمطورين: تسجيل الدخول واستعراض تطبيقاتك ورفع إصدارات جديدة إلى المتجر.'),
    'com.mobilecodestudio.app': ('Mobile Code Studio',
        'محرر أكواد للهاتف بمستكشف مجلدات ومشاريع أخيرة',
        'محرر أكواد لأندرويد: افتح مجلد المشروع وتصفح الملفات من المستكشف وعدّلها بتخطيط يتكيف مع الاتجاهين.'),
}

SKIP_DIRS = {'build', '.gradle', '.git', '.idea', 'node_modules', 'intermediates'}
warned = set()


def warn_once(key, msg):
    if key not in warned:
        warned.add(key)
        print('  !! ' + msg)


# ------------------------------------------------------------------ README
def read_readme(src):
    for n in README_NAMES:
        f = pathlib.Path(src) / n
        if f.is_file():
            return f, f.read_text(encoding='utf-8', errors='ignore')
    return None, ''


def md_to_text(t, max_chars=4000):
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    t = re.sub(r'```.*?```', '', t, flags=re.S)
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t)
    t = re.sub(r'<img[^>]*>', '', t, flags=re.I)
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'<[^>]+>', '', t)
    out = []
    for line in t.splitlines():
        l = line.rstrip()
        m = re.match(r'^\s{0,3}#{1,6}\s+(.*)$', l)
        if m:
            out += ['', m.group(1).strip().strip('#').strip()]
            continue
        l = re.sub(r'^\s*[-*+]\s+', '• ', l)
        out.append(l.replace('**', '').replace('__', '').replace('`', ''))
    text = re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        text = cut[:cut.rfind('\n\n')] if '\n\n' in cut else cut
    return text


def short_of(text, limit=80):
    first = re.split(r'\n\s*\n', text.strip())[0].replace('\n', ' ').strip()
    if len(first) <= limit:
        return first
    sent = re.split(r'(?<=[.!؟?])\s', first)[0]
    if 0 < len(sent) <= limit:
        return sent
    return first[:limit - 1].rstrip() + '…'


def readme_section(src):
    """(summary, full) من قسم 'وصف التطبيق' أو None."""
    _, txt = read_readme(src)
    m = HEAD_RE.search(txt) if txt else None
    if not m:
        return None
    level = len(m.group(1))
    rest = txt[m.end():]
    nxt = re.search(r'^[ \t]{0,3}#{1,%d}[ \t]+\S' % level, rest, re.M)
    body = rest[:nxt.start()] if nxt else rest
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S).strip()
    if not body:
        return None
    sm = SUMMARY_RE.search(body)
    summary = ''
    if sm:
        summary = sm.group(1).strip()[:80]
        body = (body[:sm.start()] + body[sm.end():]).strip()
    full = md_to_text(body)
    if not full and not summary:
        return None
    if not summary:
        summary = short_of(full)
    return summary, (full or summary)


def readme_lead(src):
    _, txt = read_readme(src)
    if not txt:
        return None
    t = md_to_text(re.sub(r'^\s*#\s+.*$', '', txt, count=1, flags=re.M))
    for p in re.split(r'\n\s*\n', t):
        p = p.replace('\n', ' ').strip()
        if len(p) > 15:
            return p
    return None


def seed_readme(src, summary, full):
    f, txt = read_readme(src)
    if txt and HEAD_RE.search(txt):
        return False
    block = '\n\n## وصف التطبيق\n\nالملخص: %s\n\n%s\n' % (summary, full)
    if f is None:
        f = pathlib.Path(src) / 'README.md'
        txt = '# %s\n' % pathlib.Path(src).name
    f.write_text(txt.rstrip() + block, encoding='utf-8')
    return True


# ------------------------------------------------------------------ APK
def find_aapt():
    for n in ('aapt', 'aapt2'):
        p = shutil.which(n)
        if p:
            return p
    return None


def badging(aapt, apk):
    r = subprocess.run([aapt, 'dump', 'badging', str(apk)], capture_output=True, text=True, errors='ignore')
    b = r.stdout
    m = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", b)
    if not m:
        return None
    def grab(rx):
        x = re.search(rx, b, re.M)
        return x.group(1) if x else ''
    icons = sorted(((int(d), p) for d, p in re.findall(r"application-icon-(\d+):'([^']+)'", b)), reverse=True)
    return {'pkg': m.group(1), 'code': int(m.group(2)), 'vname': m.group(3),
            'label': grab(r"^application-label:'([^']*)'"), 'label_ar': grab(r"^application-label-ar:'([^']*)'"),
            'icons': [p for _, p in icons]}


DENSITY = {'xxxhdpi': 6, 'xxhdpi': 5, 'xhdpi': 4, 'hdpi': 3, 'mdpi': 2, 'ldpi': 1}


def icon_from_apk(apk, info):
    """bytes, ext  أو  (None, None)"""
    try:
        z = zipfile.ZipFile(apk)
    except Exception:
        return None, None
    names = set(z.namelist())
    for p in info['icons']:                           # أكبر كثافة غير XML
        if not p.endswith('.xml') and p in names:
            return z.read(p), p.rsplit('.', 1)[-1].lower()
    best = None
    for n in names:                                   # بحث بالاسم (يعمل إن لم تُخفَ الأسماء)
        low = n.lower()
        if not low.startswith('res/') or not re.search(r'ic_launcher|icon', low):
            continue
        if re.search(r'foreground|background|monochrome|\.xml$', low) or not re.search(r'\.(png|webp)$', low):
            continue
        dens = max([v for k, v in DENSITY.items() if k in low] or [0])
        key = (dens, z.getinfo(n).file_size)
        if best is None or key > best[0]:
            best = (key, n)
    if best:
        return z.read(best[1]), best[1].rsplit('.', 1)[-1].lower()
    return None, None


def icon_from_source(src):
    best = None
    for p in pathlib.Path(src).rglob('ic_launcher*'):
        if not p.is_file() or SKIP_DIRS & set(p.parts) or p.suffix.lower() not in ('.png', '.webp'):
            continue
        n = p.name
        if re.search(r'foreground|background|monochrome', n):
            continue
        rank = 9 if 'playstore' in n else DENSITY.get(p.parent.name.split('-')[-1], 0)
        if 'round' in n:
            rank -= 0.5
        key = (rank, p.stat().st_size)
        if best is None or key > best[0]:
            best = (key, p)
    if best:
        return best[1].read_bytes(), best[1].suffix.lower().lstrip('.')
    for d in ('img', 'images', 'docs', 'assets'):
        for p in sorted((pathlib.Path(src) / d).glob('*')) if (pathlib.Path(src) / d).is_dir() else []:
            if p.suffix.lower() == '.png' and re.search(r'icon|logo', p.name, re.I):
                return p.read_bytes(), 'png'
    return None, None


def to_png(data, ext):
    if ext == 'png':
        return data
    try:
        from PIL import Image
        import io
        out = io.BytesIO()
        Image.open(io.BytesIO(data)).convert('RGBA').save(out, 'PNG')
        return out.getvalue()
    except Exception:
        pass
    dwebp = shutil.which('dwebp')
    if dwebp:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            a, b = os.path.join(td, 'a.webp'), os.path.join(td, 'b.png')
            open(a, 'wb').write(data)
            if subprocess.run([dwebp, a, '-o', b], capture_output=True).returncode == 0:
                return open(b, 'rb').read()
    warn_once('webp', 'أيقونة webp بلا تحويل: ثبّت  pkg install python-pillow  لنتيجة أفضل (استُعملت كما هي)')
    return data


def placeholder_png(seed, size=192):
    h = hashlib.sha256(seed.encode()).digest()
    r, g, b = 40 + h[0] % 140, 40 + h[1] % 140, 40 + h[2] % 140
    row = b'\x00' + bytes([r, g, b]) * size
    raw = row * size

    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


# ------------------------------------------------------------------ مشاريع المصدر
def project_ids(roots):
    """pkg -> [dirs]"""
    found = {}
    for root in roots:
        root = pathlib.Path(root).expanduser()
        if not root.is_dir():
            continue
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            ids = set()
            for g in list(d.rglob('build.gradle')) + list(d.rglob('build.gradle.kts')):
                if SKIP_DIRS & set(g.relative_to(d).parts):
                    continue
                try:
                    t = g.read_text(encoding='utf-8', errors='ignore')
                except OSError:
                    continue
                for m in re.finditer(r'applicationId\s*=?\s*["\']([A-Za-z0-9_.]+)["\']', t):
                    ids.add(m.group(1))
            for i in ids:
                found.setdefault(i, []).append(d)
    return found


def pick_dir(dirs):
    if not dirs:
        return None
    for want in PREFERRED:
        for d in dirs:
            if d.name == want:
                return d
    return dirs[0]


# ------------------------------------------------------------------ الكتابة
def write(path, text, dry):
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf-8')


def read_if(path):
    try:
        return pathlib.Path(path).read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def process(pkg, info, apk, srcdir, meta, args, aapt_info_ok=True):
    mdir = meta / pkg
    report = {'pkg': pkg}
    name_en = info['label'] if info else ''
    name_ar = info['label_ar'] if info else ''
    seed = SEED.get(pkg)

    # ---- الوصف
    sec = readme_section(srcdir) if srcdir else None
    if sec:
        summary, full = sec
        report['desc'] = 'README'
        overwrite = True
    else:
        overwrite = False
        old_short = read_if(mdir / 'ar' / 'short_description.txt') or read_if(mdir / 'en-US' / 'short_description.txt')
        old_full = read_if(mdir / 'ar' / 'full_description.txt') or read_if(mdir / 'en-US' / 'full_description.txt')
        if old_short and old_full and old_short != old_full:
            summary, full, report['desc'] = old_short, old_full, 'موجود'
        elif seed:
            summary, full, report['desc'] = seed[1], seed[2], 'احتياطي'
        else:
            lead = readme_lead(srcdir) if srcdir else None
            nm = name_ar or name_en or pkg.split('.')[-1]
            summary, full = short_of(lead or nm), lead or nm
            report['desc'] = 'README-أول فقرة' if lead else 'الاسم فقط'

    title_ar = read_if(mdir / 'ar' / 'title.txt') or name_ar or (seed[0] if seed else '') or name_en or pkg.split('.')[-1]
    title_en = read_if(mdir / 'en-US' / 'title.txt') or name_en or (seed[0] if seed else '') or title_ar
    report['name'] = title_ar

    for loc, title in (('ar', title_ar), ('en-US', title_en)):
        d = mdir / loc
        if not (d / 'title.txt').exists():
            write(d / 'title.txt', title, args.dry_run)
        for fn, txt in (('short_description.txt', summary), ('full_description.txt', full)):
            f = d / fn
            if overwrite or not read_if(f) or (args.force_text):
                write(f, txt, args.dry_run)
    ymlp = meta / (pkg + '.yml')
    if not ymlp.exists():
        body = '\n'.join(('  ' + l) if l.strip() else '' for l in full.splitlines())
        write(ymlp, 'Categories:\n  - Others\nLicense: Unknown\nName: %s\nSummary: %s\nDescription: |-\n%s\n'
              % (json.dumps(title_ar, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), body), args.dry_run)

    # ---- الأيقونة
    need = [loc for loc in LOCALES if args.force_icons or not (mdir / loc / 'icon.png').exists()]
    if need:
        data = ext = None
        src_kind = ''
        if apk and info:
            data, ext = icon_from_apk(apk, info)
            src_kind = 'APK'
        if not data and srcdir:
            data, ext = icon_from_source(srcdir)
            src_kind = 'المصدر'
        if data:
            png = to_png(data, ext)
        else:
            png, src_kind = placeholder_png(pkg), 'بديلة (أيقونتها XML فقط، ضع PNG في icons/%s.png)' % pkg
        custom = pathlib.Path('icons') / (pkg + '.png')
        if custom.is_file():
            png, src_kind = custom.read_bytes(), 'icons/'
        report['icon'] = src_kind
        if not args.dry_run:
            for loc in need:
                p = mdir / loc / 'icon.png'
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(png)
    else:
        report['icon'] = 'موجودة'

    # ---- تهيئة README
    if args.seed_readme and srcdir and not sec:
        if args.dry_run:
            report['seed'] = 'سيُضاف (%s)' % srcdir
        else:
            report['seed'] = ('أُضيف إلى ' + str(srcdir)) if seed_readme(srcdir, summary, full) else ''
    return report


def verify(url):
    print('جلب', url)
    data = json.load(urllib.request.urlopen(url, timeout=30))
    base = url.rsplit('/', 1)[0]
    bad = 0
    for a in data.get('apps', []):
        loc = a.get('localized', {}) or {}
        l = loc.get('ar') or loc.get('en-US') or next(iter(loc.values()), {}) or {}
        has_icon = bool(a.get('icon') or l.get('icon'))
        has_desc = bool(l.get('description') or a.get('description') or l.get('summary') or a.get('summary'))
        flag = ''.join(['' if has_icon else ' [بلا أيقونة]', '' if has_desc else ' [بلا وصف]'])
        if flag:
            bad += 1
        print(('  ✗ ' if flag else '  ✓ ') + a['packageName'] + flag)
    print('المشاكل:', bad, 'من', len(data.get('apps', [])))


def git_remote_pages():
    try:
        u = subprocess.run(['git', 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
        m = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', u)
        if m:
            return 'https://%s.github.io/%s/repo/index-v1.json' % (m.group(1), m.group(2))
    except Exception:
        pass
    return ''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', help='مجلد الفهرس داخل المتجر (الافتراضي: manhal أو fdroid)')
    ap.add_argument('--src', action='append', help='مجلد يحوي مشاريعك (كرّره). الافتراضي: ~/storage/downloads و~/projects/apps')
    ap.add_argument('--force-icons', action='store_true')
    ap.add_argument('--force-text', action='store_true', help='يستبدل الوصف حتى لو لم يوجد قسم README')
    ap.add_argument('--seed-readme', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--verify', nargs='?', const='auto', help='يفحص index-v1.json المنشور (يُستنتج الرابط من git إن لم يُعطَ)')
    args = ap.parse_args()

    if args.verify:
        url = git_remote_pages() if args.verify == 'auto' else args.verify
        if not url:
            sys.exit('أعطني الرابط:  --verify https://USER.github.io/REPO/repo/index-v1.json')
        return verify(url)

    sub = args.dir or next((d for d in ('manhal', 'fdroid') if pathlib.Path(d, 'repo').is_dir()), None)
    if not sub:
        sys.exit('لم أجد manhal/repo ولا fdroid/repo هنا. شغّل السكربت من جذر مستودع المتجر.')
    repo, meta = pathlib.Path(sub) / 'repo', pathlib.Path(sub) / 'metadata'
    aapt = find_aapt()
    if not aapt:
        sys.exit('aapt غير مثبّت.  ثبّته بـ:  pkg install aapt')

    best = {}                                         # pkg -> (code, apk, info)
    for apk in sorted(repo.glob('*.apk')):
        info = badging(aapt, apk)
        if not info:
            print('  ?? لم أستطع قراءة', apk.name)
            continue
        if info['pkg'] not in best or info['code'] > best[info['pkg']][0]:
            best[info['pkg']] = (info['code'], apk, info)
    roots = args.src or ['~/storage/downloads', '~/projects/apps']
    pids = project_ids(roots)
    print('تطبيقات في المتجر: %d | مشاريع مصدر معروفة: %d' % (len(best), len(pids)))
    rows = []
    for pkg, (code, apk, info) in sorted(best.items()):
        d = pick_dir(pids.get(pkg, []))
        if len(pids.get(pkg, [])) > 1:
            print('  (%s: عدة مجلدات %s، اخترت %s)' % (pkg, [x.name for x in pids[pkg]], d.name))
        rows.append(process(pkg, info, apk, d, meta, args))
    print()
    for r in rows:
        print('✓ %-34s %-28s وصف: %-14s أيقونة: %s%s' % (r['pkg'], r['name'][:28], r['desc'], r['icon'],
                                                          ('  README: ' + r['seed']) if r.get('seed') else ''))
    if args.dry_run:
        print('\n(تشغيل تجريبي: لم يُكتب شيء)')
    else:
        print('\nتم. الآن:  git add -A && git commit -m "store metadata" && git pull --rebase && git push')


if __name__ == '__main__':
    main()
