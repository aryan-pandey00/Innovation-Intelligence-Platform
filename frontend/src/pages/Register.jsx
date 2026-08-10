import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService, extractErrorMessage } from '../services/api'
import AuthShell from '../components/AuthShell'
import { IconEye, IconEyeOff } from '../components/ui/icons'

/** The role decides which modules and dashboard you get, so it needs explaining
 *  rather than being a bare dropdown. */
/* Both hints fit one line each. At two lines they added ~36px to a form whose last
   line already fell below the fold, and neither needed the length — the second was
   also the app's only "commercialization" among British spellings elsewhere. */
const ROLES = [
  {
    value: 'researcher',
    label: 'Researcher',
    hint: 'Funding, trends and patent analysis for your published work.',
  },
  {
    value: 'startup_founder',
    label: 'Startup Founder',
    hint: 'Funding, accelerators and routes to commercialisation.',
  },
]

export default function Register() {
  const [form, setForm] = useState({
    email: '', full_name: '', password: '', role: 'researcher', organization: '',
  })
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const res = await authService.register(form)
      localStorage.setItem('token', res.data.access_token)
      authService.setCachedUser(res.data.user)
      navigate('/portfolio')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not create your account.'))
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Takes a minute. You can fill in your research profile next."
      footer={<>Already registered? <Link to="/login">Sign in</Link></>}
    >
      {error && <div className="error">{error}</div>}
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input id="full_name" name="full_name" autoComplete="name" required
                 value={form.full_name} onChange={change} />
        </div>
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" autoComplete="email" required
                 value={form.email} onChange={change} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <div className="input-affix">
            <input id="password" name="password" type={showPassword ? 'text' : 'password'}
                   autoComplete="new-password" minLength={6} required
                   value={form.password} onChange={change} />
            <button type="button" className="affix-btn"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((v) => !v)}>
              {showPassword ? <IconEyeOff size={17} /> : <IconEye size={17} />}
            </button>
          </div>
          <p className="field-help">At least 6 characters.</p>
        </div>
        <div className="field">
          <label htmlFor="organization">Organisation <span className="optional">optional</span></label>
          <input id="organization" name="organization"
                 value={form.organization} onChange={change} />
        </div>

        <fieldset className="field role-choice">
          <legend>I am a</legend>
          {ROLES.map((r) => (
            <label key={r.value} className={form.role === r.value ? 'role-opt sel' : 'role-opt'}>
              <input type="radio" name="role" value={r.value}
                     checked={form.role === r.value} onChange={change} />
              <span>
                <strong>{r.label}</strong>
                <span className="role-hint">{r.hint}</span>
              </span>
            </label>
          ))}
          {/* No role policy here. It named two roles this form cannot grant, to a
              reader who has never seen either term, and could not change what they
              do next — both choices they can make are already above. */}
        </fieldset>

        <button type="submit" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
