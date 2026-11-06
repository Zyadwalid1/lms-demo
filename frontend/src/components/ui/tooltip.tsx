import * as T from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'

export const TooltipProvider = T.Provider

export function Tooltip({ content, children, side = 'top' }: { content: ReactNode; children: ReactNode; side?: 'top' | 'right' | 'bottom' | 'left' }) {
  return (
    <T.Root delayDuration={300}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content side={side} sideOffset={6} className="z-50 max-w-64 origin-[var(--radix-tooltip-content-transform-origin)] animate-menu-in rounded-md bg-text px-2.5 py-1.5 text-xs text-background shadow-lg">
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}
