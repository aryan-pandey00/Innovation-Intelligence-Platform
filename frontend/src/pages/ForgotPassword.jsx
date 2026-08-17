import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authService, extractErrorMessage } from '../services/api'
import AuthShell from '../components/AuthShell'
import { IconEye, IconEyeOff } from '../components/ui/icons'

const MIN_PASSWORD = 8
const MAX_APPEAL = 500
const CLAIM_KEY = 'pwreset'
const POLL_MS = 5000
const MAX_POLLS = 180

const stepsFor = (mode) => [
  'Your email',
  mode === 'appeal' ? 'Tell an administrator' : 'Your questions',
  'Approval',
  'New password',
]
const STEP_INDEX = { ask: 0, answer: 1, appeal: 1, waiting: 2, approved: 3 }

const read = () => {
  try {
    return JSON.parse(localStorage.getItem(CLAIM_KEY) || 'null')
  } catch {
    return null
  }
}

function Steps({ step, mode }) {
  const at = STEP_INDEX[step]
  if (at == null) return null
  return (
    <ol className="reset-steps" aria-label="Progress">
      {stepsFor(mode).map((label, i) => (
        <li key={label}
            className={i === at ? 'now' : i < at ? 'done' : ''}
            aria-current={i === at ? 'step' : undefined}>
          <span className="reset-step-n">{i + 1}</span>
          <span>{label}</span>
        </li>
      ))}
    </ol>
  )
}

