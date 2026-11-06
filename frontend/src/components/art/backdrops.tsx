/**
 * LearnHub page artwork. Every page gets its own backdrop instead of a flat colour:
 * generated SVG drawn from the theme tokens, so it follows light / dark mode, stays
 * sharp at any size and costs a few KB. The shapes are seeded, so the same page
 * always gets the same picture (no layout shift, no flicker).
 *
 *   constellation  home: a network of learning paths
 *   mosaic         course catalogue: floating course tiles
 *   waves          course page: layered waves in the course's category colours
 *   path           my learning: a winding journey with milestones
 *   contours       business: topographic map ("where your teams stand")
 *   blueprint      instructor studio and the design page: drafting grid
 *   circuit        admin console: circuit traces
 *   aurora         sign-in pages: soft light behind floating shapes
 *   orbit          empty / not-found states
 *   ribbons        plans and subscriptions: flowing ribbons
 *   confetti       order complete: a burst of brand-coloured confetti
 *   notebook       lessons in the player: a ruled page with margin and pencil marks
 *   guilloche      certificates and verification: security-print rosettes
 *   honeycomb      achievements: a wall of badges, some earned
 *   checklist      required training: rows ticked off on a clipboard grid
 *   signal         notifications: rings spreading from a bell
 *   dials          settings: control dials with tick marks
 *   bubbles        help and support: a conversation drifting upwards
 */
import { memo, useId, type ReactNode } from 'react'

import { cn } from '@/lib/cn'

export type BackdropVariant = 'constellation' | 'mosaic' | 'waves' | 'path' | 'contours' | 'blueprint' | 'circuit' | 'aurora' | 'orbit' | 'ribbons' | 'confetti' | 'notebook' | 'guilloche' | 'honeycomb' | 'checklist' | 'signal' | 'dials' | 'bubbles'

