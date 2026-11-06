import { ArrowRight, Award, Briefcase, CheckCircle2, Code2, HeartPulse, Infinity as InfinityIcon, Megaphone, Palette, Search, Server, ShieldCheck, Sparkles, Star, Users, type LucideIcon } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { Backdrop } from '@/components/art/backdrops'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { CourseThumb } from '@/components/ui/course-thumb'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useCategories, useCourses, usePlans } from '@/features/catalog/api'
import { CourseGrid } from '@/features/catalog/CourseCard'
import { useMe } from '@/features/identity/auth'
import { cn } from '@/lib/cn'
import { money } from '@/lib/format'
import { Link, useNavigate } from '@/lib/router'

const categoryIcons: Record<string, LucideIcon> = { code: Code2, briefcase: Briefcase, palette: Palette, server: Server, 'shield-check': ShieldCheck, 'heart-pulse': HeartPulse, megaphone: Megaphone }

function Hero() {
  const [q, setQ] = useState('')
  const navigate = useNavigate()
  const submit = (e: FormEvent) => {
    e.preventDefault()
    navigate(`/courses${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ''}`)
  }
  return (
    <section className="relative overflow-hidden border-b border-border bg-surface">
      <Backdrop variant="constellation" height="100%" fade={false} />
      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-14 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-20">
        <div className="stagger">
          <Badge tone="primary" className="px-3 py-1 text-[13px]">
            <Sparkles /> Online courses for real skills
          </Badge>
          <h1 className="mt-5 text-4xl leading-[1.08] font-bold tracking-tight text-text sm:text-5xl lg:text-[56px]">
            Learn. Improve. <span className="text-primary">Advance.</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted">High-quality courses from industry experts. Buy what you need, or subscribe for everything, with certificates you can share.</p>
          <form onSubmit={submit} role="search" className="mt-8 flex max-w-xl gap-2 rounded-xl border border-border bg-surface p-1.5 shadow">
            <Input icon={<Search />} value={q} onChange={(e) => setQ(e.target.value)} placeholder="What do you want to learn?" aria-label="Search courses" className="h-11 border-0 shadow-none focus-visible:ring-0" />
            <Button type="submit" size="lg" className="h-11">
              Search
            </Button>
          </form>
          <dl className="mt-8 flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted">
            {[
              [Users, 'Learn at your own pace'],
              [Award, 'CPD certificates'],
              [ShieldCheck, 'Compliance training for teams'],
            ].map(([Icon, text]) => {
              const I = Icon as LucideIcon
              return (
                <div key={text as string} className="flex items-center gap-2">
                  <I className="size-4 text-primary" /> <dd>{text as string}</dd>
                </div>
              )
            })}
          </dl>
        </div>
        <HeroVisual />
      </div>
    </section>
  )
}

/** Decorative product preview (no stock photos): a course card, progress and a certificate. */
function HeroVisual() {
  return (
    <div aria-hidden className="relative mx-auto hidden h-[400px] w-full max-w-[480px] lg:block">
      <Card className="absolute top-0 right-0 w-[330px] rotate-[1.5deg] p-3 shadow-lg motion-safe:animate-[float_10s_ease-in-out_infinite]">
        <CourseThumb title="" category="Development" />
        <p className="mt-3 text-sm font-semibold">Web Development Fundamentals</p>
        <p className="text-xs text-muted">Daniel Reeve</p>
        <div className="mt-2 flex items-center gap-1 text-xs">
          <span className="font-semibold text-warning">4.8</span>
          {[1, 2, 3, 4, 5].map((i) => (
            <Star key={i} className="size-3 fill-warning text-warning" />
          ))}
        </div>
      </Card>
      <Card className="absolute bottom-2 left-0 w-[260px] -rotate-[2deg] p-4 shadow-lg motion-safe:animate-[float_12s_ease-in-out_infinite_reverse]">
        <p className="text-xs font-medium text-muted">Your progress</p>
        <p className="mt-1 text-sm font-semibold">Python for Data Analysis</p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-2">
          <div className="h-full w-[68%] rounded-full bg-primary" />
        </div>
        <p className="mt-2 text-xs text-muted">68% complete · 12 lectures left</p>
      </Card>
      <Card className="absolute top-10 left-0 flex w-[230px] items-center gap-3 p-4 shadow-lg motion-safe:animate-[float_9s_ease-in-out_infinite]">
        <span className="flex size-10 items-center justify-center rounded-full bg-success-soft text-success">
          <Award className="size-5" />
        </span>
        <div>
          <p className="text-sm font-semibold">Certificate earned</p>
          <p className="text-xs text-muted">Fire Safety Awareness</p>
        </div>
      </Card>
    </div>
  )
}

