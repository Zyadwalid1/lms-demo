import * as P from '@radix-ui/react-popover'
import { Award, Bell, BellOff, CheckCheck, ClipboardCheck, Megaphone, MessageSquare, Star, Ticket } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { type Notification, useMarkRead, useNotifications, useUnreadCount } from '@/features/engagement/api'
import { cn } from '@/lib/cn'
import { relativeDate } from '@/lib/format'
import { Link, useNavigate } from '@/lib/router'

const icons: Record<string, typeof Bell> = {
  course_assigned: ClipboardCheck,
  answer_posted: MessageSquare,
  question_posted: MessageSquare,
  announcement: Megaphone,
  review_reply: Star,
  badge_awarded: Award,
  ticket_reply: Ticket,
  certificate_issued: Award,
  work_marked: ClipboardCheck,
}

/** One notification row, shared by the bell and the notifications page. */
export function NotificationRow({ n, onOpen, compact }: { n: Notification; onOpen: (n: Notification) => void; compact?: boolean }) {
  const Icon = icons[n.kind] ?? Bell
  const unread = !n.read_at
  return (
    <button type="button" onClick={() => onOpen(n)} className={cn('group flex w-full items-start gap-3 text-left transition-colors hover:bg-surface-2', compact ? 'px-4 py-3' : 'rounded-xl border border-border bg-surface p-4 shadow-sm', unread && !compact && 'border-primary/30')}>
      <span className={cn('flex size-9 shrink-0 items-center justify-center rounded-full', unread ? 'bg-primary-soft text-primary-soft-text' : 'bg-surface-2 text-muted')}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn('block text-sm', unread ? 'font-semibold' : 'font-medium')}>{n.title}</span>
        {n.body ? <span className={cn('block text-[13px] text-muted', compact && 'line-clamp-2')}>{n.body}</span> : null}
        <span className="mt-1 block text-xs text-subtle">{relativeDate(n.created_at)}</span>
      </span>
      {unread ? <span aria-label="Unread" className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" /> : null}
    </button>
  )
}

/** Open a notification: mark it read, then go where it points (only our own pages). */
export function useOpenNotification() {
  const mark = useMarkRead()
  const navigate = useNavigate()
  return (n: Notification) => {
    if (!n.read_at) mark.mutate([n.id])
    if (n.url?.startsWith('/') && !n.url.startsWith('//')) navigate(n.url)
  }
}

/** The bell: unread count (polled once a minute), the latest few, and "mark all read". */
export function NotificationBell({ onDark }: { onDark?: boolean }) {
  const [open, setOpen] = useState(false)
  const unread = useUnreadCount()
  const list = useNotifications(false, open)
  const markAll = useMarkRead()
  const openOne = useOpenNotification()
  const count = unread.data?.unread ?? 0
  const items = list.data?.pages[0]?.items.slice(0, 6) ?? []

  return (
    <P.Root open={open} onOpenChange={setOpen}>
      <P.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label={count ? `Notifications, ${count} unread` : 'Notifications'} className={cn('relative', onDark && 'text-nav-text hover:bg-nav-hover hover:text-white')}>
          <Bell key={count} className={count ? 'animate-bounce-once' : undefined} />
          {count ? (
            <span className="absolute top-1 right-0.5 flex h-[18px] min-w-[18px] animate-pop items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white ring-2 ring-surface tabular">
              {count > 99 ? '99+' : count}
            </span>
          ) : null}
        </Button>
      </P.Trigger>
      <P.Portal>
        <P.Content align="end" sideOffset={8} collisionPadding={12} className="z-50 w-[min(380px,calc(100vw-24px))] origin-(--radix-popover-content-transform-origin) animate-menu-in overflow-hidden rounded-xl border border-border bg-surface shadow-lg data-[state=closed]:animate-menu-out">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <p className="text-sm font-semibold">Notifications</p>
            {count ? (
              <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => markAll.mutate(null)} loading={markAll.isPending}>
                <CheckCheck /> Mark all read
              </Button>
            ) : null}
          </div>
          <div className="max-h-[min(420px,60dvh)] overflow-y-auto">
            {list.isLoading ? (
              <div className="grid gap-2 p-4">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : !items.length ? (
              <div className="flex flex-col items-center px-6 py-10 text-center">
                <BellOff className="size-6 text-subtle" />
                <p className="mt-2 text-sm font-medium">You're all caught up</p>
                <p className="text-xs text-muted">Answers, announcements and new training appear here.</p>
              </div>
            ) : (
              <ul className="stagger divide-y divide-border">
                {items.map((n) => (
                  <li key={n.id}>
                    <NotificationRow n={n} compact onOpen={(x) => (setOpen(false), openOne(x))} />
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Link to="/notifications" onClick={() => setOpen(false)} className="block border-t border-border px-4 py-2.5 text-center text-sm font-medium text-primary hover:bg-surface-2">
            See all notifications
          </Link>
        </P.Content>
      </P.Portal>
    </P.Root>
  )
}
