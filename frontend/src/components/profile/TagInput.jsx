import { useState } from 'react'
import { Link } from 'react-router-dom'
import { InfoHint } from '../ui'
import { byKey } from '../modules'

/**
 * Chip input for the three profile field types.
 *
 * Which field a term goes in decides which module uses it, and that was the most
 * confusing thing about the profile — a discipline in Technology Areas becomes a
 * patent query and returns nonsense. `routing` shows the field-to-page mapping at
 * a glance, and takes module keys so it reads with the same names as the sidebar.
 */
export default function TagInput({ label, routing = [], hint, tags, onChange, placeholder,
                                   elsewhere = [] }) {
  const [draft, setDraft] = useState('')
  const [note, setNote] = useState('')

  const add = () => {
    const v = draft.trim()
    if (!v) return
    const low = v.toLowerCase()

    if (tags.some((t) => t.toLowerCase() === low)) {
      setNote(`“${v}” is already here.`)
      return
    }
    // Funding dedupes before querying so nothing breaks, but a term sitting in
    // two fields is invisible to the user. Say which field already holds it.
    const held = elsewhere.find((f) => f.terms.some((t) => t.toLowerCase() === low))
    if (held) {
      setNote(`“${v}” is already in ${held.label}. One field is enough.`)
      return
    }
    const broader = [...tags, ...elsewhere.flatMap((f) => f.terms)]
      .find((t) => low.startsWith(`${t.toLowerCase()} `) || t.toLowerCase().startsWith(`${low} `))
    if (broader) {
      setNote(`Added. Note you also have “${broader}”, which overlaps.`)
      onChange([...tags, v])
      setDraft('')
      return
    }

    setNote('')
    onChange([...tags, v])
    setDraft('')
  }

  const remove = (t) => { setNote(''); onChange(tags.filter((x) => x !== t)) }

  return (
    <div className="field">
      <label>
        {label}
        {hint && <InfoHint>{hint}</InfoHint>}
      </label>
      {routing.length > 0 && (
        <p className="field-routing">
          <span aria-hidden="true">→ </span>
          {routing.map((key, i) => (
            <span key={key}>
              {i > 0 && <span aria-hidden="true"> · </span>}
              <Link to={byKey[key].to}>{byKey[key].name}</Link>
            </span>
          ))}
        </p>
      )}
      {tags.length > 0 && (
        <div className="tag-list">
          {tags.map((t) => (
            <span key={t} className="tag">
              {t}
              <button type="button" aria-label={`Remove ${t}`} onClick={() => remove(t)}>×</button>
            </span>
          ))}
        </div>
      )}
      <input
        value={draft}
        placeholder={placeholder || 'Type and press Enter'}
        onChange={(e) => { setDraft(e.target.value); setNote('') }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
        }}
      />
      {note && <p className="field-note" role="status">{note}</p>}
    </div>
  )
}
