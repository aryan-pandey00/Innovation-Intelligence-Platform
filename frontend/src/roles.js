
export const ROLES = [
  { value: 'researcher', label: 'Researcher' },
  { value: 'startup_founder', label: 'Startup Founder' },
  { value: 'innovation_manager', label: 'Innovation Manager' },
  { value: 'admin', label: 'Administrator' },
]

export const ROLE_LABEL = Object.fromEntries(ROLES.map((r) => [r.value, r.label]))
export const ROLE_ORDER = Object.fromEntries(ROLES.map((r, i) => [r.value, i]))

export const OWNERS = ['researcher', 'startup_founder']
export const STAFF = ['innovation_manager', 'admin']

export const isOwner = (role) => OWNERS.includes(role)

export const roleLabel = (role) => ROLE_LABEL[role] || role || 'Unknown'
