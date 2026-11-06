/** Small motion helpers. Everything here respects "reduce motion". */
import { type RefObject, useEffect, useRef, useState } from 'react'

export const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** true once the element has scrolled into view (then stays true). */
export function useInView<T extends Element>(): [RefObject<T | null>, boolean] {
  const ref = useRef<T>(null)
  const [seen, setSeen] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    const io = new IntersectionObserver(([e]) => e?.isIntersecting && (setSeen(true), io.disconnect()), { threshold: 0.2 })
    io.observe(el)
    return () => io.disconnect()
  }, [seen])
  return [ref, seen]
}

/** Counts from 0 to `target` (ease-out, ~0.8 s) once `start` is true. */
export function useCountUp(target: number, start = true, ms = 800) {
  const [v, setV] = useState(0)
  const still = reducedMotion()
  useEffect(() => {
    if (!start || still) return
    let raf = 0
    const t0 = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / ms)
      setV(target * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, start, ms, still])
  return still ? target : v
}

/** 0 on the first paint, then the real value: CSS transitions animate the fill. */
export function useFill(value: number, start = true) {
  const [v, setV] = useState(() => (reducedMotion() ? value : 0))
  useEffect(() => {
    if (!start) return
    const id = requestAnimationFrame(() => setV(value))
    return () => cancelAnimationFrame(id)
  }, [value, start])
  return v
}

/** Tiny event bus for "something was added" nudges (cart icon bounce). */
const bus = new EventTarget()
export const emit = (name: string) => bus.dispatchEvent(new Event(name))
export function useOn(name: string, fn: () => void) {
  useEffect(() => {
    bus.addEventListener(name, fn)
    return () => bus.removeEventListener(name, fn)
  }, [name, fn])
}
