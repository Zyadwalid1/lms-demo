import { BookOpen, Building2, PlayCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { CourseThumb } from '@/components/ui/course-thumb'
import { EmptyState, ErrorState } from '@/components/ui/misc'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { useMe } from '@/features/identity/auth'
import { useMyCourses } from '@/features/learning/api'
import { Link } from '@/lib/router'

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
}

export function MyLearningPage() {
  const { data: me } = useMe()
  const { data, isLoading, error, refetch } = useMyCourses()
  const items = data?.items ?? []
  const current = items.find((i) => i.progress_pct > 0 && i.progress_pct < 100) ?? items[0]

  return (
    <>
      <p className="text-sm text-muted">
        {greeting()}, {me?.full_name?.split(' ')[0] || 'there'}
      </p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-[26px]">Continue your learning</h1>

      {error ? (
        <ErrorState message={(error as Error).message} onRetry={() => void refetch()} />
      ) : isLoading ? (
        <div className="mt-6 grid gap-4">
          <Skeleton className="h-40 rounded-lg" />
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-64 rounded-lg" />
            ))}
          </div>
        </div>
      ) : !items.length ? (
        <Card className="mt-6">
          <EmptyState icon={<BookOpen />} title="No courses yet" body="Courses you buy, and training your company assigns, appear here." action={<Button asChild><Link to="/courses">Browse courses</Link></Button>} />
        </Card>
      ) : (
        <>
          {current ? (
            <Card className="mt-6 flex animate-reveal flex-col gap-5 p-4 sm:flex-row sm:items-center sm:p-5">
              <CourseThumb src={current.thumbnail_url} title={current.title} className="sm:w-56" />
              <div className="min-w-0 flex-1">
                <Badge tone="primary">{current.progress_pct > 0 ? 'In progress' : 'Up next'}</Badge>
                <h2 className="mt-2 text-lg font-semibold tracking-tight">{current.title}</h2>
                <p className="text-sm text-muted">{current.instructors.join(', ')}</p>
                <div className="mt-4 flex items-center gap-3">
                  <Progress value={current.progress_pct} label="Progress" />
                  <span className="text-xs text-muted tabular">{Math.round(current.progress_pct)}%</span>
                </div>
              </div>
              <Button size="lg" asChild>
                <Link to={`/learn/${current.slug}`}>
                  <PlayCircle /> {current.progress_pct > 0 ? 'Continue' : 'Start'}
                </Link>
              </Button>
            </Card>
          ) : null}
          <h2 className="mt-10 mb-4 text-lg font-semibold tracking-tight">My courses</h2>
          <div className="stagger grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {items.map((c) => (
              <Link key={c.enrollment_id} to={`/learn/${c.slug}`} className="group rounded-lg border border-border bg-surface p-2.5 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow">
                <CourseThumb src={c.thumbnail_url} title={c.title} />
                <div className="px-1 pt-3 pb-1">
                  <h3 className="line-clamp-2 text-[15px] font-semibold group-hover:text-primary">{c.title}</h3>
                  {c.org_name ? (
                    <p className="mt-1 inline-flex items-center gap-1 text-xs text-muted">
                      <Building2 className="size-3.5" /> Assigned by {c.org_name}
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-muted">{c.instructors.join(', ')}</p>
                  )}
                  <div className="mt-3 flex items-center gap-3">
                    <Progress value={c.progress_pct} tone={c.progress_pct >= 100 ? 'success' : 'primary'} label="Progress" />
                    <span className="text-xs text-muted tabular">{Math.round(c.progress_pct)}%</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  )
}
