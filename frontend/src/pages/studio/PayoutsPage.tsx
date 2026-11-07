import { AlertTriangle, BadgeCheck, CheckCircle2, Clock, CreditCard, History, Landmark, Mail, Pencil, Wallet } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardBody, CardHeader } from '@/components/ui/card'
import { CountUp } from '@/components/ui/count-up'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Field, Input } from '@/components/ui/input'
import { EmptyState, ErrorState, PageHeader, StatCard } from '@/components/ui/misc'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, Td, Th, Tr } from '@/components/ui/table'
import { usePayoutAccount, usePayouts, useSetPayoutAccount, useStudioRevenue } from '@/features/studio/api'
import { cn } from '@/lib/cn'
import { money, shortDate } from '@/lib/format'
import { radioKeyDown, radioTabIndex } from '@/lib/radio'

const gbp = (minor: number) => money(Math.round(minor), 'GBP')

// the payouts app's statuses and methods, in plain words
const STATUS: Record<string, { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral'; Icon: typeof Clock }> = {
  pending: { label: 'Awaiting approval', tone: 'warning', Icon: Clock },
  paid: { label: 'Paid', tone: 'success', Icon: CheckCircle2 },
  failed: { label: 'Failed', tone: 'danger', Icon: AlertTriangle },
  held: { label: 'On hold', tone: 'neutral', Icon: Clock },
}
const METHODS = [
  { value: 'stripe', label: 'Stripe Connect', Icon: CreditCard },
  { value: 'paypal', label: 'PayPal', Icon: Mail },
] as const
const methodLabel = (m: string | null | undefined) => METHODS.find((x) => x.value === m)?.label ?? (m || '—')

function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { label: status, tone: 'neutral' as const, Icon: Clock }
  return (
    <Badge tone={s.tone}>
      <s.Icon aria-hidden /> {s.label}
    </Badge>
  )
}

