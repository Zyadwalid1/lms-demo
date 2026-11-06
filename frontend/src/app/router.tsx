import { BarChart3, BookOpen, Building2, ClipboardCheck, CreditCard, DollarSign, FileBarChart, GraduationCap, LayoutDashboard, LifeBuoy, MessageSquare, Network, ScrollText, Settings, ShieldCheck, Star, UserPlus, Users, Wallet } from 'lucide-react'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Outlet } from 'react-router-dom'

import { LearnerLayout } from '@/components/layout/LearnerLayout'
import { PublicLayout } from '@/components/layout/PublicLayout'
import { type NavSection, WorkspaceLayout } from '@/components/layout/WorkspaceLayout'
import { ComingSoon, NotFoundPage } from '@/pages/StatusPages'

import { PageSpinner, RequireAuth, RequireManager, RequireRole } from './guards'

// Every page is its own chunk: visitors download the marketplace only.
const named = <K extends string>(load: () => Promise<Record<K, React.ComponentType>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })))
const HomePage = named(() => import('@/pages/HomePage'), 'HomePage')
const CoursesPage = named(() => import('@/pages/CoursesPage'), 'CoursesPage')
const CoursePage = named(() => import('@/pages/CoursePage'), 'CoursePage')
const MyLearningPage = named(() => import('@/pages/MyLearningPage'), 'MyLearningPage')
const DesignPage = named(() => import('@/pages/DesignPage'), 'DesignPage')
const LoginPage = named(() => import('@/pages/auth/LoginPage'), 'LoginPage')
const SignupPage = named(() => import('@/pages/auth/SignupPage'), 'SignupPage')
const VerifyEmailPage = named(() => import('@/pages/auth/VerifyEmailPage'), 'VerifyEmailPage')
const CartPage = named(() => import('@/pages/shop/CartPage'), 'CartPage')
const CheckoutSuccessPage = named(() => import('@/pages/shop/CheckoutSuccessPage'), 'CheckoutSuccessPage')
const PlansPage = named(() => import('@/pages/shop/PlansPage'), 'PlansPage')
const WishlistPage = named(() => import('@/pages/shop/WishlistPage'), 'WishlistPage')
const OrdersPage = named(() => import('@/pages/shop/OrdersPage'), 'OrdersPage')
const PlayerPage = named(() => import('@/pages/learn/PlayerPage'), 'PlayerPage')
const CertificatesPage = named(() => import('@/pages/learner/CertificatesPage'), 'CertificatesPage')
const AchievementsPage = named(() => import('@/pages/learner/AchievementsPage'), 'AchievementsPage')
const RequiredTrainingPage = named(() => import('@/pages/learner/RequiredTrainingPage'), 'RequiredTrainingPage')
const NotificationsPage = named(() => import('@/pages/learner/NotificationsPage'), 'NotificationsPage')
const AccountPage = named(() => import('@/pages/learner/AccountPage'), 'AccountPage')
const SupportPage = named(() => import('@/pages/learner/SupportPages'), 'SupportPage')
const TicketPage = named(() => import('@/pages/learner/SupportPages'), 'TicketPage')
const VerifyPage = named(() => import('@/pages/VerifyPage'), 'VerifyPage')
const ComplianceDashboard = named(() => import('@/pages/business/ComplianceDashboard'), 'ComplianceDashboard')

const page = (el: ReactNode) => <Suspense fallback={<PageSpinner />}>{el}</Suspense>
const soon = (title: string, milestone: string) => <ComingSoon title={title} milestone={milestone} />

const businessNav: NavSection[] = [
  { items: [{ to: '/business', label: 'Overview', Icon: LayoutDashboard, end: true }] },
  {
    title: 'Compliance',
    items: [
      { to: '/business/matrix', label: 'Training matrix', Icon: ClipboardCheck },
      { to: '/business/requirements', label: 'Requirements', Icon: ShieldCheck },
      { to: '/business/reports', label: 'Reports', Icon: FileBarChart },
    ],
  },
  {
    title: 'People',
    items: [
      { to: '/business/people', label: 'People', Icon: Users },
      { to: '/business/units', label: 'Locations & teams', Icon: Network },
      { to: '/business/invites', label: 'Invitations', Icon: UserPlus },
    ],
  },
  {
    title: 'Learning',
    items: [
      { to: '/business/library', label: 'Course library', Icon: BookOpen },
      { to: '/business/assign', label: 'Assign training', Icon: GraduationCap },
    ],
  },
  {
    title: 'Company',
    items: [
      { to: '/business/billing', label: 'Billing', Icon: CreditCard },
      { to: '/business/settings', label: 'Settings', Icon: Building2 },
    ],
  },
]

