import * as A from '@radix-ui/react-avatar'

import { cn } from '@/lib/cn'
import { initials } from '@/lib/format'

const sizes = { sm: 'size-7 text-[11px]', md: 'size-9 text-xs', lg: 'size-12 text-sm' }
// a stable colour per person, from the brand-safe chart palette
const tones = ['bg-primary-soft text-primary-soft-text', 'bg-success-soft text-success', 'bg-warning-soft text-warning', 'bg-info-soft text-info', 'bg-danger-soft text-danger']

export function Avatar({ name, src, size = 'md', className }: { name: string; src?: string; size?: keyof typeof sizes; className?: string }) {
  const tone = tones[[...name].reduce((a, c) => a + c.charCodeAt(0), 0) % tones.length]
  return (
    <A.Root className={cn('inline-flex shrink-0 overflow-hidden rounded-full font-semibold', sizes[size], className)}>
      {src ? <A.Image src={src} alt="" className="size-full object-cover" /> : null}
      <A.Fallback className={cn('flex size-full items-center justify-center', tone)} delayMs={src ? 300 : 0}>
        {initials(name) || '?'}
      </A.Fallback>
    </A.Root>
  )
}
