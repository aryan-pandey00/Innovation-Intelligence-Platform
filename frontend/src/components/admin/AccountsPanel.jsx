import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { adminService, authService, extractErrorMessage } from '../../services/api'
import { useSession } from '../../services/session'
import { ROLES, ROLE_LABEL, ROLE_ORDER, isOwner } from '../../roles'
import TagRow from '../TagRow'
import { Card, StatCard, StatGrid } from '../ui'
import { fmtStamp } from '../ui/format'

const ROLES_FOR_ADMIN = ROLES.filter((r) => r.value !== 'admin')

const sortUsers = (rows) => [...rows].sort((a, b) =>
  (ROLE_ORDER[a.role] ?? 9) - (ROLE_ORDER[b.role] ?? 9)
  || (a.full_name || '').localeCompare(b.full_name || ''))

export default function AccountsPanel() {
  const [users, setUsers] = useState([])
  const [audit, setAudit] = useState([])
  const [openId, setOpenId] = useState(null)
  const [selected, setSelected] = useState(null)
  const [profileMsg, setProfileMsg] = useState('')
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { user: me, verified, refresh } = useSession()
  const isSuperAdmin = !!me?.is_superuser
  const known = !!me?.id

  const load = () => {
    adminService.listUsers()
      .then((res) => setUsers(sortUsers(res.data)))
      .catch((err) => {
        if (err.response?.status === 401) { authService.logout(); navigate('/login') }
        else setError('Could not load the user list.')
      })
    adminService.auditLog().then((res) => setAudit(res.data)).catch(() => setAudit([]))
  }

  useEffect(load, [])   // eslint-disable-line react-hooks/exhaustive-deps

  const changeRole = async (user, role) => {
    if (role === user.role) return
    if (!window.confirm(
      `Change ${user.full_name} from ${ROLE_LABEL[user.role] || user.role} `
      + `to ${ROLE_LABEL[role] || role}? This changes what they can access.`
    )) {
      load()
      return
    }
    try {
      await adminService.changeRole(user.id, role)
      load()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not change that role.'))
      load()
    }
  }

  const setSuperuser = async (user, grant) => {
    if (!window.confirm(grant
      ? `Make ${user.full_name} a super-admin? They will be able to create, change `
        + 'and remove other administrator accounts, including yours.'
      : `Remove super-admin from ${user.full_name}?`)) return
    try {
      await adminService.setSuperuser(user.id, grant)
      load()
      if (user.id === me?.id) refresh()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not change super-admin.'))
    }
  }

  const deleteUser = async (u) => {
    if (!window.confirm(`Delete ${u.full_name} (${u.email}) permanently? This cannot be undone.`)) return
    try {
      await adminService.deleteUser(u.id)
      if (openId === u.id) { setOpenId(null); setSelected(null); setProfileMsg('') }
      load()
    } catch (err) {
      alert(extractErrorMessage(err, 'Could not delete that user.'))
    }
  }

  const viewProfile = async (u) => {
    if (openId === u.id) { setOpenId(null); setSelected(null); setProfileMsg(''); return }
    setOpenId(u.id); setSelected(null); setProfileMsg('Loading…')
    try {
      const res = await adminService.getUserProfile(u.id)
      setSelected({ user: u, profile: res.data })
      setProfileMsg('')
    } catch (err) {
      if (err.response?.status === 404) {
        setSelected({ user: u, profile: null })
        setProfileMsg('')
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
    <>
      {error && <div className="error">{error}</div>}
      {verified && !known && (
        <div className="error">
          Could not confirm which account is yours, so role changes and deletions
          are switched off. Reload to try again.
        </div>
      )}

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
              <tr><th>Name</th><th>Email</th><th>Role</th><th>Portfolio</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {shown.map((u) => {
                const isSelf = known && u.id === me.id
                const isProtected = u.role === 'admin' && !isSuperAdmin
                const availableRoles = isSuperAdmin ? ROLES : ROLES_FOR_ADMIN
                const isOpen = openId === u.id

                const cls = isProtected ? 'row-protected' : ''

                return (
                  <Fragment key={u.id}>
                  <tr className={cls}>
                    <td>
                      {u.full_name}
                      {u.is_superuser && <span className="super-tag">Super</span>}
                    </td>
                    <td>{u.email}</td>
                    <td>
                      {isProtected ? (
                        <span className="role-badge role-locked">{ROLE_LABEL[u.role]}</span>
                      ) : (
                        <select
                          className="role-select"
                          value={u.role}
                          disabled={isSelf || !known || u.is_superuser}
                          aria-label={`Role for ${u.full_name}`}
                          title={u.is_superuser
                            ? 'Remove super-admin before changing this role' : ''}
                          onChange={(e) => changeRole(u, e.target.value)}
                        >
                          {availableRoles.map((r) => {
                            const orig = u.original_role || u.role
                            const isInvalidBaseChange = isOwner(r.value) && isOwner(orig)
                              && r.value !== orig
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
                      <button className="mini-view" onClick={() => viewProfile(u)}
                              disabled={!isOwner(u.role)}
                              aria-expanded={isOwner(u.role) ? isOpen : undefined}
                              title={isOwner(u.role) ? ''
                                : 'Staff accounts have no research portfolio'}>
                        {!isOwner(u.role) ? 'No portfolio'
                          : (isOpen ? 'Hide' : 'Summary')}
                      </button>
                    </td>
                    <td className="row-actions">
                      <div className="row-actions-inner">
                        {isSuperAdmin && u.role === 'admin' && !isSelf && (
                          <button className="mini-view"
                                  onClick={() => setSuperuser(u, !u.is_superuser)}>
                            {u.is_superuser ? 'Remove super' : 'Make super'}
                          </button>
                        )}
                        {isProtected ? (
                          <span className="cell-note">Protected</span>
                        ) : (
                          <button className="mini-del" disabled={isSelf || !known}
                                  onClick={() => deleteUser(u)}>
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="row-detail">
                      <td colSpan={5}>
                        {selected?.user.id === u.id
                          ? <PortfolioSummary user={u} profile={selected.profile} />
                          : <p className="muted">{profileMsg}</p>}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                )
              })}
              {shown.length === 0 && (
                <tr><td colSpan={5} className="cell-note">No account matches that search.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {known && (
          <p className="table-foot">
            {isSuperAdmin
              ? 'As super-admin you can change or remove any account, including other '
                + 'administrators, and grant super-admin to one of them.'
              : 'You can manage researchers, founders and managers. Administrator '
                + 'accounts are locked to a super-admin.'}
          </p>
        )}
      </Card>

      <RecentChanges events={audit} />
    </>
  )
}

function PortfolioSummary({ user, profile }) {
  if (!profile) {
    return (
      <p className="empty-note">
        {user.full_name} has not built a portfolio yet, so no analysis module has
        anything to run on for them.
      </p>
    )
  }

  const org = [profile.organization, profile.organization_type, profile.country]
    .filter(Boolean).join(' · ')
  const counts = [
    [profile.research_domains?.length || 0, 'research domain', 'research domains'],
    [profile.keywords?.length || 0, 'keyword', 'keywords'],
    [profile.technology_areas?.length || 0, 'technology area', 'technology areas'],
    [profile.publications?.length || 0, 'publication', 'publications'],
    [profile.patents?.length || 0, 'patent', 'patents'],
  ].map(([n, one, many]) => `${n} ${n === 1 ? one : many}`)

  return (
    <div className="acct-summary">
      <p className="detail-org">{org || <span className="detail-none">No organisation,
        type or country set</span>}</p>
      <p className="profile-driving">
        {counts.map((text, i) => (
          <span key={text}>
            {i > 0 && <span className="term-sep"> · </span>}
            <span className="term-count">{text}</span>
          </span>
        ))}
      </p>
      <TagRow label="Works on" items={profile.technology_areas}
              empty="no technology area set — patent and innovation analysis has
                     nothing to run on" />
      <Link to={`/innovator/${user.id}`} className="inline-link link-block">
        Open full profile →
      </Link>
    </div>
  )
}

const ACTION_LABEL = {
  role_change: 'changed the role of',
  grant_super: 'made super-admin',
  revoke_super: 'removed super-admin from',
  delete_user: 'deleted the account of',
  delete_self: 'deleted their own account',
}

function RecentChanges({ events }) {
  return (
    <Card title="Recent changes"
          sub={'Role changes, super-admin grants, account deletions and password '
            + 'resets — the most recent 20'}>
      {events.length === 0 ? (
        <p className="empty-note">Nothing has changed yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="user-table">
            <thead>
              <tr><th>When</th><th>Who</th><th>Did what</th><th>To whom</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="cell-note nowrap">{fmtStamp(e.at)}</td>
                  <td>{e.actor_email}</td>
                  <td>
                    {ACTION_LABEL[e.action] || e.action}
                    {e.detail && <span className="cell-note"> · {e.detail}</span>}
                  </td>
                  <td>{e.action === 'delete_self'
                    ? <span className="cell-note">themselves</span>
                    : e.target_email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
