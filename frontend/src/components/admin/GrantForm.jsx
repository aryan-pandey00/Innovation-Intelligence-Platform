import { useState } from 'react'

import TagInput from '../profile/TagInput'
import { OWNERS, ROLE_LABEL } from '../../roles'
import { Card } from '../ui'
import { SOURCE_LABELS } from '../ui/format'

const BLANK = {
  title: '', agency: '', source_type: 'government_grant', description: '',
  domains: [], keywords: [], eligible_roles: [], countries: [],
  amount_min: '', amount_max: '', currency: 'USD', deadline: '', url: '',
}

const today = () => new Date().toISOString().slice(0, 10)

export default function GrantForm({ value, onSave, onCancel, busy, error }) {
  const [form, setForm] = useState(() => ({
    ...BLANK,
    ...(value || {}),
    amount_min: value?.amount_min ?? '',
    amount_max: value?.amount_max ?? '',
    deadline: value?.deadline ?? '',
    url: value?.url ?? '',
    currency: value?.currency ?? 'USD',
  }))

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  const setList = (field) => (items) => setForm((f) => ({ ...f, [field]: items }))

  const min = form.amount_min === '' ? null : Number(form.amount_min)
  const max = form.amount_max === '' ? null : Number(form.amount_max)
  const reversed = min != null && max != null && min > max
  const past = form.deadline !== '' && form.deadline < today()
  const untagged = form.domains.length === 0 && form.keywords.length === 0
  const ready = form.title.trim() && form.agency.trim() && form.description.trim()
    && !reversed

  const submit = (e) => {
    e.preventDefault()
    if (!ready || busy) return
    onSave({
      ...form,
      amount_min: min, amount_max: max,
      deadline: form.deadline || null,
      url: form.url.trim() || null,
    })
  }

  const toggleRole = (role) => setForm((f) => ({
    ...f,
    eligible_roles: f.eligible_roles.includes(role)
      ? f.eligible_roles.filter((r) => r !== role)
      : [...f.eligible_roles, role],
  }))

  return (
    <Card title={value?.id ? 'Edit grant' : 'Add a grant'}
          aside={<button className="mini-view" onClick={onCancel}>Cancel</button>}>
      <form onSubmit={submit}>
        {error && <div className="error">{error}</div>}

        <div className="field">
          <label htmlFor="g-title">Title</label>
          <input id="g-title" value={form.title} onChange={set('title')} required />
        </div>
        <div className="grid-2">
          <div className="field">
            <label htmlFor="g-agency">Funding agency</label>
            <input id="g-agency" value={form.agency} onChange={set('agency')} required />
          </div>
          <div className="field">
            <label htmlFor="g-type">Type</label>
            <select id="g-type" value={form.source_type} onChange={set('source_type')}>
              {Object.entries(SOURCE_LABELS).map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="g-desc">Description</label>
          <textarea id="g-desc" rows={3} value={form.description}
                    onChange={set('description')} required />
        </div>

        <div className="grid-2">
          <div className="field">
            <label htmlFor="g-min">Amount from</label>
            <input id="g-min" type="number" min="0" value={form.amount_min}
                   onChange={set('amount_min')} placeholder="Leave blank if not stated" />
          </div>
          <div className="field">
            <label htmlFor="g-max">Amount up to</label>
            <input id="g-max" type="number" min="0" value={form.amount_max}
                   onChange={set('amount_max')} placeholder="Leave blank if not stated" />
          </div>
          <div className="field">
            <label htmlFor="g-cur">Currency</label>
            <input id="g-cur" value={form.currency} onChange={set('currency')} />
          </div>
          <div className="field">
            <label htmlFor="g-deadline">Deadline</label>
            <input id="g-deadline" type="date" value={form.deadline}
                   onChange={set('deadline')} />
          </div>
        </div>
        {reversed && (
          <p className="field-help warn">
            The lower amount is above the upper one, so this would list as a
            backwards range.
          </p>
        )}
        {past && !reversed && (
          <p className="field-help warn">
            This date has passed, so the grant is ineligible for everyone until it
            is changed.
          </p>
        )}

        <div className="field">
          <label htmlFor="g-url">Link</label>
          <input id="g-url" value={form.url} onChange={set('url')}
                 placeholder="https://…" />
        </div>

        <TagInput label="Domains" tags={form.domains} onChange={setList('domains')}
                  placeholder="energy systems" />
        <TagInput label="Keywords" tags={form.keywords} onChange={setList('keywords')}
                  placeholder="grid, storage" />
        <p className="field-help">
          Domains and keywords are what a portfolio is matched against, and they
          carry most of the relevance score. A grant with none can only match on
          its description text, which rarely clears the bar — the usual reason a
          grant reaches nobody.
        </p>
        {untagged && (
          <p className="field-help warn">
            No domains or keywords yet, so this grant will almost certainly reach
            nobody.
          </p>
        )}

        <TagInput label="Countries" tags={form.countries} onChange={setList('countries')}
                  placeholder="United States" />
        <p className="field-help">Leave empty for any country.</p>

        <div className="field">
          <label>Open to</label>
          {OWNERS.map((role) => (
            <label key={role} className="checkbox-row">
              <input type="checkbox" checked={form.eligible_roles.includes(role)}
                     onChange={() => toggleRole(role)} />
              {ROLE_LABEL[role]}
            </label>
          ))}
          <p className="field-help">
            Leave both unticked to open it to any applicant.
          </p>
        </div>

        <div className="form-actions">
          <button type="submit" className="save-btn" disabled={!ready || busy}>
            {busy ? 'Saving…' : (value?.id ? 'Save changes' : 'Add grant')}
          </button>
        </div>
      </form>
    </Card>
  )
}
