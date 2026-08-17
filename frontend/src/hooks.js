import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { adminService, notificationService } from './services/api'

export const ALERTS_CHANGED = 'alerts-changed'
export const alertsChanged = () => window.dispatchEvent(new Event(ALERTS_CHANGED))

export function useUnreadAlerts() {
  const [count, setCount] = useState(0)
  const { pathname } = useLocation()

  useEffect(() => {
    let live = true
    const read = () => notificationService.unreadCount()
      .then((res) => { if (live) setCount(res.data.unread || 0) })
      .catch(() => {})
    read()
    window.addEventListener(ALERTS_CHANGED, read)
    return () => { live = false; window.removeEventListener(ALERTS_CHANGED, read) }
  }, [pathname])

  return count
}

export const RESETS_CHANGED = 'resets-changed'
export const resetsChanged = () => window.dispatchEvent(new Event(RESETS_CHANGED))

export function useWaitingResets(role) {
  const [count, setCount] = useState(0)
  const { pathname } = useLocation()

  useEffect(() => {
    if (role !== 'admin') { setCount(0); return undefined }
    let live = true
    const read = () => adminService.waitingResets()
      .then((res) => { if (live) setCount(res.data.waiting || 0) })
      .catch(() => {})
    read()
    window.addEventListener(RESETS_CHANGED, read)
    return () => { live = false; window.removeEventListener(RESETS_CHANGED, read) }
  }, [pathname, role])

  return count
}

export function usePipelineFields(role) {
  const [fields, setFields] = useState([])

  useEffect(() => {
    if (role !== 'innovation_manager') return
    let live = true
    adminService.pipelineStats()
      .then((res) => {
        if (live) setFields((res.data.technologies || []).map((t) => t.name))
      })
      .catch(() => {})
    return () => { live = false }
  }, [role])

  return fields
}