export default function ForgotPassword() {
  const [step, setStep] = useState('ask')
  const [mode, setMode] = useState('questions')
  const [email, setEmail] = useState('')
  const [claim, setClaim] = useState('')
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState(['', ''])
  const [appeal, setAppeal] = useState('')

  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [gaveUp, setGaveUp] = useState(false)
  const polls = useRef(0)
  const navigate = useNavigate()

  const forget = () => localStorage.removeItem(CLAIM_KEY)
  const remember = (next) =>
    localStorage.setItem(CLAIM_KEY, JSON.stringify({ ...read(), ...next }))

  const applyState = useCallback((state) => {
    if (state === 'approved') setStep('approved')
    else if (state === 'declined') setStep('declined')
    else if (state === 'expired' || state === 'used') setStep('expired')
  }, [])

  useEffect(() => {
    const saved = read()
    if (!saved?.claim) return
    let cancelled = false
    authService.resetStatus(saved.claim)
      .then((res) => {
        if (cancelled) return
        const state = res.data.state
        if (state === 'expired' || state === 'used') {
          forget()
          return
        }
        setClaim(saved.claim)
        setEmail(saved.email || '')
        setMode(saved.mode || 'questions')
        if (state === 'waiting') setStep('waiting')
        else applyState(state)
      })
      .catch(() => forget())
    return () => { cancelled = true }
  }, [applyState])

  useEffect(() => {
    if (step !== 'waiting' || !claim) return undefined
    polls.current = 0
    const id = setInterval(async () => {
      polls.current += 1
      if (polls.current > MAX_POLLS) {
        setGaveUp(true)
        clearInterval(id)
        return
      }
      try {
        applyState((await authService.resetStatus(claim)).data.state)
      } catch {
      }
    }, POLL_MS)
    return () => clearInterval(id)
  }, [step, claim, applyState])

  const ask = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      const res = await authService.forgotPassword(email)
      setMode(res.data.mode)
      setQuestions(res.data.questions || [])
      setAnswers(['', ''])
      setAppeal('')
      setStep(res.data.mode === 'appeal' ? 'appeal' : 'answer')
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not start that request.'))
    } finally {
      setBusy(false)
    }
  }

  const sendToAdmin = async (call, fallback) => {
    if (busy) return
    setBusy(true); setError('')
    try {
      const res = await call()
      setClaim(res.data.claim)
      remember({ claim: res.data.claim, email, mode })
      setGaveUp(false)
      setStep('waiting')
    } catch (err) {
      setError(extractErrorMessage(err, fallback))
    } finally {
      setBusy(false)
    }
  }

  const submitAnswers = (e) => {
    e.preventDefault()
    sendToAdmin(() => authService.submitSecurityAnswers(
      email, answers, appeal.trim() || null), 'Could not send your answers.')
  }

  const submitAppeal = (e) => {
    e.preventDefault()
    sendToAdmin(() => authService.appealForReset(email, appeal),
                'Could not send your message.')
  }

  const setNewPassword = async (e) => {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError('')
    try {
      await authService.resetPassword(claim, password)
      forget()
      authService.logout()
      navigate('/login', { replace: true, state: {
        notice: 'Password changed. Sign in with the new one.',
      } })
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not set your password.'))
      setBusy(false)
    }
  }

  const startOver = () => {
    forget()
    setClaim(''); setEmail(''); setQuestions([]); setAnswers(['', ''])
    setAppeal(''); setMode('questions')
    setPassword(''); setError(''); setGaveUp(false); setStep('ask')
  }

  const useAnother = (
    <button type="button" className="linklike reset-switch" onClick={startOver}>
      Use a different email
    </button>
  )

  return (
    <AuthShell
      title="Forgot Password"
      subtitle="An administrator checks it is you, then lets you back in."
      footer={<>Remembered it? <Link to="/login">Sign in</Link></>}
    >
      <div className="notice">
        <strong>No email is sent.</strong> An administrator lets you back in on this
        page, so keep it open.
      </div>

      <Steps step={step} mode={mode} />
      {error && <div className="error">{error}</div>}

      {step === 'ask' && (
        <form onSubmit={ask}>
          <div className="field">
            <label htmlFor="fp-email">Email address</label>
            <input id="fp-email" type="email" autoComplete="email" required
                   autoFocus value={email}
                   onChange={(e) => setEmail(e.target.value)} />
          </div>
          <button type="submit" disabled={busy}>
            {busy ? 'Checking…' : 'Continue'}
          </button>
        </form>
      )}

      {step === 'answer' && (
        <form onSubmit={submitAnswers}>
          <p className="reset-for">
            Resetting <strong>{email}</strong> {useAnother}
          </p>
          {questions.map((question, i) => (
            <div className="field" key={question}>
              <label htmlFor={`fp-a${i}`}>{question}</label>
              <input id={`fp-a${i}`} required maxLength={120} autoComplete="off"
                     value={answers[i] || ''}
                     onChange={(e) => setAnswers(
                       answers.map((a, j) => (j === i ? e.target.value : a)))} />
            </div>
          ))}
          <p className="field-help">
            Capitalisation and punctuation do not matter.
          </p>
          <div className="field">
            <label htmlFor="fp-note">Anything else worth saying <span
              className="field-optional">(optional)</span></label>
            <textarea id="fp-note" rows={3} maxLength={MAX_APPEAL}
                      value={appeal}
                      onChange={(e) => setAppeal(e.target.value)} />
            <p className="field-help">
              If you are not sure you remembered these correctly, say who you are and
              what you use this platform for — an administrator can check that.{' '}
              {appeal && (
                <span className="char-left">{MAX_APPEAL - appeal.length} left</span>
              )}
            </p>
          </div>
          <button type="submit" disabled={busy}>
            {busy ? 'Sending…' : 'Send to an administrator'}
          </button>
        </form>
      )}

      {step === 'appeal' && (
        <form onSubmit={submitAppeal}>
          <p className="reset-for">
            Resetting <strong>{email}</strong> {useAnother}
          </p>
          <div className="notice">
            <strong>No security questions were set on this account.</strong> There is
            nothing here to prove it is you, so an administrator has to decide.
          </div>
          <div className="field">
            <label htmlFor="fp-appeal">Tell them who you are</label>
            <textarea id="fp-appeal" required rows={4} maxLength={MAX_APPEAL}
                      autoFocus value={appeal}
                      onChange={(e) => setAppeal(e.target.value)} />
            <p className="field-help">
              Your department, who you work with, what you use this platform for —
              anything an administrator can check.{' '}
              <span className="char-left">{MAX_APPEAL - appeal.length} left</span>
            </p>
          </div>
          <button type="submit" disabled={busy || !appeal.trim()}>
            {busy ? 'Sending…' : 'Send to an administrator'}
          </button>
        </form>
      )}

      {step === 'waiting' && (
        <div className="reset-wait">
          <p className="reset-for">
            Sent for <strong>{email}</strong> {useAnother}
          </p>
          <div className="reset-pulse" aria-hidden="true" />
          <p className="muted" role="status">
            {gaveUp
              ? 'Still waiting. Your request is in their queue — leave this open, or '
                + 'come back later.'
              : 'Waiting for an administrator. This page updates on its own.'}
          </p>
        </div>
      )}

      {step === 'approved' && (
        <form onSubmit={setNewPassword}>
          <p className="save-ok">Approved. Set a new password within 30 minutes.</p>
          <div className="field">
            <label htmlFor="fp-password">New password</label>
            <div className="input-affix">
              <input id="fp-password" type={show ? 'text' : 'password'}
                     autoComplete="new-password" required autoFocus
                     minLength={MIN_PASSWORD} maxLength={72}
                     value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="affix-btn"
                      aria-label={show ? 'Hide password' : 'Show password'}
                      aria-pressed={show} onClick={() => setShow((v) => !v)}>
                {show ? <IconEyeOff size={17} /> : <IconEye size={17} />}
              </button>
            </div>
            <p className="field-help">
              At least {MIN_PASSWORD} characters. Not your own name or email.
            </p>
          </div>
          <button type="submit" disabled={busy}>
            {busy ? 'Saving…' : 'Set new password'}
          </button>
          <p className="field-help">This signs you out everywhere else.</p>
        </form>
      )}

      {step === 'declined' && (
        <div className="reset-wait">
          <div className="error">
            An administrator declined this request. Speak to them, then ask again.
          </div>
          <button type="button" onClick={startOver}>Start again</button>
        </div>
      )}

      {step === 'expired' && (
        <div className="reset-wait">
          <div className="notice">
            This request has expired or was already used. Asking again takes a moment.
          </div>
          <button type="button" onClick={startOver}>Start again</button>
        </div>
      )}
    </AuthShell>
  )
}