// small seeded PRNG (mulberry32): same seed, same art
function rng(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const W = 1600
const H = 640

function Svg({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" className={cn('absolute inset-0 size-full', className)} aria-hidden focusable="false">
      {children}
    </svg>
  )
}

function Glow({ id, cx, cy, r, color, opacity }: { id: string; cx: number; cy: number; r: number; color: string; opacity: number }) {
  return (
    <>
      <defs>
        <radialGradient id={id}>
          <stop offset="0" stopColor={color} stopOpacity={opacity} />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx={cx} cy={cy} r={r} fill={`url(#${id})`} />
    </>
  )
}

const Constellation = memo(function Constellation() {
  const id = useId()
  const r = rng(7)
  const nodes = Array.from({ length: 46 }, () => ({ x: 720 + r() * 860, y: 30 + r() * 580, s: r() }))
  const edges: [number, number][] = []
  nodes.forEach((a, i) =>
    nodes.forEach((b, j) => {
      if (j > i && Math.hypot(a.x - b.x, a.y - b.y) < 150) edges.push([i, j])
    }),
  )
  return (
    <Svg>
      <Glow id={`${id}g1`} cx={1180} cy={180} r={520} color="var(--primary)" opacity={0.22} />
      <Glow id={`${id}g2`} cx={260} cy={-40} r={420} color="var(--chart-5)" opacity={0.1} />
      <g fill="none" stroke="var(--primary)" strokeOpacity="0.16">
        <ellipse cx="1180" cy="300" rx="430" ry="170" transform="rotate(-14 1180 300)" />
        <ellipse cx="1180" cy="300" rx="300" ry="110" transform="rotate(-14 1180 300)" strokeDasharray="2 8" />
      </g>
      <g stroke="var(--primary)" strokeOpacity="0.22" strokeWidth="1">
        {edges.map(([i, j]) => (
          <line key={`${i}-${j}`} x1={nodes[i]!.x} y1={nodes[i]!.y} x2={nodes[j]!.x} y2={nodes[j]!.y} />
        ))}
      </g>
      {nodes.map((n, i) => (
        <circle key={i} cx={n.x} cy={n.y} r={n.s > 0.86 ? 5 : 2.2 + n.s * 1.6} fill={n.s > 0.86 ? 'var(--primary)' : 'var(--primary-soft-text)'} fillOpacity={n.s > 0.86 ? 0.8 : 0.35} />
      ))}
      {nodes
        .filter((n) => n.s > 0.86)
        .map((n, i) => (
          <circle key={`h${i}`} cx={n.x} cy={n.y} r={12} fill="none" stroke="var(--primary)" strokeOpacity="0.25" />
        ))}
    </Svg>
  )
})

const Mosaic = memo(function Mosaic({ seed = 21 }: { seed?: number }) {
  const id = useId()
  const r = rng(seed)
  const colors = ['var(--primary)', 'var(--chart-5)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)']
  const tiles = Array.from({ length: 34 }, () => ({ x: r() * W, y: r() * H, s: 34 + r() * 70, rot: -18 + r() * 36, c: colors[Math.floor(r() * colors.length)]!, o: 0.05 + r() * 0.1, outline: r() > 0.6 }))
  return (
    <Svg>
      <Glow id={`${id}g`} cx={W * 0.75} cy={60} r={560} color="var(--primary)" opacity={0.16} />
      {tiles.map((t, i) => (
        <rect key={i} x={t.x} y={t.y} width={t.s * 1.5} height={t.s} rx={t.s * 0.18} transform={`rotate(${t.rot} ${t.x} ${t.y})`} fill={t.outline ? 'none' : t.c} fillOpacity={t.o} stroke={t.outline ? t.c : 'none'} strokeOpacity={0.25} />
      ))}
    </Svg>
  )
})

const Waves = memo(function Waves({ from = 'var(--primary)', to = 'var(--chart-5)' }: { from?: string; to?: string }) {
  const id = useId()
  const layers = [0, 1, 2, 3].map((i) => {
    const y = 330 + i * 70
    const a = 70 - i * 10
    return `M0 ${y} C ${300} ${y - a}, ${520} ${y + a}, ${800} ${y} S ${1300} ${y - a * 1.2}, ${W} ${y + a * 0.4} V ${H} H 0 Z`
  })
  return (
    <Svg>
      <defs>
        <linearGradient id={`${id}w`} x1="0" x2="1">
          <stop offset="0" stopColor={from} />
          <stop offset="1" stopColor={to} />
        </linearGradient>
        <pattern id={`${id}d`} width="22" height="22" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1.2" fill={from} fillOpacity="0.22" />
        </pattern>
      </defs>
      <Glow id={`${id}g`} cx={260} cy={40} r={460} color={from} opacity={0.2} />
      <Glow id={`${id}g2`} cx={1380} cy={120} r={420} color={to} opacity={0.14} />
      <rect x="900" y="0" width="700" height="300" fill={`url(#${id}d)`} />
      {layers.map((d, i) => (
        <path key={i} d={d} fill={`url(#${id}w)`} fillOpacity={0.06 + i * 0.025} />
      ))}
      <path d={layers[0]!.split(' V')[0]} fill="none" stroke={`url(#${id}w)`} strokeOpacity="0.45" strokeWidth="1.5" />
    </Svg>
  )
})

const Path = memo(function Path() {
  const id = useId()
  const d = 'M -40 470 C 180 380, 260 560, 470 470 S 760 260, 960 330 S 1260 520, 1420 300 S 1600 140, 1680 180'
  const stones = [
    [470, 470],
    [960, 330],
    [1420, 300],
  ]
  const r = rng(5)
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1250} cy={120} r={480} color="var(--primary)" opacity={0.18} />
      <Glow id={`${id}g2`} cx={180} cy={520} r={360} color="var(--chart-2)" opacity={0.1} />
      <path d={d} fill="none" stroke="var(--primary)" strokeOpacity="0.12" strokeWidth="26" strokeLinecap="round" />
      <path d={d} fill="none" stroke="var(--primary)" strokeOpacity="0.45" strokeWidth="2" strokeDasharray="2 12" strokeLinecap="round" />
      {stones.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="22" fill="var(--surface)" stroke="var(--primary)" strokeOpacity="0.5" strokeWidth="2" />
          <path d={`M ${x! - 8} ${y} l 6 6 l 11 -12`} fill="none" stroke={i < 2 ? 'var(--success)' : 'var(--text-subtle)'} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      ))}
      {Array.from({ length: 26 }, (_, i) => {
        const x = r() * W
        const y = r() * 260
        const s = 2 + r() * 4
        return <path key={i} d={`M ${x} ${y - s} L ${x + s * 0.3} ${y} L ${x} ${y + s} L ${x - s * 0.3} ${y} Z`} fill="var(--chart-3)" fillOpacity={0.25 + r() * 0.3} />
      })}
    </Svg>
  )
})

