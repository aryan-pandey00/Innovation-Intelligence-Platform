import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService, extractErrorMessage } from '../services/api'
import AuthShell from '../components/AuthShell'
import SecurityQuestionFields from '../components/SecurityQuestionFields'
import { IconEye, IconEyeOff } from '../components/ui/icons'
import { ROLE_LABEL } from '../roles'

const ROLES = [
  { value: 'researcher', hint: 'Funding, trends and patent analysis for your published work.' },
  { value: 'startup_founder', hint: 'Funding, accelerators and routes to commercialisation.' },
].map((r) => ({ ...r, label: ROLE_LABEL[r.value] }))

export default function Register() {
  const [form, setForm] = useState({
    email: '', full_name: '', password: '', role: 'researcher', organization: '',
  })
  const [questions, setQuestions] = useState([
    { question: '', answer: '' }, { question: '', answer: '' },
  ])
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const change = (e) => setForm({ ...form, [e.target.name]: e.target.value })
  const changeQ = (i, field, value) =>
    setQuestions(questions.map((q, j) => (j === i ? { ...q, [field]: value } : q)))

  const submit = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const res = await authService.register({
        ...form, security_questions: questions,
      })
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
      wide
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
                   autoComplete="new-password" minLength={8} maxLength={72} required
                   value={form.password} onChange={change} />
            <button type="button" className="affix-btn"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((v) => !v)}>
              {showPassword ? <IconEyeOff size={17} /> : <IconEye size={17} />}
            </button>
          </div>
          <p className="field-help">At least 8 characters.</p>
        </div>
        <div className="field">
          <label htmlFor="organization">Organisation <span className="optional">optional</span></label>
          <input id="organization" name="organization"
                 value={form.organization} onChange={change} />
        </div>

        <fieldset className="field signup-questions">
          <legend>If you forget your password</legend>
          <p className="field-help" style={{ marginTop: 0 }}>
            No email is sent, so an administrator uses these to check it is you.{' '}
            <strong>Pick answers you will still know in a year.</strong>
          </p>
          <SecurityQuestionFields pairs={questions} onChange={changeQ}
                                  idPrefix="signup" required />
        </fieldset>

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
        </fieldset>

        <button type="submit" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
