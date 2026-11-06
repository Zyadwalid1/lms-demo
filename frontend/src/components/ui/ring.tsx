import { useCountUp, useFill, useInView } from '@/lib/motion'

/** A percentage ring (pure SVG: no chart library). Fills and counts up into view. */
export function Ring({ value, size = 132, stroke = 12, label, color = 'var(--primary)' }: { value: number; size?: number; stroke?: number; label?: string; color?: string }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const v = Math.max(0, Math.min(100, value))
  const [ref, seen] = useInView<HTMLDivElement>()
  const fill = useFill(v, seen)
  const n = useCountUp(v, seen, 900)
  return (
    <div ref={ref} className="relative" style={{ width: size, height: size }} role="img" aria-label={`${v.toFixed(0)}% ${label ?? ''}`.trim()}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - fill / 100)} className="transition-[stroke-dashoffset] duration-[900ms] ease-out" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[28px] leading-none font-bold tracking-tight tabular">{n.toFixed(0)}%</span>
        {label ? <span className="mt-1 text-[11px] text-muted">{label}</span> : null}
      </div>
    </div>
  )
}
