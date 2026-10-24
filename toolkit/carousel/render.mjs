// Renders one carousel from Chris's own text: one slide per paragraph (blank line between), his words and
// line breaks untouched. 1080x1350 PNGs in Gloock, checked for the TikTok/IG/Gist safe zone, contrast and font.
// Usage: node carousel/render.mjs <text file> <out folder> [family]
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FAMILIES = { smoke: '#36383F', dawn: '#58351F', rose: '#582035', iron: '#573029', sea: '#103C48', savanna: '#334027', music: '#563066', amber: '#5B4B13' }
const CREAM = '#EEE3CD'
const W = 1080, H = 1350
// Safe zone for a 4:5 slide that also shows in TikTok photo mode and Gist: words stay inside this box.
const SAFE = { left: 120, right: W - 120, top: 150, bottom: H - 250 }

const [textFile, outDir, family = 'smoke'] = process.argv.slice(2)
if (!textFile || !outDir) { console.error('usage: node carousel/render.mjs <text file> <out folder> [family]'); process.exit(2) }
const bg = FAMILIES[family]
if (!bg) { console.error(`unknown family ${family}; one of ${Object.keys(FAMILIES).join(', ')}`); process.exit(2) }
const slides = fs.readFileSync(textFile, 'utf8').replace(/\r/g, '').split(/\n\s*\n/).map(s => s.trim()).filter(Boolean)
if (slides.length === 0) { console.error('no text in the file'); process.exit(2) }

function lum(hex) {
  const c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255).map(v => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05) }

const font = fs.readFileSync(path.join(HERE, '..', 'fonts', 'Gloock-Regular.ttf')).toString('base64')
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const page = (text, n, total) => `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: Gloock; src: url(data:font/ttf;base64,${font}) format('truetype'); }
html, body { margin: 0; width: ${W}px; height: ${H}px; background: ${bg}; }
body { background: radial-gradient(ellipse at 50% 42%, ${bg}00 0%, #00000055 100%), ${bg}; display: flex; align-items: center; justify-content: center; }
#words { font-family: Gloock, serif; color: ${CREAM}; text-align: center; white-space: pre; line-height: 1.18; }
#mark { position: absolute; bottom: ${H - SAFE.bottom}px; left: ${SAFE.left}px; right: ${W - SAFE.right}px; text-align: center; font-family: Gloock, serif; color: ${CREAM}; opacity: .7; letter-spacing: .32em; font-size: 26px; }
#count { position: absolute; top: ${SAFE.top}px; right: ${W - SAFE.right}px; font-family: Gloock, serif; color: ${CREAM}; opacity: .55; font-size: 24px; }
</style></head><body><div id="words">${esc(text)}</div>${n === total ? '<div id="mark">LABEAU</div>' : ''}<div id="count">${n}/${total}</div></body></html>`

fs.mkdirSync(outDir, { recursive: true })
const browser = await puppeteer.launch({ headless: true, args: process.getuid?.() === 0 ? ['--no-sandbox'] : [] })
const problems = []
try {
  const tab = await browser.newPage()
  await tab.setViewport({ width: W, height: H, deviceScaleFactor: 1 })
  // Pass 1: the largest size each slide's words fit inside the safe zone without a line break he did not write.
  // Pass 2: every slide at the smallest of those, so the type size holds steady across the swipe.
  const measure = async (i, px) => {
    await tab.setContent(page(slides[i], i + 1, slides.length), { waitUntil: 'load' })
    await tab.evaluate(() => document.fonts.ready)
    return tab.evaluate((safe, start) => {
      const el = document.getElementById('words')
      let px = start
      for (; px >= 40; px -= 2) {
        el.style.fontSize = px + 'px'
        const r = el.getBoundingClientRect()
        if (r.left >= safe.left && r.right <= safe.right && r.top >= safe.top + 50 && r.bottom <= safe.bottom - 60) break
      }
      const boxes = [...document.querySelectorAll('#words, #mark, #count')].map(e => e.getBoundingClientRect())
      return { px, inside: boxes.every(b => b.left >= safe.left && b.right <= safe.right && b.top >= safe.top && b.bottom <= safe.bottom),
        gloock: document.fonts.check(`${px}px Gloock`), family: getComputedStyle(el).fontFamily, text: el.innerText }
    }, SAFE, px)
  }
  let size = 112
  for (let i = 0; i < slides.length; i++) size = Math.min(size, (await measure(i, 112)).px)
  for (let i = 0; i < slides.length; i++) {
    const fit = await measure(i, size)
    const file = path.join(outDir, `slide-${i + 1}.png`)
    await tab.screenshot({ path: file, type: 'png' })
    const verbatim = fit.text.replace(/\s+/g, ' ').trim() === slides[i].replace(/\s+/g, ' ').trim()
    const ok = fit.inside && fit.gloock && !/italiana/i.test(fit.family) && verbatim && fit.px === size
    if (!ok) problems.push(`slide ${i + 1}: inside=${fit.inside} gloock=${fit.gloock} family=${fit.family} verbatim=${verbatim}`)
    console.log(`slide ${i + 1}: ${fit.px}px Gloock, safe zone ${fit.inside ? 'ok' : 'FAIL'}, words verbatim ${verbatim ? 'ok' : 'FAIL'} -> ${file}`)
  }
} finally {
  await browser.close()
}
const ratio = contrast(CREAM, FAMILIES[family])
if (ratio < 4.5) problems.push(`contrast ${ratio.toFixed(2)}:1 is under 4.5:1`)
console.log(`contrast cream on ${family}: ${ratio.toFixed(2)}:1`)
if (problems.length) { console.error('FAIL\n' + problems.join('\n')); process.exit(1) }
console.log(`PASS ${slides.length} slides`)
