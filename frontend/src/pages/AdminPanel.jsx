import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminService, authService, extractErrorMessage } from '../services/api'
import ProfileDetail from '../components/ProfileDetail'
import { PageHeader, Card, StatCard, StatGrid } from '../components/ui'

const SUPER_ADMIN_EMAIL = 'aryan@admin.com'

const ROLES = [
  { value: 'researcher', label: 'Researcher' },
  { value: 'startup_founder', label: 'Startup Founder' },
  { value: 'innovation_manager', label: 'Innovation Manager' },
  { value: 'admin', label: 'Administrator' },
]
const ROLES_FOR_ADMIN = ROLES.filter((r) => r.value !== 'admin')
const ROLE_LABEL = Object.fromEntries(ROLES.map((r) => [r.value, r.label]))
const ROLE_ORDER = Object.fromEntries(ROLES.map((r, i) => [r.value, i]))

// The API returns rows in insertion order, which reads as random. Group by role,
// then alphabetically, so the same user is always in the same place.
const sortUsers = (rows) => [...rows].sort((a, b) =>
  (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9)
  || (a.full_name || '').localeCompare(b.full_name || ''))

export default function AdminPanel() {
  const [users, setUsers] = useState([])
  const [me, setMe] = useState(null)
  const [selected, setSelected] = useState(null)
  const [profileMsg, setProfileMsg] = useState('')
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const detailRef = useRef(null)
  const navigate = useNavigate()

  const loadUsers = () => {
    adminService.listUsers()
      .then((res) => setUsers(sortUsers(res.data)))
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else setError('Could not load the user list.')
      })
  }

  useEffect(() => {
    authService.getMe().then((res) => setMe(res.data)).catch(() => {})
    loadUsers()
  }, [])   // eslint-disable-line

  const isSuperAdmin = me?.email === SUPER_ADMIN_EMAIL

  // Deleting a user asks for confirmation; changing their permissions did not,
  // even though a stray scroll over a <select> was enough to grant admin rights.
  const changeRole = async (user, role) => {
    if (role === user.role) return
    if (!window.confirm(
      `Change ${user.full_name} from ${ROLE_LABEL[user.role] || user.role} `
      + `to ${ROLE_LABEL[role] || role}? This changes what they can access.`
    )) {
      loadUsers()          // reset the select back to its stored value
      return
    }
    try {
      await adminService.changeRole(user.id, role)
      loadUsers()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not change that role.'))
      loadUsers()
    }
  }

  const deleteUser = async (u) => {
    if (!window.confirm(`Delete ${u.full_name} (${u.email}) permanently? This cannot be undone.`)) return
    try {
      await adminService.deleteUser(u.id)
      if (selected?.user.id === u.id) setSelected(null)
      loadUsers()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not delete that user.'))
    }
  }

  // The panel renders below a table that can be taller than the viewport, so
  // opening it from a lower row used to look like nothing had happened.
  const revealDetail = () => {
    requestAnimationFrame(() => {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }

  const viewProfile = async (u) => {
    if (selected?.user.id === u.id) { setSelected(null); return }   // click again to close
    setSelected(null); setProfileMsg(`Loading ${u.full_name}'s portfolio…`)
    try {
      const res = await adminService.getUserProfile(u.id)
      setSelected({ user: u, profile: res.data })
      setProfileMsg(''); revealDetail()
    } catch (err) {
      if (err.response?.status === 404) {
        setSelected({ user: u, profile: null })
        setProfileMsg(''); revealDetail()
      } else {
        setProfileMsg('Could not load that portfolio.')
      }
    }
  }

  const counts = users.reduce((acc, u) => {
    acc[u.role] = (acc[u.role] || 0) + 1
    return acc
  }, {})

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return users
    return users.filter((u) =>
      (u.full_name || '').toLowerCase().includes(q)
      || (u.email || '').toLowerCase().includes(q)
      || (ROLE_LABEL[u.role] || '').toLowerCase().includes(q))
  }, [users, filter])

  return (
    <div className="dashboard">
      <PageHeader trail="Account" title="Platform Administration">
        Everyone with an account, what they can access, and the portfolio each of
        them has built.
      </PageHeader>

      {error && <div className="error">{error}</div>}

      <StatGrid>
        <StatCard value={users.length} label="Accounts" />
        <StatCard value={counts.researcher || 0} label="Researchers" />
        <StatCard value={counts.startup_founder || 0} label="Startup founders" />
        <StatCard value={counts.innovation_manager || 0} label="Innovation managers" />
        <StatCard value={counts.admin || 0} label="Administrators" />
      </StatGrid>

      <Card
        title="Accounts"
        sub={filter
          ? `${shown.length} of ${users.length} matching "${filter}"`
          : 'Grouped by role, then name'}
        aside={(
          <input
            className="table-search"
            type="search"
            placeholder="Search name, email or role"
            aria-label="Search accounts"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        )}
      >
        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr><th>Name</th><th>Email</th><th>Role</th><th colSpan={2}>Actions</th></tr>
            </thead>
            <tbody>
              {shown.map((u) => {
                const isSelf = me && u.id === me.id
                const isProtected = u.role === 'admin' && !isSuperAdmin
                const availableRoles = isSuperAdmin ? ROLES : ROLES_FOR_ADMIN
                const isOpen = selected?.user.id === u.id

                const cls = [isProtected && 'row-protected', isOpen && 'row-open']
                  .filter(Boolean).join(' ')

                return (
                  <tr key={u.id} className={cls}>
                    <td>
                      {u.full_name}
                      {u.email === SUPER_ADMIN_EMAIL && <span className="super-tag">Super</span>}
                    </td>
                    <td>{u.email}</td>
                    <td>
                      {isProtected ? (
                        <span className="role-badge role-locked">{ROLE_LABEL[u.role]}</span>
                      ) : (
                        <select
                          className="role-select"
                          value={u.role}
                          disabled={isSelf}
                          aria-label={`Role for ${u.full_name}`}
                          onChange={(e) => changeRole(u, e.target.value)}
                        >
                          {availableRoles.map((r) => {
                            const orig = u.original_role || u.role
                            const isBase = (role) => role === 'researcher' || role === 'startup_founder'
                            const isInvalidBaseChange = isBase(r.value) && isBase(orig) && r.value !== orig
                            return (
                              <option key={r.value} value={r.value} disabled={isInvalidBaseChange}>
                                {r.label}
                              </option>
                            )
                          })}
                        </select>
                      )}
                    </td>
                    <td>
                      <button className="mini-view" onClick={() => viewProfile(u)}>
                        {isOpen ? 'Hide portfolio' : 'View portfolio'}
                      </button>
                    </td>
                    <td>
                      {isProtected ? (
                        <span className="cell-note">Protected</span>
                      ) : (
                        <button className="mini-del" disabled={isSelf} onClick={() => deleteUser(u)}>
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
              {shown.length === 0 && (
                <tr><td colSpan={5} className="cell-note">No account matches that search.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {me && (
          <p className="table-foot">
            {isSuperAdmin
              ? 'As Super-Admin you can change or remove any account, including other administrators.'
              : 'You can manage researchers, founders and managers. Administrator accounts are locked to the Super-Admin.'}
          </p>
        )}
      </Card>

      {profileMsg && <Card><p className="muted">{profileMsg}</p></Card>}

      {selected && (
        <div ref={detailRef}>
          <Card
            title={`${selected.user.full_name} — portfolio`}
            sub={`${ROLE_LABEL[selected.user.role]} · ${selected.user.email}`}
            aside={<button className="mini-view" onClick={() => setSelected(null)}>Close</button>}
          >
            {selected.profile
              ? <ProfileDetail p={selected.profile} />
              : <p className="empty-note">This user has not built a portfolio yet, so no
                  analysis module has anything to run on for them.</p>}
          </Card>
        </div>
      )}
    </div>
  )
}
