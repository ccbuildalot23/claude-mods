import React, { useEffect, useState } from 'react'
import { AbsoluteFill, continueRender, delayRender, interpolate, staticFile, useCurrentFrame } from 'remotion'

// His words only, passed in as props (one string per row, his breaks). Hook-first: every row is on screen at
// full strength in frame 1, inside the TikTok/IG/Gist safe zone (top 270, bottom 672, sides 120 of 1080x1920).
// The figure is a solid shape with a light behind it: no face, no features, ever.
export const silhouetteDefaults = {
  rows: ['Let someone into', 'all that darkness', '', 'They’re bound to bring', 'in a little light'],
  bg: '#36383F',
  ink: '#EEE3CD',
  glow: '#F2C98A',
}
type Props = typeof silhouetteDefaults

const font = new FontFace('Gloock', `url(${staticFile('Gloock-Regular.ttf')}) format('truetype')`)

const MAX_PX = 74
const WIDTH = 840 // 1080 minus the 120 px sides of the safe zone

// The largest size up to 74 px at which his longest row fits the safe width on one line (his breaks, never ours).
function fitSize(rows: string[]): number {
  const ctx = document.createElement('canvas').getContext('2d')
  if (!ctx) return MAX_PX
  ctx.font = `${MAX_PX}px Gloock`
  const widest = Math.max(1, ...rows.map(r => ctx.measureText(r).width))
  return Math.min(MAX_PX, Math.floor((MAX_PX * WIDTH) / widest))
}

export const Silhouette: React.FC<Props> = ({ rows, bg, ink, glow }) => {
  const [handle] = useState(() => delayRender('Gloock'))
  const [px, setPx] = useState(MAX_PX)
  useEffect(() => {
    font.load().then(f => { document.fonts.add(f); setPx(fitSize(rows)); continueRender(handle) })
  }, [handle, rows])
  const frame = useCurrentFrame()
  const push = interpolate(frame, [0, 450], [1, 1.06])
  const light = interpolate(frame, [0, 36, 450], [0.35, 0.8, 1], { extrapolateRight: 'clamp' })
  const end = interpolate(frame, [360, 390], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill style={{ backgroundColor: bg, overflow: 'hidden' }}>
      <AbsoluteFill style={{ transform: `scale(${push})`, transformOrigin: '50% 75%' }}>
        <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 66%, ${glow} 0%, ${glow}55 18%, ${bg}00 46%)`, opacity: light }} />
        <svg viewBox="0 0 1080 1920" style={{ position: 'absolute', inset: 0 }}>
          <path
            fill="#0d0d10"
            d="M540 1010c-92 0-160 78-160 178 0 70 30 128 76 160-40 14-74 30-104 52-110 32-212 92-262 170-26 40-40 120-40 350h980c0-230-14-310-40-350-50-78-152-138-262-170-30-22-64-38-104-52 46-32 76-90 76-160 0-100-68-178-160-178z"
          />
        </svg>
      </AbsoluteFill>
      <div style={{ position: 'absolute', top: 330, bottom: 760, left: 120, right: 120, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-start', opacity: 1 - end }}>
        {rows.map((r, i) => (
          <div key={i} style={{ fontFamily: 'Gloock', fontSize: px, lineHeight: 1.2, color: ink, height: r === '' ? px * 0.6 : undefined, whiteSpace: 'pre', textAlign: 'center' }}>{r}</div>
        ))}
      </div>
      <div style={{ position: 'absolute', top: 330, left: 120, right: 120, height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: end }}>
        <div style={{ fontFamily: 'Gloock', fontSize: 64, letterSpacing: '0.32em', color: ink }}>LABEAU</div>
      </div>
    </AbsoluteFill>
  )
}
