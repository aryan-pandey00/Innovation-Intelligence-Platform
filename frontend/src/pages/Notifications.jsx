import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { notificationService, extractErrorMessage } from '../services/api'
import { useSession } from '../services/session'
import { alertsChanged } from '../hooks'
import { isOwner } from '../roles'
import Loading from '../components/Loading'
import { PageHeader, Card, EmptyNote } from '../components/ui'
import { fmtDate } from '../components/ui/format'

const KIND_LABEL = {
  funding_new: 'New funding',
  funding_deadline: 'Deadline',
  patent_activity: 'Patent activity',
  technology_emerging: 'Technology',
  research_trend: 'Research trend',
  commercialization: 'Commercialisation',
  pipeline: 'Pipeline',
  platform: 'Announcement',
  platform_health: 'Platform',
}

const SCOPE = {
  owner: 'New and closing grants, risks in your portfolio, and changes in the fields you named.',
  innovation_manager: 'Innovators who cannot be matched or assessed yet, and announcements from an administrator.',
  admin: 'Announcements, and the catalogue and access problems worth your attention.',
}

const feedNote = (role) => (isOwner(role)
  ? 'Worked out from your own portfolio and the catalogue when you open this page. '
    + 'Nothing here is sent by email.'
  : 'Worked out from the platform’s own figures when you open this page. '
    + 'Nothing here is sent by email.')

function Row({ item, onRead, onDismiss }) {
  const unread = !item.read_at
  return (
    <li className={unread ? 'note-row unread' : 'note-row'}>
      <div className="note-main">
        <div className="note-head">
          <span className={`note-kind kind-${item.kind}`}>
            {KIND_LABEL[item.kind] || item.kind}
          </span>
          {unread && <span className="note-dot" aria-label="Unread" />}
          <span className="note-when">
            {fmtDate(item.occurred_at || item.created_at)}
          </span>
        </div>
        <p className="note-title">{item.title}</p>
        <p className="note-body">{item.body}</p>
        {item.link && (
          <Link to={item.link} className="inline-link"
                onClick={() => unread && onRead(item.id)}>
            Open →
          </Link>
        )}
      </div>
      <div className="note-actions">
        {unread && (
          <button className="link-btn" onClick={() => onRead(item.id)}>
            Mark read
          </button>
        )}
        <button className="link-btn danger" onClick={() => onDismiss(item.id)}>
          Dismiss
        </button>
      </div>
    </li>
  )
}

export default function Notifications() {
  const { role } = useSession()
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await notificationService.feed({ limit: 100 })
      setItems(res.data.items)
      setUnread(res.data.unread)
      setError('')
      alertsChanged()
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not load your alerts.'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const read = async (id) => {
    setItems((cur) => cur.map((n) => (
      n.id === id && !n.read_at ? { ...n, read_at: new Date().toISOString() } : n)))
    setUnread((n) => Math.max(0, n - 1))
    try { await notificationService.markRead(id); alertsChanged() } catch { load() }
  }

  const dismiss = async (id) => {
    const gone = items.find((n) => n.id === id)
    setItems((cur) => cur.filter((n) => n.id !== id))
    if (gone && !gone.read_at) setUnread((n) => Math.max(0, n - 1))
    try { await notificationService.dismiss(id); alertsChanged() } catch { load() }
  }

  const readAll = async () => {
    setItems((cur) => cur.map((n) => (
      n.read_at ? n : { ...n, read_at: new Date().toISOString() })))
    setUnread(0)
    try { await notificationService.markAllRead(); alertsChanged() } catch { load() }
  }

  if (loading) return <Loading message="Loading your alerts…" />

  const now = items.filter((n) => n.priority === 'now')
  const context = items.filter((n) => n.priority !== 'now')
  const scope = isOwner(role) ? SCOPE.owner : (SCOPE[role] || SCOPE.owner)

  return (
    <div className="dashboard">
      <PageHeader trail="Account" title="Notifications">
        {scope}
      </PageHeader>

      {error && <div className="error">{error}</div>}

      <Card
        title={unread ? `${unread} unread`
          : (items.length ? `${items.length} read` : 'All caught up')}
        sub={items.length ? feedNote(role) : undefined}
        aside={unread > 0
          ? <button className="link-btn" onClick={readAll}>Mark all read</button>
          : null}
      >
        {items.length === 0 ? (
          <EmptyNote>
            Nothing to report. {isOwner(role)
              ? 'New grants that match your profile, approaching deadlines and '
                + 'movement in your fields will appear here.'
              : 'Anything needing your attention will appear here.'}
          </EmptyNote>
        ) : (
          <>
            {now.length > 0 && (
              <>
                <p className="section-label">Needs attention</p>
                <ul className="note-list">
                  {now.map((n) => (
                    <Row key={n.id} item={n} onRead={read} onDismiss={dismiss} />
                  ))}
                </ul>
              </>
            )}
            {context.length > 0 && (
              <>
                <p className="section-label" style={{ marginTop: now.length ? 22 : 0 }}>
                  Worth knowing
                </p>
                <ul className="note-list">
                  {context.map((n) => (
                    <Row key={n.id} item={n} onRead={read} onDismiss={dismiss} />
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        {!isOwner(role) && (
          <p className="table-foot">
            Funding and portfolio alerts belong to accounts that own a portfolio, so
            this account does not receive them.
            {role === 'admin' && (
              <> Announcements are sent from{' '}
                <Link to="/announcements" className="inline-link">
                  Announcements</Link>, in the sidebar.
              </>
            )}
          </p>
        )}
      </Card>
    </div>
  )
}
