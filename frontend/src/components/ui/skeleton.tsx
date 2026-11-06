import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/cn'

/** Placeholder shaped like the content that is loading, so nothing jumps when it arrives. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden className={cn('animate-pulse rounded-md bg-surface-2', className)} {...props} />
}
