import { useEffect, useMemo, useState } from 'react'
import { Banner, Interstitial } from './Ads.jsx'

const STORE_NAME = 'متجر المنهل'
const REPO_URL = new URL('repo', window.location.href.split('#')[0]).href

const OSES = [
  ['all', 'الكل'], ['android', 'Android'], ['windows', 'Windows'],
  ['linux', 'Linux'], ['macos', 'macOS'], ['ios', 'iOS'],
]
const OS_LABEL = { android: 'Android', windows: 'Windows', linux: 'Linux', macos: 'macOS', ios: 'iOS' }
const fmtSize = (b) => (b ? (b / 1048576).toFixed(1) + ' MB' : '')

function detectOS() {
  const u = navigator.userAgent
  if (/android/i.test(u)) return 'android'
  if (/iphone|ipad|ipod/i.test(u)) return 'ios'
  if (/windows/i.test(u)) return 'windows'
  if (/mac/i.test(u)) return 'macos'
  if (/linux|x11/i.test(u)) return 'linux'
  return 'all'
}

// يدمج تطبيقات أندرويد (فهرس F-Droid) مع تطبيقات باقي الأنظمة (catalog/apps.json)
async function loadAll() {
  const j = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(r.status); return r.json() })
  const [fd, cat] = await Promise.allSettled([j('repo/index-v1.json'), j('catalog/apps.json')])
  if (fd.status === 'rejected' && cat.status === 'rejected') throw new Error('load')
  const map = new Map()
  const get = (id, base) => {
    if (!map.has(id)) map.set(id, { id, downloads: [], ...base })
    return map.get(id)
  }
  if (fd.status === 'fulfilled') {
    const data = fd.value
    for (const a of data.apps) {
      const vs = (data.packages[a.packageName] || []).slice().sort((x, y) => y.versionCode - x.versionCode)
      const v = vs.find((x) => x.versionCode === a.suggestedVersionCode) || vs[0]
      if (!v) continue
      const loc = a.localized?.ar || a.localized?.['en-US'] || {}
      const item = get(a.packageName, {
        name: loc.name || a.name, summary: loc.summary || a.summary,
        desc: loc.description || a.description, icon: a.icon ? `repo/icons/${a.icon}` : null,
      })
      item.downloads.push({ os: 'android', version: v.versionName, size: v.size, url: `repo/${v.apkName}` })
    }
  }
  if (cat.status === 'fulfilled') {
    for (const a of cat.value.apps || []) {
      const item = get(a.id, { name: a.name || a.id, summary: a.summary, desc: a.description, icon: a.icon || null })
      if (!item.icon && a.icon) item.icon = a.icon
      for (const d of a.downloads || []) {
        item.downloads = item.downloads.filter((x) => x.os !== d.os)
        item.downloads.push(d)
      }
    }
  }
  return [...map.values()]
}

function AppCard({ item, os, onDownload }) {
  const [open, setOpen] = useState(false)
  const dls = os === 'all' ? item.downloads : item.downloads.filter((d) => d.os === os)
  return (
    <div className="card">
      <div className="row">
        {item.icon && <img src={item.icon} alt="" onError={(e) => (e.target.style.display = 'none')} />}
        <div className="grow">
          <h3>{item.name}</h3>
          <p className="muted">{item.summary}</p>
          <small>{[...new Set(item.downloads.map((d) => OS_LABEL[d.os] || d.os))].join(' · ')}</small>
        </div>
      </div>
      {open && item.desc && <p className="desc" dangerouslySetInnerHTML={{ __html: item.desc }} />}
      <div className="actions">
        {dls.map((d) => (
          <button key={d.os + (d.arch || '')} className="btn" onClick={() => onDownload(d.url, item.name)}>
            {OS_LABEL[d.os] || d.os} {d.version} {fmtSize(d.size) && `· ${fmtSize(d.size)}`}
          </button>
        ))}
        {item.desc && <button className="btn ghost" onClick={() => setOpen(!open)}>{open ? 'إخفاء' : 'التفاصيل'}</button>}
      </div>
    </div>
  )
}

export default function App() {
  const [items, setItems] = useState(null)
  const [err, setErr] = useState(null)
  const [q, setQ] = useState('')
  const [os, setOs] = useState(detectOS())
  const [openAd, setOpenAd] = useState(true)
  const [dl, setDl] = useState(null)

  const startDownload = () => {
    const a = document.createElement('a')
    a.href = dl.url; a.download = ''
    document.body.appendChild(a); a.click(); a.remove()
    setDl(null)
  }

  useEffect(() => {
    document.title = 'متجر المنهل | Manhal Store'
    const l = document.querySelector("link[rel='icon']") || document.head.appendChild(Object.assign(document.createElement('link'), { rel: 'icon' }))
    l.type = 'image/svg+xml'; l.href = 'favicon.svg'
  }, [])

  useEffect(() => {
    loadAll().then(setItems).catch(() => setErr('تعذّر تحميل فهرس التطبيقات'))
  }, [])

  const list = useMemo(() => {
    if (!items) return []
    return items
      .filter((i) => os === 'all' || i.downloads.some((d) => d.os === os))
      .filter((i) => ((i.name || '') + ' ' + (i.summary || '')).toLowerCase().includes(q.toLowerCase()))
  }, [items, os, q])

  return (
    <div className="wrap">
      <header>
        <h1>{STORE_NAME}</h1>
        <p className="muted">Manhal Store · تطبيقات لعدة أنظمة تشغيل. اختر نظامك لعرض ما يناسبه.</p>
      </header>

      <section className="card repo">
        <b>مستودع أندرويد (F-Droid / NetHunter Store)</b>
        <code dir="ltr">{REPO_URL}</code>
        <div className="actions">
          <button className="btn" onClick={() => navigator.clipboard.writeText(REPO_URL)}>نسخ الرابط</button>
          <a className="btn ghost" href={`fdroidrepo://${REPO_URL.replace(/^https?:\/\//, '')}`}>فتح في F-Droid</a>
        </div>
      </section>

      <div className="chips">
        {OSES.map(([id, label]) => (
          <button key={id} className={'chip' + (os === id ? ' on' : '')} onClick={() => setOs(id)}>{label}</button>
        ))}
      </div>
      <input className="search" placeholder="ابحث عن تطبيق…" value={q} onChange={(e) => setQ(e.target.value)} />

      {err && <p className="err">{err}</p>}
      {!items && !err && <p className="muted">جارٍ التحميل…</p>}
      <div className="grid">
        {list.map((i) => <AppCard key={i.id} item={i} os={os} onDownload={(url, name) => setDl({ url, name })} />)}
      </div>
      {items && list.length === 0 && <p className="muted">لا توجد تطبيقات لهذا النظام.</p>}

      <Banner />
      {openAd && <Interstitial title={STORE_NAME} onDone={() => setOpenAd(false)} />}
      {dl && !openAd && <Interstitial title={`تنزيل ${dl.name}`} onDone={startDownload} onCancel={() => setDl(null)} />}
    </div>
  )
}
