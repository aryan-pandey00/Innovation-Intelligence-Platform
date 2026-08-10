import { useState } from 'react'
import { profileService, extractErrorMessage } from '../../services/api'
import { Card, EmptyNote } from '../ui'
import DatasetSearch from './DatasetSearch'

const BLANK = {
  title: '', authors: [], venue: '', year: '', doi: '', url: '',
  citation_count: 0, abstract: '',
}

export default function PublicationsSection({ items, setItems }) {
  const [form, setForm] = useState(BLANK)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  const add = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const payload = {
        ...form,
        year: form.year ? Number(form.year) : null,
        citation_count: Number(form.citation_count) || 0,
      }
      const res = await profileService.addPublication(payload)
      setItems([...items, res.data])
      setForm(BLANK)
      setOpen(false)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not add that publication.'))
    }
  }

  const remove = async (id) => {
    await profileService.deletePublication(id)
    setItems(items.filter((p) => p.id !== id))
  }

  const importOne = async (rec) => {
    const res = await profileService.addPublication(rec)
    setItems((cur) => [...cur, res.data])
  }

  return (
    <Card
      title={`Publications (${items.length})`}
      sub="Feeds funding matches and your Research Novelty score."
    >
      <DatasetSearch kind="publication" onImport={importOne} />

      {items.length === 0 && <EmptyNote>Nothing added yet — search above to import your work.</EmptyNote>}

      {items.map((p) => (
        <div key={p.id} className="entry">
          <div>
            <strong>{p.title}</strong>
            <div className="muted">
              {[p.authors?.join(', '), p.venue, p.year,
                p.citation_count ? `${p.citation_count.toLocaleString('en-US')} citations` : null]
                .filter(Boolean).join(' · ')}
            </div>
          </div>
          <button type="button" className="mini-del" onClick={() => remove(p.id)}>Remove</button>
        </div>
      ))}

      {open ? (
        <form className="subform" onSubmit={add}>
          {error && <div className="error">{error}</div>}
          <div className="field">
            <label htmlFor="pub-title">Title</label>
            <input id="pub-title" required value={form.title}
                   onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="pub-authors">Authors</label>
            <input id="pub-authors" placeholder="Comma separated" value={form.authors.join(', ')}
                   onChange={(e) => setForm({
                     ...form,
                     authors: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                   })} />
          </div>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="pub-venue">Journal or venue</label>
              <input id="pub-venue" value={form.venue}
                     onChange={(e) => setForm({ ...form, venue: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pub-year">Year</label>
              <input id="pub-year" type="number" value={form.year}
                     onChange={(e) => setForm({ ...form, year: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pub-doi">DOI</label>
              <input id="pub-doi" value={form.doi}
                     onChange={(e) => setForm({ ...form, doi: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pub-cites">Citations</label>
              <input id="pub-cites" type="number" value={form.citation_count}
                     onChange={(e) => setForm({ ...form, citation_count: e.target.value })} />
            </div>
          </div>
          <div className="form-actions">
            <button type="submit">Add publication</button>
            <button type="button" className="btn-quiet" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        <button type="button" className="btn-quiet add-manual" onClick={() => setOpen(true)}>
          Add manually
        </button>
      )}
    </Card>
  )
}
