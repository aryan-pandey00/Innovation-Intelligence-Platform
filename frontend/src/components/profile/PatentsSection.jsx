import { useState } from 'react'
import { profileService, extractErrorMessage } from '../../services/api'
import { Card, EmptyNote } from '../ui'
import { fmtDate } from '../ui/format'
import DatasetSearch from './DatasetSearch'

const BLANK = {
  title: '', assignee: '', patent_number: '', filing_date: '',
  classification: '', technology_domain: '', citation_count: 0, url: '', abstract: '',
}

export default function PatentsSection({ items, setItems }) {
  const [form, setForm] = useState(BLANK)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  const add = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const payload = {
        ...form,
        filing_date: form.filing_date || null,
        citation_count: Number(form.citation_count) || 0,
      }
      const res = await profileService.addPatent(payload)
      setItems([...items, res.data])
      setForm(BLANK)
      setOpen(false)
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not add that patent.'))
    }
  }

  const remove = async (id) => {
    await profileService.deletePatent(id)
    setItems(items.filter((p) => p.id !== id))
  }

  const importOne = async (rec) => {
    const res = await profileService.addPatent(rec)
    setItems((cur) => [...cur, res.data])
  }

  return (
    <Card
      title={`Patents (${items.length})`}
      sub="Feeds your Patent Strength score and the commercialisation advice."
    >
      <DatasetSearch kind="patent" onImport={importOne} />

      {items.length === 0 && (
        <EmptyNote>
          None yet. If you publish but hold no patents, the Innovation page will flag
          whether your recent work is still protectable.
        </EmptyNote>
      )}

      {items.map((p) => (
        <div key={p.id} className="entry">
          <div>
            <strong>{p.title}</strong>
            <div className="muted">
              {[p.assignee, p.patent_number, p.classification, p.technology_domain,
                p.filing_date ? `filed ${fmtDate(p.filing_date)}` : null,
                p.citation_count ? `${p.citation_count} citations` : null]
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
            <label htmlFor="pat-title">Title</label>
            <input id="pat-title" required value={form.title}
                   onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="pat-assignee">Assignee</label>
              <input id="pat-assignee" value={form.assignee}
                     onChange={(e) => setForm({ ...form, assignee: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pat-number">Patent number</label>
              <input id="pat-number" value={form.patent_number}
                     onChange={(e) => setForm({ ...form, patent_number: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pat-class">Classification</label>
              <input id="pat-class" placeholder="e.g. H01M" value={form.classification}
                     onChange={(e) => setForm({ ...form, classification: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pat-domain">Technology domain</label>
              <input id="pat-domain" value={form.technology_domain}
                     onChange={(e) => setForm({ ...form, technology_domain: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pat-date">Filing date</label>
              <input id="pat-date" type="date" value={form.filing_date}
                     onChange={(e) => setForm({ ...form, filing_date: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="pat-cites">Citations</label>
              <input id="pat-cites" type="number" value={form.citation_count}
                     onChange={(e) => setForm({ ...form, citation_count: e.target.value })} />
            </div>
          </div>
          <div className="form-actions">
            <button type="submit">Add patent</button>
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
