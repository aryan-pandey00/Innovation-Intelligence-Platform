import { Link } from 'react-router-dom'
import { CARD_MODULES } from './modules'

/**
 * The five tool cards, shared by the dashboard and the public landing page so
 * both name the same tools the same way.
 *
 * `linked` is false on the landing page: those routes require an account.
 */
export default function ToolCards({ linked = true }) {
  return (
    <div className="module-cards">
      {CARD_MODULES.map(({ key, to, name, blurb, Icon }) => {
        const body = (
          <>
            <span className="mc-icon" aria-hidden="true"><Icon size={20} /></span>
            <span className="mc-title">{name}</span>
            <span className="mc-desc">{blurb}</span>
            {linked && <span className="mc-go" aria-hidden="true">→</span>}
          </>
        )
        return linked
          ? <Link key={key} to={to} className="module-card">{body}</Link>
          : <article key={key} className="module-card">{body}</article>
      })}
    </div>
  )
}
