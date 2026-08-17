
import { lineIcon as svg } from './ui/icons'
import { OWNERS } from '../roles'

const IconDashboard = svg(
  <>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
  </>
)

const IconPortfolio = svg(
  <>
    <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H10l1.5 2h6A2.5 2.5 0 0 1 20 9.5v7A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5Z" />
    <path d="M4 11h16" />
  </>
)

const IconFunding = svg(
  <>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M14.5 9.2A2.8 2.8 0 0 0 12 8c-1.5 0-2.6.8-2.6 2s1 1.7 2.6 2 2.6.8 2.6 2-1.1 2-2.6 2a2.8 2.8 0 0 1-2.5-1.2" />
    <path d="M12 6.2v1.6M12 16.2v1.6" />
  </>
)

const IconTrends = svg(
  <>
    <path d="M4 19V5" />
    <path d="M4 19h16" />
    <path d="M7.5 15.5l3.5-4.5 3 2.5 4.5-6" />
    <path d="M15 7h3.5v3.5" />
  </>
)

const IconPatents = svg(
  <>
    <path d="M6 3.5h8.5L19 8v9.5A2 2 0 0 1 17 19.5H6a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2Z" />
    <path d="M14 3.5V8h5" />
    <circle cx="11" cy="12.5" r="2.5" />
    <path d="M9.4 14.6 8.5 17.5l2.5-1.3 2.5 1.3-.9-2.9" />
  </>
)

const IconTechnology = svg(
  <>
    <rect x="7.5" y="7.5" width="9" height="9" rx="1.5" />
    <path d="M10.5 4v3.5M13.5 4v3.5M10.5 16.5V20M13.5 16.5V20M4 10.5h3.5M4 13.5h3.5M16.5 10.5H20M16.5 13.5H20" />
  </>
)

const IconInnovation = svg(
  <>
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="12" cy="12" r="0.6" fill="currentColor" />
  </>
)

const IconCommercialization = svg(
  <>
    <path d="M5 20V9.5A2.5 2.5 0 0 1 7.5 7H11" />
    <path d="M11 4.5h6.5L16 6.75l1.5 2.25H11Z" />
    <path d="M11 4v6" />
    <path d="M5 20h14" />
    <path d="M15.5 20v-5a2 2 0 0 1 2-2h1.5" />
  </>
)

const IconProfile = svg(
  <>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M4.8 20a7.2 7.2 0 0 1 14.4 0" />
  </>
)

const IconReports = svg(
  <>
    <path d="M6.5 3h7L18 7.5V19a2 2 0 0 1-2 2H6.5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
    <path d="M13 3v5h5" />
    <path d="M8.5 13h7M8.5 16.5h4.5" />
  </>
)

const IconAlerts = svg(
  <>
    <path d="M18 8.5a6 6 0 1 0-12 0c0 4.5-1.5 5.8-2 6.4a.6.6 0 0 0 .45 1h15.1a.6.6 0 0 0 .45-1c-.5-.6-2-1.9-2-6.4Z" />
    <path d="M10.4 19a1.9 1.9 0 0 0 3.2 0" />
  </>
)

const IconAdmin = svg(
  <>
    <path d="M12 3.5 19 6v5.5c0 4-2.9 7.3-7 8.5-4.1-1.2-7-4.5-7-8.5V6Z" />
    <path d="M9.5 12l1.8 1.8 3.4-3.6" />
  </>
)

const IconAnnounce = svg(
  <>
    <path d="M4 10.5v3a1.5 1.5 0 0 0 1.5 1.5H8l6.5 4V6.5L8 10.5H5.5A1.5 1.5 0 0 0 4 12Z" />
    <path d="M17.5 9.5a3.5 3.5 0 0 1 0 5" />
    <path d="M8 15v3.5a1.5 1.5 0 0 0 3 0V17" />
  </>
)

const IconResets = svg(
  <>
    <rect x="4.5" y="11" width="15" height="9" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 7.5-2" />
    <path d="M12 14.5v2.5" />
  </>
)

const EVERYONE = '*'
const OWNERS_AND_MANAGERS = [...OWNERS, 'innovation_manager']