const Contours = memo(function Contours() {
  const id = useId()
  const rings = (cx: number, cy: number, n: number, seed: number) => {
    const r = rng(seed)
    const k1 = 2 + Math.floor(r() * 3)
    const k2 = 3 + Math.floor(r() * 3)
    return Array.from({ length: n }, (_, i) => {
      const base = 40 + i * 34
      const pts = Array.from({ length: 73 }, (_, j) => {
        const t = (j / 72) * Math.PI * 2
        const rad = base + Math.sin(k1 * t + i * 0.35) * (8 + i * 1.6) + Math.cos(k2 * t + seed) * (5 + i)
        return `${(cx + Math.cos(t) * rad * 1.35).toFixed(1)},${(cy + Math.sin(t) * rad).toFixed(1)}`
      })
      return `M${pts.join('L')}Z`
    })
  }
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1300} cy={40} r={520} color="var(--primary)" opacity={0.2} />
      <g fill="none" stroke="var(--primary)" strokeWidth="1">
        {rings(1320, 120, 14, 3).map((d, i) => (
          <path key={`a${i}`} d={d} strokeOpacity={0.08 + (i % 4 === 0 ? 0.14 : 0.06)} />
        ))}
        {rings(260, 560, 10, 9).map((d, i) => (
          <path key={`b${i}`} d={d} strokeOpacity={0.06 + (i % 4 === 0 ? 0.1 : 0.05)} />
        ))}
      </g>
      <circle cx="1320" cy="120" r="5" fill="var(--primary)" fillOpacity="0.5" />
    </Svg>
  )
})

const Blueprint = memo(function Blueprint() {
  const id = useId()
  return (
    <Svg>
      <defs>
        <pattern id={`${id}m`} width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="var(--primary)" strokeOpacity="0.07" />
        </pattern>
        <pattern id={`${id}M`} width="120" height="120" patternUnits="userSpaceOnUse">
          <rect width="120" height="120" fill={`url(#${id}m)`} />
          <path d="M120 0H0V120" fill="none" stroke="var(--primary)" strokeOpacity="0.13" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill={`url(#${id}M)`} />
      <Glow id={`${id}g`} cx={1250} cy={80} r={480} color="var(--primary)" opacity={0.16} />
      <g fill="none" stroke="var(--primary)" strokeOpacity="0.35" strokeWidth="1.2">
        <circle cx="1240" cy="250" r="150" strokeDasharray="4 6" />
        <rect x="1060" y="150" width="190" height="130" rx="10" />
        <path d="M1060 320h360M1060 314v12M1420 314v12" />
        <path d="M1330 120l90 90" strokeDasharray="3 5" />
      </g>
      <text x="1205" y="345" fill="var(--primary)" fillOpacity="0.45" fontSize="12" fontFamily="ui-monospace, monospace">
        360 px
      </text>
    </Svg>
  )
})

