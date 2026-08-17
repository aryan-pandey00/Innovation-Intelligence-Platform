import { useEffect, useState } from 'react'

const SWEEP_MS = 850
const easeOut = (p) => 1 - (1 - p) ** 3

export const STEP_MS = 70

export const skipMotion = () =>
  typeof window !== 'undefined' && window.matchMedia
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function useRevealOnScroll(rootRef, key) {
  useEffect(() => {
    const root = rootRef.current
    if (!root) return undefined

    const still = skipMotion() || typeof IntersectionObserver === 'undefined'

    let first = true
    const io = still ? null : new IntersectionObserver((entries) => {
      const hits = entries.filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      hits.forEach((e, i) => {
        if (first && i) e.target.style.setProperty('--enter', `${i * STEP_MS}ms`)
        e.target.classList.add('is-in')
        io.unobserve(e.target)
      })
      if (hits.length) first = false
    }, { rootMargin: '0px 0px -6% 0px' })

    const scan = () => {
      for (const el of root.querySelectorAll('.dashboard > *')) {
        if (el.classList.contains('is-in')) continue
        if (still) el.classList.add('is-in')
        else io.observe(el)
      }
    }

    let queued = false
    const mo = new MutationObserver(() => {
      if (queued) return
      queued = true
      requestAnimationFrame(() => { queued = false; scan() })
    })

    scan()
    mo.observe(root, { childList: true, subtree: true })
    return () => { mo.disconnect(); if (io) io.disconnect() }
  }, [rootRef, key])
}

export function useCountUp(target, delay = 0) {
  const [shown, setShown] = useState(() => (skipMotion() ? target : 0))

  useEffect(() => {
    if (skipMotion()) { setShown(target); return undefined }

    setShown(0)
    let raf = 0
    let began = 0
    const frame = (now) => {
      if (!began) began = now
      const elapsed = now - began - delay
      if (elapsed < 0) { raf = requestAnimationFrame(frame); return }
      const p = Math.min(1, elapsed / SWEEP_MS)
      setShown(Math.round(target * easeOut(p)))
      if (p < 1) raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [target, delay])

  return shown
}
