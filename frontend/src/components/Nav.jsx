import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { authService, USER_UPDATED } from '../services/api'
import { visibleGroups } from './modules'

/**
 * Grouped sidebar, rendered from the shared module registry so a page's sidebar
 * label and its dashboard card cannot drift apart. Sections describe what you do
 * in them rather than naming a category.
 */

const ROLE_LABEL = {
  researcher: 'Researcher',
  startup_founder: 'Startup Founder',
  innovation_manager: 'Innovation Manager',
  admin: 'Administrator',
}

const initials = (name) => (name || '?')
  .split(/\s+/).filter(Boolean).slice(0, 2)
  .map((w) => w[0].toUpperCase()).join('') || '?'

export default function Nav() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [user, setUser] = useState(authService.getCachedUser)

  // keeps the displayed name in sync after a rename (this tab, and other tabs)
  useEffect(() => {
    const refresh = () => setUser(authService.getCachedUser())
    window.addEventListener(USER_UPDATED, refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener(USER_UPDATED, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  const role = user.role || 'researcher'
  const groups = visibleGroups(role)

  const logout = () => { authService.logout(); navigate('/login') }

  return (
    <nav className="side" aria-label="Main navigation">
      <Link to="/dashboard" className="side-brand">
        Innovation<br /><span className="brand-accent">Intelligence</span>
      </Link>

      {groups.map((group) => (
        <div className="side-group" key={group.label}>
          <div className="side-group-label">{group.label}</div>
          {group.links.map(({ to, name, Icon }) => {
            const active = pathname === to
            return (
              <Link key={to} to={to}
                    className={active ? 'navlink active' : 'navlink'}
                    aria-current={active ? 'page' : undefined}>
                {/* each tool's own icon, not the same dot nine times over */}
                <Icon size={17} />
                {name}
              </Link>
            )
          })}
        </div>
      ))}

      <div className="side-foot">
        <div className="side-user">
          <span className="avatar" aria-hidden="true">{initials(user.full_name)}</span>
          <div style={{ minWidth: 0 }}>
            <div className="side-user-name">{user.full_name || 'Signed in'}</div>
            <div className="side-user-role">{ROLE_LABEL[role] || role}</div>
          </div>
        </div>
        <button className="logout" onClick={logout}>Log out</button>
      </div>
    </nav>
  )
}
