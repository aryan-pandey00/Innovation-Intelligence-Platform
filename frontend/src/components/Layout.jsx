import { Suspense, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Loading from './Loading'
import Nav from './Nav'
import { useRevealOnScroll } from './ui/motion'

export default function Layout() {
  const main = useRef(null)
  useRevealOnScroll(main, useLocation().pathname)

  return (
    <div className="shell">
      <Nav />
      <main className="shell-main" ref={main}>
        <Suspense fallback={<Loading message="Loading…" />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