// ---------------------------------------------------------------- payout account
function AccountForm({ method: initialMethod, country: initialCountry, onDone }: { method?: string | null; country?: string | null; onDone: () => void }) {
  const save = useSetPayoutAccount()
  const [method, setMethod] = useState<string>(initialMethod || 'paypal')
  const [email, setEmail] = useState('')
  const [acct, setAcct] = useState('')
  const [country, setCountry] = useState(initialCountry || '')
  const [error, setError] = useState<string>()
  const checked = METHODS.findIndex((m) => m.value === method)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setError(undefined)
    if (country && !/^[A-Za-z]{2}$/.test(country)) return setError('Use the 2-letter country code, for example GB.')
    save.mutate(
      { method, paypal_email: method === 'paypal' ? email.trim() : '', stripe_account_id: method === 'stripe' ? acct.trim() : '', country: country.toUpperCase() },
      {
        onSuccess: () => {
          toast.success('Payout details saved. We check them before your next payout.')
          onDone()
        },
        onError: (err) => setError((err as Error).message),
      },
    )
  }

  return (
    <form onSubmit={submit} className="grid gap-5 p-4">
      <div className="grid gap-2">
        <span id="payout-method" className="text-sm font-medium text-text">
          How should we pay you?
        </span>
        <div role="radiogroup" aria-labelledby="payout-method" className="grid gap-2 sm:grid-cols-2">
          {METHODS.map((m, i) => {
            const on = method === m.value
            return (
              <button
                key={m.value}
                type="button"
                role="radio"
                aria-checked={on}
                tabIndex={radioTabIndex(i, checked)}
                onClick={() => setMethod(m.value)}
                onKeyDown={(e) => radioKeyDown(e, i, METHODS.length, (j) => setMethod(METHODS[j]!.value))}
                className={cn(
                  'flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none',
                  on ? 'border-primary bg-primary-soft text-primary-soft-text' : 'border-border hover:bg-surface-2',
                )}
              >
                <m.Icon className="size-4 shrink-0" aria-hidden />
                <span className="font-medium">{m.label}</span>
              </button>
            )
          })}
        </div>
      </div>
      {method === 'paypal' ? (
        <Field label="PayPal email" hint="The email address of your PayPal account.">
          {(p) => <Input {...p} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
      ) : (
        <Field label="Stripe account ID" hint="Starts with acct_. You'll find it in your Stripe dashboard.">
          {(p) => <Input {...p} required pattern="acct_[A-Za-z0-9]+" placeholder="acct_…" value={acct} onChange={(e) => setAcct(e.target.value)} />}
        </Field>
      )}
      <Field label="Country" hint="2-letter code, for example GB.">
        {(p) => <Input {...p} maxLength={2} autoComplete="country" className="w-24 uppercase" value={country} onChange={(e) => setCountry(e.target.value)} />}
      </Field>
      {error ? (
        <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <p className="text-[13px] text-muted">Changing these details means we check them again before paying you.</p>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={save.isPending}>
          Save details
        </Button>
      </div>
    </form>
  )
}

function AccountCard() {
  const q = usePayoutAccount()
  const [open, setOpen] = useState(false)
  const a = q.data
  return (
    <Card className="min-w-0">
      <CardHeader
        title="Payout method"
        description="Where your earnings are sent"
        action={
          a?.configured ? (
            <Button size="sm" variant="secondary" onClick={() => setOpen(true)}>
              <Pencil aria-hidden /> Edit
            </Button>
          ) : null
        }
      />
      <CardBody>
        {q.isPending ? (
          <Skeleton className="h-20 rounded-lg" />
        ) : q.isError || !a ? (
          <ErrorState onRetry={() => void q.refetch()} />
        ) : !a.configured ? (
          <EmptyState
            className="py-6"
            icon={<Landmark />}
            title="No payout method yet"
            body="Add one so we can send you what you earn."
            action={<Button onClick={() => setOpen(true)}>Add payout method</Button>}
          />
        ) : (
          <div className="animate-reveal flex items-start gap-3 rounded-lg border border-border p-4">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary-soft text-primary-soft-text">
              {a.method === 'stripe' ? <CreditCard className="size-5" aria-hidden /> : <Mail className="size-5" aria-hidden />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{methodLabel(a.method)}</p>
              <p className="truncate text-sm text-muted">
                {a.method === 'paypal' ? a.paypal_email : a.stripe_connected ? 'Stripe account connected' : 'Not connected yet'}
                {a.country ? ` · ${a.country}` : ''}
              </p>
              <div className="mt-2">
                {a.verified ? (
                  <Badge tone="success">
                    <BadgeCheck aria-hidden /> Checked
                  </Badge>
                ) : (
                  <Badge tone="warning">
                    <Clock aria-hidden /> Waiting to be checked
                  </Badge>
                )}
              </div>
            </div>
          </div>
        )}
      </CardBody>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent side="right" title={a?.configured ? 'Edit payout method' : 'Add payout method'} className="w-[min(440px,100vw)]">
          {open ? <AccountForm method={a?.method} country={a?.country} onDone={() => setOpen(false)} /> : null}
        </DialogContent>
      </Dialog>
    </Card>
  )
}

// ---------------------------------------------------------------- history
function PayoutHistory() {
  const q = usePayouts()
  return (
    <Card className="min-w-0">
      <CardHeader title="Payout history" description="Each payout covers your earnings up to the end of its period" />
      <CardBody>
        {q.isPending ? (
          <div className="grid gap-2" aria-busy="true" aria-label="Loading payouts">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        ) : q.isError ? (
          <ErrorState onRetry={() => void q.refetch()} />
        ) : q.data.length === 0 ? (
          <EmptyState className="py-8" icon={<History />} title="No payouts yet" body="Your first payout appears here once you have earnings ready to send." />
        ) : (
          <div className="animate-reveal">
            {/* phones: one card per payout */}
            <ul className="stagger grid gap-3 sm:hidden">
              {q.data.map((p) => (
                <li key={p.id} className="rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold tabular">{gbp(p.amount_gbp_minor)}</p>
                      <p className="text-xs text-muted">Up to {shortDate(p.period_end)}</p>
                    </div>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    {methodLabel(p.method)}
                    {p.paid_at ? ` · paid ${shortDate(p.paid_at)}` : ''}
                  </p>
                  {p.failure_reason ? <p className="mt-1 text-xs text-danger">{p.failure_reason}</p> : null}
                </li>
              ))}
            </ul>
            <div className="max-sm:hidden">
              <Table>
                <thead>
                  <tr>
                    <Th>Period ends</Th>
                    <Th className="text-right">Amount</Th>
                    <Th>Method</Th>
                    <Th>Status</Th>
                    <Th>Paid</Th>
                  </tr>
                </thead>
                <tbody className="stagger">
                  {q.data.map((p) => (
                    <Tr key={p.id}>
                      <Td>{shortDate(p.period_end)}</Td>
                      <Td className="text-right font-medium tabular">{gbp(p.amount_gbp_minor)}</Td>
                      <Td>{methodLabel(p.method)}</Td>
                      <Td>
                        <StatusBadge status={p.status} />
                        {p.failure_reason ? <p className="mt-1 text-xs text-danger">{p.failure_reason}</p> : null}
                      </Td>
                      <Td className="text-muted">{p.paid_at ? shortDate(p.paid_at) : '—'}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

export function PayoutsPage() {
  const rev = useStudioRevenue()
  const b = rev.data?.balance
  const fmt = (n: number) => gbp(n)
  return (
    <div>
      <PageHeader title="Payouts" description="Your balance, where we send your earnings, and what has been paid." />
      <div className="grid gap-6">
        {rev.isPending ? (
          <div className="grid grid-cols-1 gap-4 min-[420px]:grid-cols-3" aria-busy="true" aria-label="Loading balance">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[118px] rounded-xl" />
            ))}
          </div>
        ) : rev.isError || !b ? (
          <Card>
            <ErrorState onRetry={() => void rev.refetch()} />
          </Card>
        ) : (
          <ul className="animate-reveal stagger grid grid-cols-1 gap-4 min-[420px]:grid-cols-3">
            <li className="min-w-0">
              <StatCard label="Available for payout" tone="success" icon={<Wallet />} value={<CountUp value={b.available} format={fmt} />} hint="Goes out with your next payout" />
            </li>
            <li className="min-w-0">
              <StatCard label="Pending" tone="warning" icon={<Clock />} value={<CountUp value={b.pending} format={fmt} />} hint="Inside the refund window" />
            </li>
            <li className="min-w-0">
              <StatCard label="Paid out" tone="info" icon={<CheckCircle2 />} value={<CountUp value={b.paid} format={fmt} />} hint="All time" />
            </li>
          </ul>
        )}
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <PayoutHistory />
          <div className="grid content-start gap-6">
            <AccountCard />
            <Card>
              <CardHeader title="How payouts work" />
              <CardBody>
                <ul className="grid gap-2.5 text-sm text-muted">
                  {[
                    'Earnings become available once the refund window has passed.',
                    'Available earnings are gathered into a payout for each period.',
                    'Each payout is approved before it is sent to your payout method.',
                  ].map((t) => (
                    <li key={t} className="flex gap-2">
                      <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                      {t}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}
