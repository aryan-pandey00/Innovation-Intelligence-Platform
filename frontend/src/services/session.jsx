import { createContext, useCallback, useContext, useEffect, useState } from 'react'

import { authService, USER_UPDATED } from './api'

const SessionContext = createContext(null)

export function SessionProvider({ children }) {
  const [user, setUser] = useState(authService.getCachedUser)
  const [verified, setVerified] = useState(false)

  const refresh = useCallback(() => authService.getMe()
    .then((res) => {
      authService.setCachedUser(res.data)
      setUser(res.data)
      setVerified(true)
      return res.data
    })
    .catch((err) => {
      if (err.response?.status === 401) {
        authService.logout()
        setUser({})
      }
      setVerified(true)
      return null
    }), [])

  useEffect(() => {
    if (localStorage.getItem('token')) refresh()
    else setVerified(true)
  }, [refresh])

  useEffect(() => {
    const sync = () => setUser(authService.getCachedUser())
    window.addEventListener(USER_UPDATED, sync)
    window.addEventListener('storage', sync)
    return () => {
      window.removeEventListener(USER_UPDATED, sync)
      window.removeEventListener('storage', sync)
    }
  }, [])

  return (
    <SessionContext.Provider value={{ user, role: user?.role, verified, refresh }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (ctx === null) {
    throw new Error('useSession must be used inside a SessionProvider')
  }
  return ctx
}
