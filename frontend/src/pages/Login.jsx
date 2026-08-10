import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authService, extractErrorMessage } from '../services/api'
import AuthShell from '../components/AuthShell'
import { IconEye, IconEyeOff } from '../components/ui/icons'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (busy) return          // a double click used to fire two login requests
    setBusy(true)
    setError('')
    try {
      const res = await authService.login(email, password)
      localStorage.setItem('token', res.data.access_token)
      authService.setCachedUser(res.data.user)
      navigate(res.data.user.role === 'admin' ? '/admin' : '/dashboard')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not sign you in.'))
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to your workspace."
      footer={<>New here? <Link to="/register">Create an account</Link></>}
    >
      {error && <div className="error">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" autoComplete="email" required
                 value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          {/* One reveal control. The native one is suppressed in CSS; without that,
              Edge and Chrome drew their own eye beside ours. */}
          <div className="input-affix">
            <input id="password" type={showPassword ? 'text' : 'password'}
                   autoComplete="current-password" required
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            <button type="button" className="affix-btn"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((v) => !v)}>
              {showPassword ? <IconEyeOff size={17} /> : <IconEye size={17} />}
            </button>
          </div>
        </div>
        <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </AuthShell>
  )
}