const Circuit = memo(function Circuit() {
  const id = useId()
  const r = rng(13)
  const traces = Array.from({ length: 22 }, () => {
    let x = 700 + r() * 900
    let y = r() * H
    let d = `M${x.toFixed(0)} ${y.toFixed(0)}`
    for (let s = 0; s < 4; s++) {
      if (s % 2 === 0) x += (r() > 0.5 ? 1 : -1) * (40 + r() * 140)
      else y += (r() > 0.5 ? 1 : -1) * (30 + r() * 100)
      d += ` L${x.toFixed(0)} ${y.toFixed(0)}`
    }
    return { d, x, y }
  })
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1250} cy={100} r={500} color="var(--primary)" opacity={0.16} />
      <g fill="none" stroke="var(--primary)" strokeOpacity="0.2" strokeWidth="1.4" strokeLinejoin="round">
        {traces.map((t, i) => (
          <path key={i} d={t.d} />
        ))}
      </g>
      {traces.map((t, i) => (
        <circle key={i} cx={t.x} cy={t.y} r="3.5" fill="var(--surface)" stroke="var(--primary)" strokeOpacity="0.5" />
      ))}
    </Svg>
  )
})

const Aurora = memo(function Aurora({ onDark }: { onDark?: boolean }) {
  const id = useId()
  const r = rng(3)
  // on the dark sign-in panel the text sits low, so shapes stay in the top half there
  const shapes = Array.from({ length: 14 }, () => ({ x: r() * W, y: r() * H * (onDark ? 0.5 : 1), s: 10 + r() * 26, k: Math.floor(r() * 3), rot: r() * 90 }))
  const stroke = onDark ? '#ffffff' : 'var(--primary)'
  return (
    <Svg>
      <Glow id={`${id}a`} cx={1100} cy={120} r={560} color="var(--primary)" opacity={onDark ? 0.75 : 0.22} />
      <Glow id={`${id}b`} cx={420} cy={600} r={480} color="var(--chart-5)" opacity={onDark ? 0.35 : 0.12} />
      <Glow id={`${id}c`} cx={1450} cy={560} r={360} color="#ec4899" opacity={onDark ? 0.3 : 0.08} />
      <g fill="none" stroke={stroke} strokeOpacity={onDark ? 0.22 : 0.18} strokeWidth="1.5">
        {shapes.map((s, i) =>
          s.k === 0 ? (
            <circle key={i} cx={s.x} cy={s.y} r={s.s} />
          ) : s.k === 1 ? (
            <rect key={i} x={s.x} y={s.y} width={s.s * 1.6} height={s.s * 1.6} rx={s.s * 0.35} transform={`rotate(${s.rot} ${s.x} ${s.y})`} />
          ) : (
            <path key={i} d={`M${s.x - s.s} ${s.y}h${s.s * 2}M${s.x} ${s.y - s.s}v${s.s * 2}`} strokeLinecap="round" />
          ),
        )}
      </g>
    </Svg>
  )
})

const Ribbons = memo(function Ribbons() {
  const id = useId()
  const ribbon = (y: number, amp: number, phase: number) => {
    const pts = Array.from({ length: 9 }, (_, i) => [i * 200, y + Math.sin(i * 0.9 + phase) * amp] as const)
    const top = pts.map(([x, yy], i) => `${i ? 'L' : 'M'}${x} ${yy.toFixed(1)}`).join(' ')
    const bottom = [...pts].reverse().map(([x, yy]) => `L${x} ${(yy + 46 + Math.cos(x / 260 + phase) * 18).toFixed(1)}`).join(' ')
    return `${top} ${bottom} Z`
  }
  return (
    <Svg>
      <defs>
        <linearGradient id={`${id}r`} x1="0" x2="1">
          <stop offset="0" stopColor="var(--primary)" stopOpacity="0" />
          <stop offset="0.45" stopColor="var(--primary)" stopOpacity="0.22" />
          <stop offset="1" stopColor="var(--chart-5)" stopOpacity="0.12" />
        </linearGradient>
        <linearGradient id={`${id}s`} x1="0" x2="1">
          <stop offset="0" stopColor="#ec4899" stopOpacity="0" />
          <stop offset="0.6" stopColor="#ec4899" stopOpacity="0.14" />
          <stop offset="1" stopColor="var(--primary)" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      <Glow id={`${id}g`} cx={1200} cy={80} r={520} color="var(--primary)" opacity={0.18} />
      <path d={ribbon(150, 70, 0)} fill={`url(#${id}r)`} />
      <path d={ribbon(230, 90, 1.7)} fill={`url(#${id}s)`} />
      <path d={ribbon(330, 60, 3.1)} fill={`url(#${id}r)`} opacity="0.6" />
    </Svg>
  )
})

