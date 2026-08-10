/**
 * A labelled row of tags. `empty` states the absence rather than hiding the row,
 * which made "none set" indistinguishable from "not displayed here".
 */
export default function TagRow({ label, items, empty }) {
  const has = items && items.length > 0
  if (!has && !empty) return null
  return (
    <div className="tag-row">
      <strong>{label}</strong>
      {has
        ? items.map((t) => <span key={t} className="tag">{t}</span>)
        : <span className="tag-none">{empty}</span>}
    </div>
  )
}
