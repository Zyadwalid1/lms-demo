import { cn } from '@/lib/cn'

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn('size-8', className)} aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--primary)" />
      <path d="M9 10.5 16 7l7 3.5-7 3.5-7-3.5Z" fill="#fff" />
      <path d="M11 13.5v5c0 1.7 2.2 3.5 5 3.5s5-1.8 5-3.5v-5l-5 2.5-5-2.5Z" fill="#fff" opacity=".85" />
      <path d="M23 10.5v6" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

export function Logo({ className, inverted }: { className?: string; inverted?: boolean }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <LogoMark />
      <span className={cn('text-[19px] font-bold tracking-tight', inverted ? 'text-white' : 'text-text')}>LearnHub</span>
    </span>
  )
}
