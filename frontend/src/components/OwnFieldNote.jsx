import { Link } from 'react-router-dom'

import { isOwner } from '../roles'

export default function OwnFieldNote({ role, verb, detail }) {
  if (!isOwner(role)) {
    return (
      <p className="empty-note">
        Search a technology above to {verb} it, or pick one of the fields your
        innovators work in.
      </p>
    )
  }
  return (
    <>
      <p className="empty-note">
        {detail || `Search a technology above to ${verb} it.`}
      </p>
      <Link to="/portfolio" className="inline-link link-block">
        Add a technology area to your portfolio →
      </Link>
    </>
  )
}
