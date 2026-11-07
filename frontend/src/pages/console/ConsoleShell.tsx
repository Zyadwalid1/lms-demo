import { Award, BadgePercent, BarChart3, BookOpen, Building2, CreditCard, GraduationCap, History, LayoutDashboard, MessageSquare, Percent, Receipt, Settings, Stamp, Star, Tags, Users, Wallet } from 'lucide-react'

import { type NavSection, WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { ConsoleSearch } from '@/features/console/ConsoleSearch'
import { useNavCounts } from '@/features/console/api'

type CountKey = 'approvals' | 'tickets_open' | 'reports_open' | 'payout_requests'

/** A live count in the sidebar (hidden at zero). */
function NavCount({ k, label }: { k: CountKey; label: string }) {
  const { data } = useNavCounts()
  const n = data?.[k] ?? 0
  if (!n) return null
  return (
    <span className="ml-auto inline-flex min-w-5 animate-pop-in items-center justify-center rounded-full bg-primary px-1.5 text-[11px] font-semibold text-on-primary tabular" aria-label={`${n} ${label}`}>
      {n > 99 ? '99+' : n}
    </span>
  )
}

// Order of mockups 15/26 (brief, Navigation). Currencies live inside Pricing, notification
// templates inside Communications.
const consoleNav: NavSection[] = [
  {
    items: [
      { to: '/console', label: 'Dashboard', Icon: LayoutDashboard, end: true },
      { to: '/console/courses', label: 'Courses', Icon: BookOpen },
      { to: '/console/instructors', label: 'Instructors', Icon: GraduationCap },
      { to: '/console/students', label: 'Students', Icon: Users },
    ],
  },
  {
    title: 'Money',
    items: [
      { to: '/console/sales', label: 'Sales & orders', Icon: Receipt },
      { to: '/console/subscriptions', label: 'Subscriptions', Icon: CreditCard },
      { to: '/console/pricing', label: 'Pricing', Icon: Tags },
      { to: '/console/promotions', label: 'Promotions', Icon: BadgePercent },
      { to: '/console/commissions', label: 'Commissions', Icon: Percent },
      { to: '/console/payouts', label: 'Payouts', Icon: Wallet, badge: <NavCount k="payout_requests" label="payout requests waiting" /> },
      { to: '/console/reports', label: 'Reports', Icon: BarChart3 },
    ],
  },
  {
    title: 'Quality',
    items: [
      { to: '/console/approvals', label: 'Approvals', Icon: Stamp, badge: <NavCount k="approvals" label="items waiting for approval" /> },
      { to: '/console/reviews', label: 'Reviews', Icon: Star, badge: <NavCount k="reports_open" label="open reports" /> },
      { to: '/console/communications', label: 'Communications', Icon: MessageSquare, badge: <NavCount k="tickets_open" label="open tickets" /> },
      { to: '/console/certificates', label: 'Certificates', Icon: Award },
    ],
  },
  {
    title: 'Platform',
    items: [
      { to: '/console/companies', label: 'Companies', Icon: Building2 },
      { to: '/console/settings', label: 'Settings', Icon: Settings },
      { to: '/console/audit', label: 'Audit log', Icon: History },
    ],
  },
]

/** The admin console frame: navy sidebar (drawer on phones), circuit artwork by default,
 * the global search in the header. Loaded only by staff (its own chunk). */
export function ConsoleShell() {
  return <WorkspaceLayout area="Admin" sections={consoleNav} art="circuit" header={<ConsoleSearch />} />
}
