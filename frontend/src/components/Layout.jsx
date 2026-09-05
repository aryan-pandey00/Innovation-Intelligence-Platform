import { Suspense, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Loading from './Loading'
import Nav from './Nav'
import { useSession } from '../services/session'
import { useRevealOnScroll } from './ui/motion'

export default function Layout() {
  const main = useRef(null)
  const { isDemo } = useSession()
  useRevealOnScroll(main, useLocation().pathname)

  return (
    <div className="shell">
      <Nav />
      <main className="shell-main" ref={main}>
        {/* Said up front, because the alternative is finding out by clicking Save. */}
        {isDemo && (
          <div className="demo-banner" role="status">
            <strong>Read-only demo.</strong> Explore every page, chart and report.
            Nothing can be added, edited or deleted — register your own account for that.
          </div>
        )}
        <Suspense fallback={<Loading message="Loading…" />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
