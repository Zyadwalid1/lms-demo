import { Building2, Check, CheckCircle2, Infinity as InfinityIcon, Minus, Plus, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Backdrop } from '@/components/art/backdrops'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { NativeSelect } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { usePlans } from '@/features/catalog/api'
import { useBillingPortal, useMySubscriptions, useSubscribe } from '@/features/commerce/api'
import { useMe } from '@/features/identity/auth'
import { money, shortDate } from '@/lib/format'
import { useNavigate } from '@/lib/router'

const PERSONAL = ['Every course marked “included”, on any device', 'New courses added every month', 'Certificates for everything you finish', 'Cancel any time: access lasts to the end of the period']
const TEAM = ['Everything in Personal, for each seat', 'Compliance dashboard, training matrix and reminders', 'Assign courses to people, teams and sites', 'Company-private courses and branded certificates']

export function PlansPage() {
  const { data: me } = useMe()
  const { data: plans, isLoading } = usePlans()
  const navigate = useNavigate()
  const subscribe = useSubscribe()
  const portal = useBillingPortal()
  const { data: subs } = useMySubscriptions(!!me)
  const personal = plans?.find((p) => p.audience === 'personal')
  const team = plans?.find((p) => p.audience === 'team')
  const live = subs?.find((s) => s.audience === 'personal' && ['active', 'trialing', 'past_due'].includes(s.status))
  const admins = (me?.memberships ?? []).filter((m) => ['owner', 'admin'].includes(m.role))
  const [orgId, setOrgId] = useState('')
  const [seats, setSeats] = useState(10)
  const company = orgId || admins[0]?.org_id || ''
  const fail = (e: unknown) => toast.error((e as Error).message)
  const go = (url: string) => window.location.assign(url)

  return (
    <div className="relative isolate">
      <Backdrop variant="ribbons" height={520} />
      <div className="relative mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:py-16">
        <div className="mx-auto max-w-2xl animate-reveal text-center">
          <Badge tone="primary">Subscriptions</Badge>
          <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-5xl">One plan. Every course you need.</h1>
          <p className="mt-4 text-lg text-muted">Learn as much as you like, or give your whole team the training they need to stay compliant.</p>
        </div>

        <div className="stagger mt-12 grid gap-6 lg:grid-cols-2">
          <Card className="flex flex-col p-7">
            <span className="flex size-11 items-center justify-center rounded-xl bg-primary-soft text-primary-soft-text">
              <InfinityIcon className="size-6" />
            </span>
            <h2 className="mt-5 text-xl font-semibold">Personal Plan</h2>
            <p className="mt-1 text-sm text-muted">For one learner who wants to keep growing.</p>
            <p className="mt-5 text-4xl font-bold tracking-tight tabular">
              {personal ? money(personal.amount_minor, personal.currency, personal.exponent) : isLoading ? <Skeleton className="h-10 w-28" /> : '—'}
              <span className="ml-1 text-base font-normal text-muted">/ {personal?.interval ?? 'month'}</span>
            </p>
            {personal?.trial_days ? <p className="mt-1 text-sm font-medium text-success">{personal.trial_days}-day free trial</p> : null}
            <ul className="mt-6 grid gap-2.5 text-sm">
              {PERSONAL.map((t) => (
                <li key={t} className="flex gap-2.5">
                  <Check className="mt-0.5 size-4 shrink-0 text-success" /> {t}
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-7">
              {live ? (
                <div className="rounded-lg bg-success-soft p-4 text-sm text-success">
                  <p className="inline-flex items-center gap-2 font-semibold">
                    <CheckCircle2 className="size-4" /> You're subscribed{live.status === 'trialing' ? ' (free trial)' : ''}
                  </p>
                  <p className="mt-1 text-success/90">{live.cancel_at_period_end ? 'Ends' : 'Renews'} {live.current_period_end ? shortDate(live.current_period_end) : 'soon'}.</p>
                  <Button variant="secondary" size="sm" className="mt-3" loading={portal.isPending} onClick={() => portal.mutate(undefined, { onSuccess: (r) => go(r.url), onError: fail })}>
                    <Settings2 /> Manage billing
                  </Button>
                </div>
              ) : (
                <Button
                  size="lg"
                  className="w-full"
                  disabled={!personal}
                  loading={subscribe.isPending && subscribe.variables?.orgId === undefined}
                  onClick={() => (me ? personal && subscribe.mutate({ planId: personal.plan_id, currency: personal.currency }, { onSuccess: (r) => go(r.checkout_url), onError: fail }) : navigate('/login?next=/plans'))}
                >
                  {personal?.trial_days ? 'Start free trial' : 'Subscribe'}
                </Button>
              )}
            </div>
          </Card>

          <Card className="relative flex flex-col border-primary/50 p-7 ring-1 ring-primary/30">
            <Badge tone="primary" className="absolute top-6 right-6">
              Best for teams
            </Badge>
            <span className="flex size-11 items-center justify-center rounded-xl bg-primary text-on-primary">
              <Building2 className="size-6" />
            </span>
            <h2 className="mt-5 text-xl font-semibold">Team Plan</h2>
            <p className="mt-1 text-sm text-muted">For companies: training, compliance and reporting in one place.</p>
            <p className="mt-5 text-4xl font-bold tracking-tight tabular">
              {team ? money(team.amount_minor, team.currency, team.exponent) : isLoading ? <Skeleton className="h-10 w-28" /> : '—'}
              <span className="ml-1 text-base font-normal text-muted">/ seat / {team?.interval ?? 'year'}</span>
            </p>
            <ul className="mt-6 grid gap-2.5 text-sm">
              {TEAM.map((t) => (
                <li key={t} className="flex gap-2.5">
                  <Check className="mt-0.5 size-4 shrink-0 text-success" /> {t}
                </li>
              ))}
            </ul>
            <div className="mt-auto pt-7">
              {admins.length && team ? (
                <div className="grid gap-3">
                  {admins.length > 1 ? (
                    <NativeSelect value={company} onChange={(e) => setOrgId(e.target.value)} aria-label="Company">
                      {admins.map((m) => (
                        <option key={m.org_id} value={m.org_id}>
                          {m.name}
                        </option>
                      ))}
                    </NativeSelect>
                  ) : (
                    <p className="text-sm text-muted">
                      For <span className="font-medium text-text">{admins[0]!.name}</span>
                    </p>
                  )}
                  <div className="flex items-center justify-between rounded-lg border border-border p-2">
                    <Button variant="ghost" size="icon-sm" aria-label="Fewer seats" onClick={() => setSeats((n) => Math.max(5, n - 1))} disabled={seats <= 5}>
                      <Minus />
                    </Button>
                    <div className="text-center">
                      <p className="text-lg font-semibold tabular">{seats} seats</p>
                      <p className="text-xs text-muted tabular">{money(team.amount_minor * seats, team.currency, team.exponent)} / {team.interval}</p>
                    </div>
                    <Button variant="ghost" size="icon-sm" aria-label="More seats" onClick={() => setSeats((n) => Math.min(5000, n + 1))}>
                      <Plus />
                    </Button>
                  </div>
                  <Button size="lg" loading={subscribe.isPending && subscribe.variables?.orgId === company} onClick={() => subscribe.mutate({ planId: team.plan_id, currency: team.currency, seats, orgId: company }, { onSuccess: (r) => go(r.checkout_url), onError: fail })}>
                    Buy {seats} seats
                  </Button>
                </div>
              ) : (
                <div className="grid gap-2">
                  <Button size="lg" asChild>
                    <a href="mailto:business@learnhub.example.com?subject=LearnHub%20Team%20Plan">Talk to our team</a>
                  </Button>
                  <p className="text-center text-xs text-muted">Company admins can buy seats here once their company account is set up.</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        <section className="mx-auto mt-16 max-w-3xl">
          <h2 className="text-center text-xl font-semibold tracking-tight">Questions</h2>
          <div className="mt-6 grid gap-3">
            {[
              ['Can I cancel?', 'Yes, any time from Manage billing. You keep access until the end of the period you paid for.'],
              ['What happens to courses I bought separately?', 'They stay yours for life, with or without a subscription.'],
              ['Do certificates expire when my plan ends?', 'No. Certificates you earned stay valid and can always be verified.'],
            ].map(([q, a]) => (
              <details key={q} className="group rounded-lg border border-border bg-surface p-4 open:shadow-sm">
                <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
                  {q}
                  <Plus className="size-4 text-muted transition-transform group-open:rotate-45" />
                </summary>
                <p className="mt-2 text-sm text-muted">{a}</p>
              </details>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