export const MODULES = [
  {
    key: 'dashboard',
    to: '/dashboard',
    name: 'Dashboard',
    group: 'Workspace',
    roles: EVERYONE,
    card: false,
    Icon: IconDashboard,
  },
  {
    key: 'portfolio',
    to: '/portfolio',
    name: 'My Portfolio',
    group: 'Workspace',
    roles: OWNERS,
    card: false,
    Icon: IconPortfolio,
  },
  {
    key: 'innovator',
    to: '/innovator',
    name: 'Innovator',
    roles: ['admin', 'innovation_manager'],
    card: false,
    Icon: IconProfile,
  },
  {
    key: 'funding',
    to: '/funding',
    name: 'Funding Discovery',
    group: 'Discover',
    roles: OWNERS_AND_MANAGERS,
    card: true,
    Icon: IconFunding,
    blurb: 'Grants ranked against your profile, with eligibility checked against your role and country.',
  },
  {
    key: 'trends',
    to: '/trends',
    name: 'Research Trends',
    group: 'Discover',
    roles: OWNERS,
    card: true,
    Icon: IconTrends,
    blurb: 'How much is published in your field, what is rising, and the work everyone cites.',
  },
  {
    key: 'patents',
    to: '/patents',
    name: 'Patent Landscape',
    group: 'Analyse',
    roles: OWNERS_AND_MANAGERS,
    card: true,
    Icon: IconPatents,
    blurb: 'Who is patenting in a technology, how activity has moved, and the themes running through it.',
  },
  {
    key: 'technology',
    to: '/technology',
    name: 'Technology Intelligence',
    group: 'Analyse',
    roles: OWNERS_AND_MANAGERS,
    card: true,
    Icon: IconTechnology,
    blurb: 'Whether a technology is still early or already industrial.',
  },
  {
    key: 'innovation',
    to: '/innovation',
    name: 'Innovation Assessment',
    group: 'Analyse',
    roles: OWNERS,
    card: true,
    Icon: IconInnovation,
    blurb: 'A single score for your position, and what each factor contributes.',
  },
  {
    key: 'commercialization',
    to: '/commercialization',
    name: 'Commercialization',
    group: 'Act',
    roles: OWNERS,
    card: true,
    Icon: IconCommercialization,
    blurb: 'The route from a technology to a product, a licence or a company, and what to do first.',
  },
  {
    key: 'announcements',
    to: '/announcements',
    name: 'Announcements',
    group: 'Act',
    roles: ['admin'],
    card: false,
    Icon: IconAnnounce,
  },
  {
    key: 'resets',
    to: '/resets',
    name: 'Password Resets',
    group: 'Act',
    roles: ['admin'],
    card: false,
    Icon: IconResets,
  },
  {
    key: 'reports',
    to: '/reports',
    name: 'Reports',
    group: 'Act',
    roles: EVERYONE,
    card: true,
    Icon: IconReports,
    blurb: 'Any analysis written down, as a spreadsheet or a PDF.',
  },
  {
    key: 'notifications',
    to: '/notifications',
    name: 'Notifications',
    group: 'Account',
    roles: EVERYONE,
    card: false,
    Icon: IconAlerts,
  },
  {
    key: 'profile',
    to: '/profile',
    name: 'Profile',
    group: 'Account',
    roles: EVERYONE,
    card: false,
    Icon: IconProfile,
  },
  {
    key: 'admin',
    to: '/admin',
    name: 'Admin Panel',
    group: 'Account',
    roles: ['admin'],
    card: false,
    Icon: IconAdmin,
  },
]

export const GROUP_ORDER = ['Workspace', 'Discover', 'Analyse', 'Act', 'Account']

export const byKey = Object.fromEntries(MODULES.map((m) => [m.key, m]))

export const CARD_MODULES = MODULES.filter((m) => m.card)

const allows = (module, role) =>
  module.roles === EVERYONE || module.roles.includes(role)

export function visibleGroups(role) {
  return GROUP_ORDER
    .map((label) => ({
      label,
      links: MODULES.filter((m) => m.group === label && allows(m, role)),
    }))
    .filter((g) => g.links.length > 0)
}

export const HOME = '/dashboard'

export function moduleForPath(path) {
  return MODULES
    .filter((m) => path === m.to || path.startsWith(`${m.to}/`))
    .sort((a, b) => b.to.length - a.to.length)[0] || null
}

export function canOpen(role, path) {
  const module = moduleForPath(path)
  return module ? allows(module, role) : true
}