const studioNav: NavSection[] = [
  { items: [{ to: '/studio', label: 'Dashboard', Icon: LayoutDashboard, end: true }, { to: '/studio/courses', label: 'My courses', Icon: BookOpen }] },
  { title: 'Learners', items: [{ to: '/studio/students', label: 'Students', Icon: Users }, { to: '/studio/grading', label: 'Assignments', Icon: ClipboardCheck }, { to: '/studio/questions', label: 'Q&A and reviews', Icon: MessageSquare }] },
  { title: 'Money', items: [{ to: '/studio/revenue', label: 'Sales & earnings', Icon: DollarSign }, { to: '/studio/payouts', label: 'Payouts', Icon: Wallet }] },
]

const consoleNav: NavSection[] = [
  { items: [{ to: '/console', label: 'Overview', Icon: LayoutDashboard, end: true }, { to: '/console/reports', label: 'Reports', Icon: BarChart3 }] },
  { title: 'Catalogue', items: [{ to: '/console/review', label: 'Course review', Icon: ClipboardCheck }, { to: '/console/instructors', label: 'Instructors', Icon: GraduationCap }] },
  { title: 'Money', items: [{ to: '/console/orders', label: 'Orders & refunds', Icon: CreditCard }, { to: '/console/payouts', label: 'Payouts', Icon: Wallet }, { to: '/console/currencies', label: 'Currencies', Icon: DollarSign }] },
  { title: 'People', items: [{ to: '/console/users', label: 'Users', Icon: Users }, { to: '/console/tickets', label: 'Support', Icon: LifeBuoy }, { to: '/console/reviews', label: 'Reviews', Icon: Star }] },
  { title: 'System', items: [{ to: '/console/audit', label: 'Audit log', Icon: ScrollText }, { to: '/console/settings', label: 'Settings', Icon: Settings }] },
]

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      { path: '/', element: page(<HomePage />) },
      { path: '/courses', element: page(<CoursesPage />) },
      { path: '/courses/:slug', element: page(<CoursePage />) },
      { path: '/design', element: page(<DesignPage />) },
      { path: '/plans', element: page(<PlansPage />) },
      { path: '/verify', element: page(<VerifyPage />) },
      { path: '/verify/:code', element: page(<VerifyPage />) },
      { path: '/cart', element: <RequireAuth>{page(<CartPage />)}</RequireAuth> },
      { path: '/checkout/success', element: <RequireAuth>{page(<CheckoutSuccessPage />)}</RequireAuth> },
      {
        element: (
          <RequireAuth>
            <LearnerLayout />
          </RequireAuth>
        ),
        children: [
          { path: '/learn', element: page(<MyLearningPage />) },
          { path: '/learn/certificates', element: page(<CertificatesPage />), handle: { art: 'guilloche' } },
          { path: '/learn/achievements', element: page(<AchievementsPage />), handle: { art: 'honeycomb' } },
          { path: '/learn/required', element: page(<RequiredTrainingPage />), handle: { art: 'checklist' } },
          { path: '/notifications', element: page(<NotificationsPage />), handle: { art: 'signal' } },
          { path: '/wishlist', element: page(<WishlistPage />) },
          { path: '/account/orders', element: page(<OrdersPage />), handle: { art: 'ribbons' } },
          { path: '/account', element: page(<AccountPage />), handle: { art: 'dials' } },
          { path: '/support', element: page(<SupportPage />), handle: { art: 'bubbles' } },
          { path: '/support/:id', element: page(<TicketPage />), handle: { art: 'bubbles' } },
        ],
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  // the player is full-screen: its own header, no site footer
  { path: '/learn/:slug/*', element: <RequireAuth>{page(<PlayerPage />)}</RequireAuth> },
  { path: '/login', element: page(<LoginPage />) },
  { path: '/signup', element: page(<SignupPage />) },
  { path: '/account/verify-email/:key', element: page(<VerifyEmailPage />) },
  {
    path: '/business',
    element: (
      <RequireAuth>
        <RequireManager>
          <WorkspaceLayout area="Business" sections={businessNav} art="contours" />
        </RequireManager>
      </RequireAuth>
    ),
    children: [
      { index: true, element: page(<ComplianceDashboard />) },
      { path: '*', element: soon('This business screen', 'M3 (business)') },
    ],
  },
  {
    path: '/studio',
    element: (
      <RequireAuth>
        <RequireRole allowed="instructor">
          <WorkspaceLayout area="Instructor" sections={studioNav} art="blueprint" />
        </RequireRole>
      </RequireAuth>
    ),
    children: [{ path: '*', element: soon('Instructor studio', 'M4 (studio)') }, { index: true, element: soon('Instructor dashboard', 'M4 (studio)') }],
  },
  {
    path: '/console',
    element: (
      <RequireAuth>
        <RequireRole allowed="staff">
          <WorkspaceLayout area="Admin" sections={consoleNav} art="circuit" />
        </RequireRole>
      </RequireAuth>
    ),
    children: [{ path: '*', element: soon('Admin console', 'M5 (console)') }, { index: true, element: soon('Admin overview', 'M5 (console)') }],
  },
  { path: '*', element: <Outlet /> },
])
