import { Link } from 'react-router-dom'

import { CARD_MODULES, GROUP_ORDER, canOpen } from './modules'
import { useSession } from '../services/session'

export default function ToolCards() {
  const { role } = useSession()

  const visible = CARD_MODULES.filter((m) => role && canOpen(role, m.to))

  const bands = GROUP_ORDER
    .map((label) => ({ label, cards: visible.filter((m) => m.group === label) }))
    .filter((band) => band.cards.length > 0)

  return (
    <div className="tool-bands">
      {bands.map(({ label, cards }) => (
        <section className="tool-band" key={label}>
          <h3 className="tool-band-label">{label}</h3>
          <div className="module-cards">
            {cards.map(({ key, to, name, blurb, Icon }) => {
              const body = (
                <>
                  <span className="mc-head">
                    <span className="mc-icon" aria-hidden="true"><Icon size={20} /></span>
                    <span className="mc-title">{name}</span>
                    <span className="mc-go" aria-hidden="true">→</span>
                  </span>
                  <span className="mc-desc">{blurb}</span>
                </>
              )
              return (
                <Link key={key} to={to}
                      className={`module-card band-${label.toLowerCase()}`}>{body}</Link>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}
