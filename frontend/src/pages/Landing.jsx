import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { ROLE_LABEL } from '../roles'
import { byKey } from '../components/modules'

const CAPABILITIES = [
  ['funding', 'Funding that fits',
   'We rank every grant against your work and check if you can apply.'],
  ['patents', 'See the whole field',
   'Who publishes, who patents, and how the field is changing.'],
  ['innovation', 'Know what to do next',
   'One score you can break down factor by factor, plus a route to market.'],
]

const STEPS = [
  ['Describe your work',
   'Your publications, your patents and the technology areas you work in.'],
  ['We check the records',
   'Research papers from OpenAlex and patents from the European Patent Office.'],
  ['You get an answer',
   'Grants you can apply for, a clear view of your field, and a route to market.'],
]

const AUDIENCE = [
  ['researcher', 'You have published work and want to know what funding it can win.', [
    'Grants matched to the topics you research',
    'How much is published in your field and what is growing',
    'Who is patenting around your research',
  ]],
  ['startup_founder', 'You have a technology and need funding to take it to market.', [
    'Grants and accelerators you actually qualify for',
    'Which patents already exist in your area and who owns them',
    'A route from your technology to a product, a licence or a company',
  ]],
]

const SOURCES = [
  ['OpenAlex', 'Research',
   'An open catalogue of the world’s published research.',
   'Read live, every time, so what is growing in your field is current rather than '
   + 'cached.'],
  ['EPO Open Patent Services', 'Patents',
   'The European Patent Office’s own patent data.',
   'How large a field is, who is filing in it, and which organisations hold what.'],
]

const RULES = [
  'We say when a number comes from a sample',
  'Every percentage says what it is out of',
  'Missing data is labelled, not hidden',
]

function useReveal() {
  const ref = useRef(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return setShown(true)
    const io = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      setShown(true)
      io.disconnect()
    }, { rootMargin: '0px 0px -12% 0px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return [ref, shown ? 'reveal is-in' : 'reveal']
}

function Reveal({ as: Tag = 'section', className = '', children, ...rest }) {
  const [ref, cls] = useReveal()
  return (
    <Tag ref={ref} className={`${cls} ${className}`.trim()} {...rest}>{children}</Tag>
  )
}

function Steps({ items }) {
  const refs = useRef([])
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return setCount(items.length)
    const io = new IntersectionObserver((entries) => {
      let highest = 0
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        highest = Math.max(highest, Number(entry.target.dataset.step) + 1)
        io.unobserve(entry.target)
      }
      if (highest) setCount((n) => Math.max(n, highest))
    }, { rootMargin: '0px 0px -30% 0px' })
    refs.current.forEach((el) => el && io.observe(el))
    return () => io.disconnect()
  }, [items.length])

  const progress = items.length > 1 ? Math.max(0, count - 1) / (items.length - 1) : 0

  return (
    <ol className="steps" style={{ '--progress': progress }}>
      <span className="steps-rail" aria-hidden="true" />
      {items.map(([title, body], i) => (
        <li key={title} data-step={i} style={{ '--i': i }}
            ref={(el) => { refs.current[i] = el }}
            className={i < count ? 'step is-in' : 'step'}>
          <span className="step-dot" aria-hidden="true">{i + 1}</span>
          <h3>{title}</h3>
          <p>{body}</p>
        </li>
      ))}
    </ol>
  )
}

export default function Landing() {
  return (
    <div className="landing">
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
          <span className="hero-eyebrow">Research funding &amp; innovation intelligence</span>
          <h1>
            Find the funding. See the patents.<br />
            <span className="hero-accent-text">Decide what comes next.</span>
          </h1>
          <p>
            One place to see which grants fit your work and who is already patenting
            in your field.
          </p>
          <div className="landing-cta">
            <Link to="/register" className="btn-solid lg">Get started</Link>
            <Link to="/login" className="btn-quiet lg">I already have an account</Link>
          </div>
          <p className="landing-sources">
            Built on <strong>OpenAlex</strong> and <strong>EPO Open Patent Services</strong>
          </p>
        </section>
      </div>

      <Reveal className="landing-section">
        <h2>What it does</h2>
        <div className="cap-grid stagger">
          {CAPABILITIES.map(([key, title, body], i) => {
            const Icon = byKey[key].Icon
            return (
              <article className="cap" key={key} style={{ '--i': i }}>
                <span className="cap-icon" aria-hidden="true"><Icon size={20} /></span>
                <h3>{title}</h3>
                <p>{body}</p>
              </article>
            )
          })}
        </div>
      </Reveal>

      <Reveal className="landing-section landing-how">
        <h2>How it works</h2>
        <Steps items={STEPS} />
      </Reveal>

      <Reveal className="landing-section landing-audience">
        <h2>Who it is for</h2>
        <div className="audience-grid stagger">
          {AUDIENCE.map(([role, body, points], i) => (
            <article className="audience-card" key={role} style={{ '--i': i }}>
              <h3>{ROLE_LABEL[role]}</h3>
              <p>{body}</p>
              <ul>{points.map((p) => <li key={p}>{p}</li>)}</ul>
            </article>
          ))}
        </div>
        <p className="landing-note">
          Only researchers and startup founders can sign up here. An administrator sets
          up the other roles.
        </p>
      </Reveal>

      <Reveal className="landing-honesty">
        <h2>Where the numbers come from</h2>
        <div className="source-pair stagger">
          {SOURCES.map(([name, tag, what, powers], i) => (
            <article className="source-card" key={name} style={{ '--i': i }}>
              <header>
                <h3>{name}</h3>
                <span className="source-tag">{tag}</span>
              </header>
              <p>{what}</p>
              <p className="source-powers">{powers}</p>
            </article>
          ))}
        </div>
        <p className="honesty-lead">Every number says what it was measured on</p>
        <ul className="rule-row stagger">
          {RULES.map((r, i) => <li key={r} style={{ '--i': i }}>{r}</li>)}
        </ul>
        <p className="landing-note">
          Grant listings come from Grants.gov, the World Bank and UKRI.
        </p>
      </Reveal>

      <Reveal className="landing-close">
        <h2>Start with your own field</h2>
        <p className="close-lead">
          Create an account, name the technology areas you work in, and the first
          analysis runs on your own field.
        </p>
        <div className="landing-cta">
          <Link to="/register" className="btn-solid lg">Create account</Link>
          <Link to="/login" className="btn-quiet lg">Log in</Link>
        </div>
      </Reveal>

      <footer className="landing-foot">
        <span>Research Funding &amp; Innovation Intelligence Platform</span>
        <span className="muted">Data from OpenAlex and EPO Open Patent Services</span>
      </footer>
    </div>
  )
}
