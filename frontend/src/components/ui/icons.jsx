/**
 * The icon factory, plus the icons that are not module destinations. `lineIcon`
 * is shared with `components/modules.jsx`, so a control icon and a nav icon
 * cannot drift apart in weight or grid.
 */

/** 20x20 on a 24 grid, `currentColor` so one set works on dark and light. */
export const lineIcon = (paths) => function Icon({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths}
    </svg>
  )
}

export const IconEye = lineIcon(
  <>
    <path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="3" />
  </>
)

export const IconEyeOff = lineIcon(
  <>
    <path d="M9.9 5.7A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.4 3.3" />
    <path d="M6.5 7.4A16.7 16.7 0 0 0 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.2-1.1" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    <path d="M4 4l16 16" />
  </>
)
