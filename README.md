# متجر تطبيقاتي (F-Droid + React)

مستودع F-Droid + موقع React على GitHub Pages، يعمل مع F-Droid و NetHunter Store.

## 1) إنشاء مفتاح التوقيع (مرة واحدة، على جهازك)
```bash
keytool -genkey -v -keystore keystore.jks -alias myrepo \
  -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 keystore.jks > keystore.b64   # على macOS: base64 -i keystore.jks
```
⚠️ احتفظ بنسخة احتياطية من `keystore.jks` خارج GitHub. فقدانه = لا يمكن تحديث التطبيقات.

## 2) رفع المشروع إلى GitHub
```bash
git init && git add . && git commit -m "init"
git branch -M main
git remote add origin https://github.com/USERNAME/REPO.git
git push -u origin main
```

## 3) الأسرار (Settings ← Secrets and variables ← Actions)
- `KEYSTORE_B64`: محتوى ملف keystore.b64
- `KEYSTORE_PASS`: كلمة مرور المفتاح
- `KEY_ALIAS`: `myrepo`

## 4) تفعيل Pages
Settings ← Pages ← Source: **GitHub Actions**.

## 5) إضافة تطبيق
1. ضع ملف `app.apk` داخل `manhal/repo/` (اسم الملف: `package_versionCode.apk` أفضل).
2. اختياري محليًا: `cd manhal && fdroid update -c` لإنشاء `metadata/<package>.yml` ثم عدّل الاسم/الوصف/الأيقونة.
3. `git add . && git commit -m "add app" && git push`
4. بعد دقائق يصبح الموقع على `https://USERNAME.github.io/REPO/` والمستودع على `.../REPO/repo`.

## 6) الإضافة في التطبيقات
F-Droid / NetHunter Store: الإعدادات ← المستودعات ← + ← الصق رابط `.../repo`.

## تطوير محلي
```bash
npm install && npm run dev
```
(للمعاينة المحلية انسخ `manhal/repo` إلى `public/repo`.)

## ملاحظات
- لا ترفع `config.yml` ولا `keystore.jks` (موجودان في `.gitignore`).
- حد ملفات GitHub: 100MB لكل ملف. للـ APK الكبيرة استخدم Git LFS أو Releases.
- يجب أن تكون ملفات APK موقّعة.

## الإعلانات
- عدّل `src/ads.config.js` (معرّف الناشر ووحدات الإعلان) وبدّل نفس المعرّف في `index.html`.
- اجعل `testMode: false` قبل النشر.
- بانر ثابت أسفل الصفحة + إعلان منبثق عند فتح الموقع وعند كل طلب تنزيل.
- لا يبدأ التنزيل إلا بعد: تحميل الإعلان ← ظهوره فعليًا ← انتهاء العدّاد ← ضغط "متابعة".
- إذا فشل الإعلان (مثلًا مانع إعلانات) لا يُنفَّذ التنزيل.
- لا تشجّع المستخدمين على النقر على الإعلانات (يخالف سياسة AdSense).
