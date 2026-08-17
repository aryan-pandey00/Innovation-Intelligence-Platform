import { Link, Outlet, useLocation } from 'react-router-dom'

import { PageHeader } from '../components/ui'

const TABS = [
  { to: '/admin', label: 'Accounts', end: true },
  { to: '/admin/funding', label: 'Funding Catalogue' },
  { to: '/admin/sources', label: 'Data & Sources' },
]

export default function AdminPanel() {
  const { pathname } = useLocation()

  return (
    <div className="dashboard">
      <PageHeader trail="Account" title="Platform Administration">
        Everything set once that applies to everyone — who may use the platform, and
        what it runs on.
      </PageHeader>

      <nav className="tabs" aria-label="Admin sections">
        {TABS.map(({ to, label, end }) => {
          const active = end ? pathname === to : pathname.startsWith(to)
          return (
            <Link key={to} to={to} className={active ? 'tab active' : 'tab'}
                  aria-current={active ? 'page' : undefined}>
              {label}
            </Link>
          )
        })}
      </nav>

      <Outlet />
    </div>
  )
}
