import { Link } from 'react-router-dom'

const POINTS = [
  'Grants ranked against your profile, with eligibility checked',
  'Publication and patent activity, measured year by year',
  'One score for your position, and what to do about it',
]

export default function AuthShell({ title, subtitle, children, footer, wide }) {
  return (
    <div className="auth">
      <aside className="auth-brand">
        <Link to="/" className="auth-logo">
          Innovation <span className="brand-accent">Intelligence</span>
        </Link>
        <h2>Find the funding. See the patents. Decide what comes next.</h2>
        <span className="hero-accent" aria-hidden="true" />
        <ul>
          {POINTS.map((p) => <li key={p}>{p}</li>)}
        </ul>
        <p className="auth-sources">
          Built on <strong>OpenAlex</strong> and{' '}
          <strong>EPO Open Patent Services</strong> — every figure names what it was
          measured on.
        </p>
      </aside>

      <main className="auth-panel">
        <div className={wide ? 'auth-form wide' : 'auth-form'}>
          <h1>{title}</h1>
          {subtitle && <p className="page-sub">{subtitle}</p>}
          {children}
          {footer && <div className="link">{footer}</div>}
        </div>
      </main>
    </div>
  )
}
