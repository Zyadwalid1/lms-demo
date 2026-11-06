import type { ReactNode } from 'react'

import { AuthBand, AuthShowcase } from '@/components/art/auth-showcase'
import { Logo } from '@/components/ui/logo'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { Link } from '@/lib/router'

/** Sign-in pages: a calm, focused form on the left; the product showcase on the right
 * (desktop). On phones a slim strip of the same artwork sits above the form. */
export function AuthShell({ title, subtitle, children }: { title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid min-h-dvh bg-surface lg:grid-cols-[minmax(0,1fr)_minmax(0,620px)]">
      <div className="relative flex flex-col">
        <div aria-hidden className="h-24 overflow-hidden lg:hidden">
          <AuthBand />
        </div>
        {/* form side: a dot grid and soft violet light in the corners, never a flat colour */}
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,var(--border-strong)_1px,transparent_0)] [background-size:22px_22px] [mask-image:radial-gradient(60%_55%_at_0%_0%,black,transparent)]" />
          <div className="absolute -top-40 -left-40 size-[520px] rounded-full bg-[radial-gradient(closest-side,var(--primary-soft),transparent)] opacity-90" />
          <div className="absolute -right-32 -bottom-48 size-[480px] rounded-full bg-[radial-gradient(closest-side,var(--primary-soft),transparent)] opacity-70" />
        </div>
        <div className="relative flex items-center justify-between px-5 pt-5 sm:px-10 sm:pt-8">
          <Link to="/" aria-label="LearnHub home">
            <Logo />
          </Link>
          <ThemeToggle />
        </div>
        <main id="main" className="relative mx-auto flex w-full max-w-[400px] flex-1 animate-rise flex-col justify-center px-5 py-10 sm:px-0">
          <h1 className="text-[30px] leading-tight font-bold tracking-tight">{title}</h1>
          {subtitle ? <p className="mt-2 text-[15px] text-muted">{subtitle}</p> : null}
          <div className="mt-8">{children}</div>
        </main>
        <p className="relative px-5 pb-6 text-center text-xs text-subtle sm:px-10">Protected by secure sign-in. We never share your email.</p>
      </div>
      <aside className="sticky top-0 hidden h-dvh lg:block">
        <AuthShowcase />
      </aside>
    </div>
  )
}