const Confetti = memo(function Confetti() {
  const id = useId()
  const r = rng(99)
  const colors = ['var(--primary)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)', '#ec4899']
  const bits = Array.from({ length: 70 }, () => {
    const a = r() * Math.PI - Math.PI // upper half burst from the centre top
    const d = 120 + r() * 640
    return { x: 800 + Math.cos(a) * d * 1.3, y: 300 + Math.sin(a) * d * 0.55, w: 6 + r() * 10, h: 4 + r() * 6, rot: r() * 180, c: colors[Math.floor(r() * colors.length)]!, k: r() }
  })
  return (
    <Svg>
      <Glow id={`${id}g`} cx={800} cy={260} r={480} color="var(--primary)" opacity={0.16} />
      {bits.map((b, i) =>
        b.k > 0.7 ? (
          <circle key={i} cx={b.x} cy={b.y} r={b.h * 0.7} fill={b.c} fillOpacity="0.55" />
        ) : (
          <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} rx="1.5" transform={`rotate(${b.rot} ${b.x} ${b.y})`} fill={b.c} fillOpacity="0.6" />
        ),
      )}
    </Svg>
  )
})

const Orbit = memo(function Orbit() {
  const id = useId()
  return (
    <Svg>
      <Glow id={`${id}g`} cx={800} cy={320} r={420} color="var(--primary)" opacity={0.16} />
      <g fill="none" stroke="var(--primary)">
        {[120, 200, 290].map((rr, i) => (
          <ellipse key={rr} cx="800" cy="320" rx={rr * 1.6} ry={rr * 0.62} strokeOpacity={0.18 - i * 0.04} strokeDasharray={i === 1 ? '3 7' : undefined} transform="rotate(-10 800 320)" />
        ))}
      </g>
      <circle cx="1040" cy="236" r="7" fill="var(--primary)" fillOpacity="0.6" />
      <circle cx="420" cy="430" r="5" fill="var(--chart-3)" fillOpacity="0.6" />
      <circle cx="1210" cy="470" r="4" fill="var(--chart-2)" fillOpacity="0.6" />
    </Svg>
  )
})

const Notebook = memo(function Notebook() {
  const id = useId()
  const r = rng(13)
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1260} cy={90} r={460} color="var(--primary)" opacity={0.14} />
      <Glow id={`${id}g2`} cx={240} cy={40} r={340} color="var(--chart-3)" opacity={0.1} />
      <g stroke="var(--chart-5)" strokeOpacity="0.16" strokeWidth="1.5">
        {Array.from({ length: 16 }, (_, i) => (
          <line key={i} x1="0" x2={W} y1={70 + i * 36} y2={70 + i * 36} />
        ))}
      </g>
      <line x1="150" x2="150" y1="0" y2={H} stroke="var(--chart-4)" strokeOpacity="0.28" strokeWidth="2" />
      {[150, 330, 510].map((y) => (
        <circle key={y} cx="60" cy={y} r="11" fill="none" stroke="var(--text-subtle)" strokeOpacity="0.25" strokeWidth="2" />
      ))}
      {/* pencil marks: an underline swoosh, a star, a circled word */}
      <path d="M 1010 214 q 120 -18 250 4" fill="none" stroke="var(--primary)" strokeOpacity="0.4" strokeWidth="4" strokeLinecap="round" />
      <path d="M 1340 132 l 9 20 l 22 2 l -17 14 l 6 22 l -20 -12 l -20 12 l 6 -22 l -17 -14 l 22 -2 Z" fill="var(--chart-3)" fillOpacity="0.32" />
      <ellipse cx="760" cy="138" rx="96" ry="30" fill="none" stroke="var(--chart-2)" strokeOpacity="0.35" strokeWidth="3" transform="rotate(-4 760 138)" />
      {Array.from({ length: 7 }, (_, i) => {
        const y = 70 + (2 + i * 2) * 36 - 10
        const x = 220 + r() * 120
        return <rect key={i} x={x} y={y} width={180 + r() * 520} height="7" rx="3.5" fill="var(--text-subtle)" fillOpacity={0.08 + r() * 0.06} />
      })}
    </Svg>
  )
})

