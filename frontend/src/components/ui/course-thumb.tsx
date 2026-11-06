import { Briefcase, Code2, HeartPulse, Megaphone, Palette, Server, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'

import { useId } from 'react'

import { cn } from '@/lib/cn'

// Courses without an uploaded image get a branded cover: a gradient per category and
// its icon. Same course, same cover, every time.
const covers: Record<string, { from: string; to: string; Icon: LucideIcon }> = {
  development: { from: '#7c3aed', to: '#4f46e5', Icon: Code2 },
  business: { from: '#0f766e', to: '#0e9f6e', Icon: Briefcase },
  design: { from: '#db2777', to: '#9333ea', Icon: Palette },
  'it-software': { from: '#2563eb', to: '#0891b2', Icon: Server },
  'health-safety': { from: '#ea580c', to: '#dc2626', Icon: ShieldCheck },
  'care-compliance': { from: '#0891b2', to: '#2563eb', Icon: HeartPulse },
  marketing: { from: '#f59e0b', to: '#ea580c', Icon: Megaphone },
}
const fallback = { from: '#6d28d9', to: '#a21caf', Icon: Sparkles }

/** The gradient a category uses (course covers, and the course page artwork). */
// eslint-disable-next-line react/only-export-components
export function coverColors(category?: string | null) {
  const { from, to } = covers[slugOf(category)] ?? fallback
  return { from, to }
}

function slugOf(category?: string | null) {
  return (category ?? '').toLowerCase().replace(/&/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

export function CourseThumb({ src, title, category, className }: { src?: string | null; title: string; category?: string | null; className?: string }) {
  const pid = useId()
  if (src) {
    return <img src={src} alt="" loading="lazy" decoding="async" className={cn('aspect-video w-full rounded-md object-cover', className)} />
  }
  const { from, to, Icon } = covers[slugOf(category)] ?? fallback
  return (
    <div
      role="img"
      aria-label={title}
      className={cn('relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-md', className)}
      style={{ backgroundImage: `linear-gradient(135deg, ${from}, ${to})` }}
    >
      <svg className="absolute inset-0 size-full opacity-[0.14]" aria-hidden>
        <defs>
          <pattern id={pid} width="16" height="16" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.4" fill="#fff" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#${pid})`} />
      </svg>
      <span className="absolute -right-6 -bottom-8 size-28 rounded-full bg-white/10" aria-hidden />
      <span className="relative flex size-12 items-center justify-center rounded-xl bg-white/15 text-white ring-1 ring-white/25 backdrop-blur-sm">
        <Icon className="size-6" strokeWidth={1.75} />
      </span>
    </div>
  )
}
