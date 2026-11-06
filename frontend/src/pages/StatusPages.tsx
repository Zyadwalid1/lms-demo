import { Compass, Hammer } from 'lucide-react'

import { Backdrop } from '@/components/art/backdrops'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/misc'
import { Link } from '@/lib/router'

export function NotFoundPage() {
  return (
    <div className="relative isolate">
      <Backdrop variant="orbit" height={520} />
    <div className="relative mx-auto max-w-lg px-4 py-20">
      <EmptyState icon={<Compass />} title="Page not found" body="The page you are looking for doesn't exist or has moved." action={<Button asChild><Link to="/">Go home</Link></Button>} />
    </div>
    </div>
  )
}

/** Routes that exist in the navigation but are built in a later milestone. */
export function ComingSoon({ title, milestone }: { title: string; milestone: string }) {
  return (
    <Card className="relative isolate mx-auto my-6 max-w-2xl overflow-hidden">
      <Backdrop variant="orbit" height="100%" fade={false} />
      <EmptyState className="relative" icon={<Hammer />} title={title} body={`This screen is part of ${milestone}.`} />
    </Card>
  )
}