const Guilloche = memo(function Guilloche() {
  const id = useId()
  // spirograph rosettes, as on banknotes and certificates
  const rosette = (cx: number, cy: number, R: number, rr: number, d: number, turns: number) => {
    const pts: string[] = []
    for (let t = 0; t <= Math.PI * 2 * turns; t += 0.02) {
      const x = cx + (R - rr) * Math.cos(t) + d * Math.cos(((R - rr) / rr) * t)
      const y = cy + (R - rr) * Math.sin(t) - d * Math.sin(((R - rr) / rr) * t)
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`)
    }
    return `M${pts.join(' L')}`
  }
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1250} cy={200} r={480} color="var(--chart-3)" opacity={0.16} />
      <Glow id={`${id}g2`} cx={300} cy={120} r={420} color="var(--primary)" opacity={0.14} />
      <path d={rosette(1250, 230, 210, 42, 80, 21)} fill="none" stroke="var(--chart-3)" strokeOpacity="0.32" strokeWidth="1" />
      <path d={rosette(1250, 230, 120, 30, 46, 15)} fill="none" stroke="var(--primary)" strokeOpacity="0.28" strokeWidth="1" />
      <path d={rosette(1500, 470, 110, 26, 44, 13)} fill="none" stroke="var(--primary)" strokeOpacity="0.2" strokeWidth="1" />
      <g fill="none" stroke="var(--chart-3)" strokeOpacity="0.18">
        {Array.from({ length: 5 }, (_, i) => (
          <path key={i} d={`M 0 ${520 + i * 9} C 400 ${470 + i * 9}, 1200 ${590 + i * 9}, 1600 ${510 + i * 9}`} />
        ))}
      </g>
    </Svg>
  )
})

const Honeycomb = memo(function Honeycomb() {
  const id = useId()
  const r = rng(31)
  const hex = (x: number, y: number, s: number) => Array.from({ length: 6 }, (_, i) => `${(x + s * Math.cos((Math.PI / 3) * i + Math.PI / 6)).toFixed(1)},${(y + s * Math.sin((Math.PI / 3) * i + Math.PI / 6)).toFixed(1)}`).join(' ')
  const colors = ['var(--primary)', 'var(--chart-3)', 'var(--chart-2)', 'var(--chart-5)']
  const cells: ReactNode[] = []
  for (let row = 0; row < 7; row++) {
    for (let col = 0; col < 20; col++) {
      const x = col * 90 + (row % 2 ? 45 : 0)
      const y = row * 78
      const k = r()
      const fade = Math.max(0, 1 - Math.abs(x - 1150) / 900)
      cells.push(
        <polygon key={`${row}-${col}`} points={hex(x, y, 40)} fill={k > 0.85 ? colors[Math.floor(r() * 4)] : 'none'} fillOpacity={0.22 * fade + 0.04} stroke="var(--primary)" strokeOpacity={0.12 * fade + 0.03} strokeWidth="1.5" />,
      )
    }
  }
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1150} cy={160} r={520} color="var(--chart-3)" opacity={0.14} />
      {cells}
    </Svg>
  )
})

const Checklist = memo(function Checklist() {
  const id = useId()
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1220} cy={140} r={480} color="var(--chart-2)" opacity={0.14} />
      <Glow id={`${id}g2`} cx={300} cy={80} r={360} color="var(--primary)" opacity={0.1} />
      <g transform="translate(170 40) rotate(-6 1180 300)" opacity="0.85">
        <rect x="960" y="70" width="420" height="520" rx="22" fill="var(--surface)" fillOpacity="0.55" stroke="var(--primary)" strokeOpacity="0.22" strokeWidth="2" />
        <rect x="1110" y="50" width="120" height="40" rx="10" fill="var(--primary)" fillOpacity="0.25" />
        {Array.from({ length: 6 }, (_, i) => {
          const y = 140 + i * 70
          const done = i < 4
          return (
            <g key={i}>
              <rect x="1000" y={y} width="34" height="34" rx="8" fill={done ? 'var(--success)' : 'none'} fillOpacity="0.28" stroke={done ? 'var(--success)' : 'var(--text-subtle)'} strokeOpacity="0.5" strokeWidth="2" />
              {done ? <path d={`M ${1008} ${y + 17} l 7 7 l 13 -14`} fill="none" stroke="var(--success)" strokeOpacity="0.8" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" /> : null}
              <rect x="1056" y={y + 11} width={180 + ((i * 47) % 110)} height="12" rx="6" fill="var(--text-subtle)" fillOpacity="0.14" />
            </g>
          )
        })}
      </g>
      <g stroke="var(--primary)" strokeOpacity="0.07">
        {Array.from({ length: 22 }, (_, i) => (
          <line key={i} x1={i * 40} x2={i * 40} y1="0" y2={H} />
        ))}
      </g>
    </Svg>
  )
})

const Signal = memo(function Signal() {
  const id = useId()
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1240} cy={180} r={460} color="var(--primary)" opacity={0.18} />
      <g fill="none" stroke="var(--primary)">
        {Array.from({ length: 7 }, (_, i) => (
          <circle key={i} cx="1240" cy="180" r={70 + i * 72} strokeOpacity={0.26 - i * 0.032} strokeWidth={2} strokeDasharray={i % 2 ? '4 10' : undefined} />
        ))}
      </g>
      <path d="M 1240 140 c -26 0 -38 20 -38 44 v 20 l -12 16 h 100 l -12 -16 v -20 c 0 -24 -12 -44 -38 -44 Z M 1228 228 a 12 12 0 0 0 24 0" fill="var(--primary)" fillOpacity="0.3" />
      <circle cx="1268" cy="148" r="9" fill="var(--chart-4)" fillOpacity="0.65" />
      {[[560, 120, 'var(--chart-2)'], [880, 410, 'var(--chart-3)'], [380, 330, 'var(--chart-5)']].map(([x, y, c], i) => (
        <circle key={i} cx={x as number} cy={y as number} r="6" fill={c as string} fillOpacity="0.5" />
      ))}
    </Svg>
  )
})

const Dials = memo(function Dials() {
  const id = useId()
  const dial = (cx: number, cy: number, r: number, angle: number, color: string) => (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="var(--surface)" fillOpacity="0.4" stroke={color} strokeOpacity="0.3" strokeWidth="2" />
      {Array.from({ length: 36 }, (_, i) => {
        const a = (i / 36) * Math.PI * 2
        const inner = r + 8
        const outer = r + (i % 3 ? 16 : 26)
        return <line key={i} x1={cx + Math.cos(a) * inner} y1={cy + Math.sin(a) * inner} x2={cx + Math.cos(a) * outer} y2={cy + Math.sin(a) * outer} stroke={color} strokeOpacity={i % 3 ? 0.18 : 0.35} strokeWidth="2" />
      })}
      <line x1={cx} y1={cy} x2={cx + Math.cos(angle) * (r - 14)} y2={cy + Math.sin(angle) * (r - 14)} stroke={color} strokeOpacity="0.6" strokeWidth="5" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="7" fill={color} fillOpacity="0.6" />
    </g>
  )
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1180} cy={200} r={480} color="var(--primary)" opacity={0.15} />
      {dial(1180, 230, 120, -0.9, 'var(--primary)')}
      {dial(1420, 120, 60, 2.2, 'var(--chart-5)')}
      {dial(930, 90, 46, 0.4, 'var(--chart-2)')}
      {/* sliders on the right, clear of page titles and navigation */}
      <g stroke="var(--primary)" strokeOpacity="0.16" strokeWidth="6" strokeLinecap="round">
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <line x1="1330" x2="1560" y1={300 + i * 56} y2={300 + i * 56} />
            <circle cx={1370 + i * 70} cy={300 + i * 56} r="12" fill="var(--surface)" stroke="var(--primary)" strokeOpacity="0.4" strokeWidth="3" />
          </g>
        ))}
      </g>
    </Svg>
  )
})

const Bubbles = memo(function Bubbles() {
  const id = useId()
  const bubble = (x: number, y: number, w: number, h: number, left: boolean, color: string, o: number) => (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={h / 2.4} fill={color} fillOpacity={o} />
      <path d={left ? `M ${x + 26} ${y + h - 2} l -14 20 l 30 -14 Z` : `M ${x + w - 26} ${y + h - 2} l 14 20 l -30 -14 Z`} fill={color} fillOpacity={o} />
      {[0, 1, 2].map((i) => (
        <circle key={i} cx={x + w / 2 - 20 + i * 20} cy={y + h / 2} r="5" fill="var(--surface)" fillOpacity="0.7" />
      ))}
    </g>
  )
  return (
    <Svg>
      <Glow id={`${id}g`} cx={1220} cy={160} r={500} color="var(--chart-5)" opacity={0.14} />
      <Glow id={`${id}g2`} cx={260} cy={60} r={360} color="var(--primary)" opacity={0.12} />
      {bubble(1000, 250, 260, 78, true, 'var(--primary)', 0.16)}
      {bubble(1180, 120, 220, 70, false, 'var(--chart-5)', 0.18)}
      {bubble(1060, 30, 170, 56, true, 'var(--chart-2)', 0.14)}
      {bubble(1340, 330, 150, 52, false, 'var(--primary)', 0.1)}
      {bubble(640, 90, 130, 46, true, 'var(--chart-3)', 0.1)}
    </Svg>
  )
})

/**
 * The artwork for one page, placed behind its top area and faded into the page
 * background so content always reads clearly. Purely decorative (aria-hidden).
 */
export function Backdrop({ variant, height = 560, className, from, to, fade = true, onDark, seed }: { variant: BackdropVariant; height?: number | string; className?: string; from?: string; to?: string; fade?: boolean; onDark?: boolean; seed?: number }) {
  const art = {
    constellation: <Constellation />,
    mosaic: <Mosaic seed={seed} />,
    waves: <Waves from={from} to={to} />,
    path: <Path />,
    contours: <Contours />,
    blueprint: <Blueprint />,
    circuit: <Circuit />,
    aurora: <Aurora onDark={onDark} />,
    orbit: <Orbit />,
    ribbons: <Ribbons />,
    confetti: <Confetti />,
    notebook: <Notebook />,
    guilloche: <Guilloche />,
    honeycomb: <Honeycomb />,
    checklist: <Checklist />,
    signal: <Signal />,
    dials: <Dials />,
    bubbles: <Bubbles />,
  }[variant]
  return (
    <div
      aria-hidden
      className={cn('pointer-events-none absolute inset-x-0 top-0 -z-0 overflow-hidden select-none', fade && '[mask-image:linear-gradient(to_bottom,black_45%,transparent)]', className)}
      style={{ height }}
    >
      {art}
    </div>
  )
}
