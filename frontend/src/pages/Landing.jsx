import { Link } from 'react-router-dom'
import ToolCards from '../components/ToolCards'

/**
 * Public front door. `/` used to redirect straight to a login form saying only
 * "Login", so a first-time visitor learned nothing about the product.
 *
 * Deliberately no statistics: nothing pre-auth could source them, and inventing
 * numbers here would undercut the data work behind everything else.
 */
export default function Landing() {
  return (
    <div className="landing">
      {/* The nav and the hero are one dark band, so they share one background:
          two separately-painted blocks cannot carry a gradient across the seam. */}
      <div className="landing-top">
        <header className="landing-nav">
          <span className="landing-brand">
            Innovation <span className="brand-accent">Intelligence</span>
          </span>
          <nav className="landing-actions">
            <Link to="/login" className="btn-quiet">Log in</Link>
            <Link to="/register" className="btn-solid">Create account</Link>
          </nav>
        </header>

        <section className="landing-hero">
          <h1>
            Find the funding. See the patents.<br />
            Decide what comes next.
          </h1>
          <p>
            One place to find funding, follow your field, and see where your research
            can go next.
          </p>
          <div className="landing-cta">
            <Link to="/register" className="btn-solid lg">Get started</Link>
            <Link to="/login" className="btn-quiet lg">I already have an account</Link>
          </div>
        </section>
      </div>

      <section className="landing-modules">
        <h2>What it covers</h2>
        {/* Not linked: every one of these routes needs an account. */}
        <ToolCards linked={false} />
      </section>

      <footer className="landing-foot">
        <span>Research Funding &amp; Innovation Intelligence Platform</span>
        {/* The one place a data source is still named: a footer credit, not a claim
            about what the product does. */}
        <span className="muted">Data from OpenAlex and EPO Open Patent Services</span>
      </footer>
    </div>
  )
}
