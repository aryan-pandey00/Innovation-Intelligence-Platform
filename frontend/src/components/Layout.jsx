import { Outlet } from 'react-router-dom'
import Nav from './Nav'

export default function Layout() {
  return (
    <div className="shell">
      <Nav />
      <main className="shell-main">
        <Outlet />
      </main>
    </div>
  )
}
