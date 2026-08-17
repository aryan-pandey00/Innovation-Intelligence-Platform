import { Link, useLocation, useNavigate } from 'react-router-dom'
import { authService } from '../services/api'
import { useSession } from '../services/session'
import { roleLabel } from '../roles'
import { useUnreadAlerts, useWaitingResets } from '../hooks'
import { moduleForPath, visibleGroups } from './modules'

const initials = (name) => (name || '?')
  .split(/\s+/).filter(Boolean).slice(0, 2)
  .map((w) => w[0].toUpperCase()).join('') || '?'

export default function Nav() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, role } = useSession()

  const groups = visibleGroups(role)
  const unread = useUnreadAlerts()
  const waitingResets = useWaitingResets(role)

  const here = moduleForPath(pathname)

  const logout = () => { authService.logout(); navigate('/') }

  return (
    <nav className="side" aria-label="Main navigation">
      <Link to="/dashboard" className="side-brand">
        Innovation<br /><span className="brand-accent">Intelligence</span>
      </Link>

      {groups.map((group) => (
        <div className="side-group" key={group.label}>
          <div className="side-group-label">{group.label}</div>
          {group.links.map(({ key, to, name, Icon }) => {
            const active = here?.key === key
            const badge =
              key === 'notifications' ? { n: unread, label: `${unread} unread` }
              : key === 'resets' ? { n: waitingResets,
                                     label: `${waitingResets} waiting to be let back in` }
              : null
            return (
              <Link key={to} to={to}
                    className={active ? 'navlink active' : 'navlink'}
                    aria-current={active ? 'page' : undefined}>
                <Icon size={17} />
                {name}
                {badge && badge.n > 0 && (
                  <span className="nav-badge" aria-label={badge.label}>
                    {badge.n > 9 ? '9+' : badge.n}
                  </span>
                )}
              </Link>
            )
          })}
        </div>
      ))}

      <div className="side-foot">
        <div className="side-user">
          <span className="avatar" aria-hidden="true">{initials(user.full_name)}</span>
          <div style={{ minWidth: 0 }}>
            <div className="side-user-name">{user?.full_name || 'Signed in'}</div>
            <div className="side-user-role">{roleLabel(role)}</div>
          </div>
        </div>
        <button className="logout" onClick={logout}>Log out</button>
      </div>
    </nav>
  )
}
