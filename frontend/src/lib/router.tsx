/**
 * Link, NavLink and useNavigate with page transitions switched on everywhere.
 * React Router wraps each navigation in document.startViewTransition(), so the browser
 * cross-fades / morphs between the two pages (see the "Motion" section of index.css).
 * Browsers without View Transitions simply switch pages instantly.
 */
import { forwardRef, useCallback } from 'react'
import {
  Link as RRLink,
  type LinkProps,
  NavLink as RRNavLink,
  type NavigateOptions,
  type NavLinkProps,
  type To,
  useNavigate as useRRNavigate,
} from 'react-router-dom'

export const Link = forwardRef<HTMLAnchorElement, LinkProps>(function Link(props, ref) {
  return <RRLink ref={ref} viewTransition {...props} />
})

export const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(function NavLink(props, ref) {
  return <RRNavLink ref={ref} viewTransition {...props} />
})

// eslint-disable-next-line react/only-export-components
export function useNavigate() {
  const navigate = useRRNavigate()
  return useCallback((to: To, options?: NavigateOptions) => navigate(to, { viewTransition: true, ...options }), [navigate])
}