function Section({ title, description, action, children }: { title: string; description?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
          {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function Categories() {
  const { data, isLoading } = useCategories()
  return (
    <div className={cn('grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7', data && 'stagger')}>
      {isLoading || !data
        ? Array.from({ length: 7 }, (_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        : data.map((c) => {
            const Icon = categoryIcons[c.icon] ?? Sparkles
            return (
              <Link key={c.id} to={`/courses?category=${c.slug}`} className="group flex flex-col items-center gap-2.5 rounded-lg border border-border bg-surface px-3 py-5 text-center shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow">
                <span className="flex size-11 items-center justify-center rounded-xl bg-primary-soft text-primary-soft-text transition-colors group-hover:bg-primary group-hover:text-on-primary">
                  <Icon className="size-5" />
                </span>
                <span className="text-[13px] leading-tight font-medium">{c.name}</span>
              </Link>
            )
          })}
    </div>
  )
}

function Plans() {
  const { data } = usePlans()
  const personal = data?.find((p) => p.audience === 'personal')
  const team = data?.find((p) => p.audience === 'team')
  return (
    <div className="stagger grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr]">
      <div className="flex flex-col justify-center">
        <h2 className="text-2xl font-semibold tracking-tight">Get more with a subscription</h2>
        <p className="mt-2 text-muted">Access our whole personal library for one monthly price, or give your team everything they need to stay compliant.</p>
        <ul className="mt-4 grid gap-2 text-sm">
          {['Hundreds of courses, new every month', 'Certificates for every course', 'Cancel any time'].map((t) => (
            <li key={t} className="flex items-center gap-2">
              <CheckCircle2 className="size-4 text-success" /> {t}
            </li>
          ))}
        </ul>
      </div>
      {[
        { plan: personal, title: 'Personal Plan', unit: '/ month', note: personal?.trial_days ? `${personal.trial_days}-day free trial` : '', cta: 'Start free trial', Icon: InfinityIcon },
        { plan: team, title: 'Team Plan', unit: '/ seat / year', note: team ? 'From 5 seats · compliance dashboard' : '', cta: 'Get it for your team', Icon: Briefcase, featured: true },
      ].map(({ plan, title, unit, note, cta, Icon, featured }) => (
        <Card key={title} className={featured ? 'relative border-primary/50 p-6 ring-1 ring-primary/30' : 'p-6'}>
          {featured ? <Badge tone="primary" className="absolute top-4 right-4">Best for teams</Badge> : null}
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-text">
            <Icon className="size-5" />
          </span>
          <p className="mt-4 font-semibold">{title}</p>
          <p className="mt-1 text-3xl font-bold tracking-tight tabular">
            {plan ? money(plan.amount_minor, plan.currency, plan.exponent) : <Skeleton className="h-9 w-24" />}
            <span className="ml-1 text-sm font-normal text-muted">{unit}</span>
          </p>
          <p className="mt-1 text-sm text-muted">{note}</p>
          <Button className="mt-5 w-full" variant={featured ? 'primary' : 'secondary'} asChild>
            <Link to="/plans">{cta}</Link>
          </Button>
        </Card>
      ))}
    </div>
  )
}

export function HomePage() {
  const { data: me } = useMe()
  const popular = useCourses({ sort: 'popular', limit: 8 })
  const fresh = useCourses({ sort: 'newest', limit: 4 })

  return (
    <>
      <Hero />
      <Section title="Browse by category" description="Find the right course for where you want to go.">
        <Categories />
      </Section>
      <Section
        title="Most popular courses"
        description="What learners are taking right now."
        action={
          <Button variant="link" asChild>
            <Link to="/courses">
              View all <ArrowRight />
            </Link>
          </Button>
        }
      >
        <CourseGrid courses={popular.data?.items} loading={popular.isLoading} />
      </Section>
      <section className="border-y border-border bg-surface">
        <div className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <Plans />
        </div>
      </section>
      <Section title="New and noteworthy">
        <CourseGrid courses={fresh.data?.items} loading={fresh.isLoading} count={4} />
      </Section>
      {!me ? (
        <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
          <div className="relative overflow-hidden rounded-2xl bg-primary px-6 py-10 text-on-primary sm:px-10">
            <Backdrop variant="aurora" onDark height="100%" fade={false} />
            <div className="relative flex flex-wrap items-center justify-between gap-6">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight">Ready to start learning?</h2>
                <p className="mt-1 text-white/80">Create a free account to enrol in courses, track progress and earn certificates.</p>
              </div>
              <Button size="lg" variant="secondary" className="border-0 bg-white text-primary hover:bg-white/90" asChild>
                <Link to="/signup">
                  Create an account <ArrowRight />
                </Link>
              </Button>
            </div>
          </div>
        </section>
      ) : null}
    </>
  )
}
