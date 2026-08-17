import TagRow from './TagRow'

const none = (text) => <span className="detail-none">{text}</span>

export default function ProfileDetail({ p }) {
  const org = [p.organization, p.country].filter(Boolean).join(' · ')

  return (
    <div className="profile-detail">
      <p className="detail-headline">{p.headline || none('No headline set')}</p>
      <p className="detail-bio">{p.bio || none('No bio written')}</p>
      <p className="detail-org">{org || none('No organisation or country set')}</p>

      <TagRow label="Research domains" items={p.research_domains}
              empty="none set — research trends fall back to a default query" />
      <TagRow label="Keywords" items={p.keywords} empty="none set" />
      <TagRow label="Technology areas" items={p.technology_areas}
              empty="none set — patent and technology analysis has nothing to run on" />

      <h3>Publications ({p.publications?.length || 0})</h3>
      {p.publications?.length > 0 ? (
        <div className="entry-cols">
          {p.publications.map((pub) => (
            <div key={pub.id} className="entry entry-stacked">
              <strong>{pub.title}</strong>
              <div className="entry-meta">
                {[pub.authors?.join(', '), pub.venue, pub.year].filter(Boolean).join(' · ')}
              </div>
            </div>
          ))}
        </div>
      ) : <p className="detail-none">None listed.</p>}

      <h3>Patents ({p.patents?.length || 0})</h3>
      {p.patents?.length > 0 ? (
        <div className="entry-cols">
          {p.patents.map((pat) => (
            <div key={pat.id} className="entry entry-stacked">
              <strong>{pat.title}</strong>
              <div className="entry-meta">
                {[pat.assignee, pat.patent_number, pat.technology_domain]
                  .filter(Boolean).join(' · ')}
              </div>
            </div>
          ))}
        </div>
      ) : <p className="detail-none">None listed.</p>}
    </div>
  )
}
