import { Navigate, useLocation } from 'react-router-dom'

import Loading from './Loading'
import { HOME, canOpen, moduleForPath } from './modules'
import { useSession } from '../services/session'
import { roleLabel } from '../roles'

export default function RequireAccess({ children }) {
  const { pathname, state } = useLocation()
  const { role, verified } = useSession()

  if (!localStorage.getItem('token')) return <Navigate to="/login" replace />

  if (!role && !verified) return <Loading message="Checking your access…" />

  if (role && !canOpen(role, pathname)) {
    return <Navigate to={HOME} replace state={{ denied: pathname, role }} />
  }

  return (
    <>
      {state?.denied && <DeniedNotice path={state.denied} role={state.role} />}
      {children}
    </>
  )
}

function DeniedNotice({ path, role }) {
  const module = moduleForPath(path)
  return (
    <div className="denied-band">
      <p className="notice">
        {module ? `${module.name} is not part of your workspace.` : 'That page is not part of your workspace.'}
        {' '}Your role is {roleLabel(role)}.
      </p>
    </div>
  )
}
