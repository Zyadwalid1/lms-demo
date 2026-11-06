import { useMutation, useQuery } from '@tanstack/react-query'

import { api, unwrap } from '@/api/client'
import { API_BASE_URL } from '@/lib/env'
import { currentOrgId } from '@/lib/workspace'

export type Dashboard = Awaited<ReturnType<typeof fetchDashboard>>
export type RequirementSummary = Awaited<ReturnType<typeof fetchSummary>>[number]
const fetchDashboard = () => unwrap(api.GET('/api/v1/compliance/dashboard'))
const fetchSummary = () => unwrap(api.GET('/api/v1/compliance/summary'))

export function useDashboard() {
  return useQuery({ queryKey: ['compliance', 'dashboard', currentOrgId()], queryFn: fetchDashboard })
}

export function useSummary() {
  return useQuery({ queryKey: ['compliance', 'summary', currentOrgId()], queryFn: fetchSummary })
}

export function useRemind() {
  return useMutation({
    mutationFn: (statusId: string) => unwrap(api.POST('/api/v1/compliance/statuses/{status_id}/remind', { params: { path: { status_id: statusId } } })),
  })
}

/** CSV export needs the X-Org-Id header, so it is fetched and saved rather than linked. */
export async function downloadExport() {
  const res = await fetch(`${API_BASE_URL}/api/v1/compliance/export.csv`, { credentials: 'include', headers: { 'X-Org-Id': currentOrgId() ?? '' } })
  if (!res.ok) throw new Error('The export could not be created.')
  const url = URL.createObjectURL(await res.blob())
  const a = Object.assign(document.createElement('a'), { href: url, download: `compliance-${new Date().toISOString().slice(0, 10)}.csv` })
  a.click()
  URL.revokeObjectURL(url)
}

export const STATUS = {
  compliant: { label: 'Compliant', tone: 'success', color: 'var(--success)' },
  expiring_soon: { label: 'Expiring soon', tone: 'warning', color: 'var(--chart-3)' },
  in_progress: { label: 'In progress', tone: 'info', color: 'var(--chart-5)' },
  not_started: { label: 'Not started', tone: 'neutral', color: 'var(--border-strong)' },
  overdue: { label: 'Overdue', tone: 'danger', color: 'var(--chart-4)' },
  expired: { label: 'Expired', tone: 'danger', color: 'var(--danger)' },
  exempt: { label: 'Exempt', tone: 'outline', color: 'var(--text-subtle)' },
} as const
export type StatusKey = keyof typeof STATUS

/** The learner's required training in one company (each company is asked separately). */
export function useMyRequirements(orgId: string) {
  return useQuery({
    queryKey: ['my-requirements', orgId],
    queryFn: () => unwrap(api.GET('/api/v1/compliance/my', { headers: { 'X-Org-Id': orgId } })),
  })
}
