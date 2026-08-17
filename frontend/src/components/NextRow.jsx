import { Link } from 'react-router-dom'

import { byKey, canOpen } from './modules'
import { useSession } from '../services/session'

export default function NextRow({ items, exclude = [] }) {
  const { role } = useSession()

  if (!role) return null

  const already = new Set(exclude.filter(Boolean))
  const open = items
    .map((item) => ({ ...item, module: byKey[item.key] }))
    .filter(({ module }) => module && canOpen(role, module.to)
                            && !already.has(module.to))

  if (open.length === 0) return null

  return (
    <div className="next-row">
      {open.map(({ key, title, note, module }) => {
        const { Icon, to } = module
        return (
          <Link key={key} to={to} className="next-card">
            <Icon size={18} />
            <span><strong>{title}</strong>{note}</span>
          </Link>
        )
      })}
    </div>
  )
}
