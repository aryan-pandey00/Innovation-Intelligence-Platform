import { Link } from 'react-router-dom'

/**
 * Two-panel frame for Login and Register. The left panel gives the auth pages a
 * product identity, since the nav bar carrying the brand only wraps
 * authenticated routes, and uses space a lone centred card wasted.
 */
/* "Measured on real corpora" was the heaviest phrase in the app, on the first
   page a visitor sees. Each point now names what you get. */
const POINTS = [
  'Grants ranked against your profile, with eligibility checked',
  'Publication and patent activity, measured year by year',
  'One score for your position, and what to do about it',
]

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="auth">
      <aside className="auth-brand">
        <Link to="/" className="auth-logo">
          Innovation <span className="brand-accent">Intelligence</span>
        </Link>
        <h2>Find funding, see who else is patenting, and decide what to build next.</h2>
        <span className="hero-accent" aria-hidden="true" />
        <ul>
          {POINTS.map((p) => <li key={p}>{p}</li>)}
        </ul>
      </aside>

      <main className="auth-panel">
        <div className="auth-form">
          <h1>{title}</h1>
          {subtitle && <p className="page-sub">{subtitle}</p>}
          {children}
          {footer && <div className="link">{footer}</div>}
        </div>
      </main>
    </div>
  )
}
