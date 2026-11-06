import { useCountUp, useInView } from '@/lib/motion'

/** A number that counts up when it scrolls into view. Screen readers get the final value. */
export function CountUp({ value, format = (n) => Math.round(n).toLocaleString('en-GB'), className }: { value: number; format?: (n: number) => string; className?: string }) {
  const [ref, seen] = useInView<HTMLSpanElement>()
  const v = useCountUp(value, seen)
  return (
    <span ref={ref} className={className}>
      <span aria-hidden>{format(v)}</span>
      <span className="sr-only">{format(value)}</span>
    </span>
  )
}
