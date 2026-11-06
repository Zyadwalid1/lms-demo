import { BellOff, CheckCheck, Settings } from 'lucide-react'
import { useState } from 'react'

import { NotificationRow, useOpenNotification } from '@/components/layout/NotificationBell'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState, ErrorState, PageHeader } from '@/components/ui/misc'
import { Skeleton } from '@/components/ui/skeleton'
import { useMarkRead, useNotifications } from '@/features/engagement/api'
import { Link } from '@/lib/router'

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const q = useNotifications(unreadOnly)
  const mark = useMarkRead()
  const open = useOpenNotification()
  const items = q.data?.pages.flatMap((p) => p.items) ?? []
  const unread = q.data?.pages[0]?.unread ?? 0

  return (
    <>
      <PageHeader
        title="Notifications"
        description={unread ? `${unread} unread` : 'Answers to your questions, announcements, new training and more.'}
        actions={
          <>
            <Button variant="secondary" size="sm" asChild>
              <Link to="/account#notifications">
                <Settings /> Settings
              </Link>
            </Button>
            {unread ? (
              <Button size="sm" onClick={() => mark.mutate(null)} loading={mark.isPending}>
                <CheckCheck /> Mark all read
              </Button>
            ) : null}
          </>
        }
      />
      <div className="mb-4 flex gap-2">
        <Button size="sm" variant={unreadOnly ? 'ghost' : 'soft'} onClick={() => setUnreadOnly(false)}>
          All
        </Button>
        <Button size="sm" variant={unreadOnly ? 'soft' : 'ghost'} onClick={() => setUnreadOnly(true)}>
          Unread
        </Button>
      </div>
      {q.error ? (
        <ErrorState message={q.error.message} onRetry={() => void q.refetch()} />
      ) : q.isLoading ? (
        <div className="grid gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : !items.length ? (
        <Card>
          <EmptyState icon={<BellOff />} title={unreadOnly ? 'Nothing unread' : 'No notifications yet'} body="You're all caught up." />
        </Card>
      ) : (
        <>
          <ul className="stagger grid gap-2.5">
            {items.map((n) => (
              <li key={n.id}>
                <NotificationRow n={n} onOpen={open} />
              </li>
            ))}
          </ul>
          {q.hasNextPage ? (
            <div className="mt-6 flex justify-center">
              <Button variant="secondary" onClick={() => void q.fetchNextPage()} loading={q.isFetchingNextPage}>
                Show older
              </Button>
            </div>
          ) : null}
        </>
      )}
    </>
  )
}
