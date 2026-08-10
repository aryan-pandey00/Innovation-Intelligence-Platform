import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Portfolio from './pages/Portfolio'
import Profile from './pages/Profile'
import Funding from './pages/Funding'
import Trends from './pages/Trends'
import PatentLandscape from './pages/PatentLandscape'
import TechIntelligence from './pages/TechIntelligence'
import Innovation from './pages/Innovation'
import Commercialization from './pages/Commercialization'
import AdminPanel from './pages/AdminPanel'
import Layout from './components/Layout'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" />
}

function AdminRoute({ children }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" />
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  return user.role === 'admin' ? children : <Navigate to="/dashboard" />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<Layout />}>
        <Route path="/dashboard" element={
          <ProtectedRoute><Dashboard /></ProtectedRoute>
        } />
        <Route path="/portfolio" element={
          <ProtectedRoute><Portfolio /></ProtectedRoute>
        } />
        {/* Not /settings: this page holds a display name, email, role, organisation,
            country, ORCID and account deletion, none of which is a setting. */}
        <Route path="/profile" element={
          <ProtectedRoute><Profile /></ProtectedRoute>
        } />
        <Route path="/settings" element={<Navigate to="/profile" replace />} />
        <Route path="/funding" element={
          <ProtectedRoute><Funding /></ProtectedRoute>
        } />
        <Route path="/trends" element={
          <ProtectedRoute><Trends /></ProtectedRoute>
        } />
        <Route path="/patents" element={
          <ProtectedRoute><PatentLandscape /></ProtectedRoute>
        } />
        <Route path="/technology" element={
          <ProtectedRoute><TechIntelligence /></ProtectedRoute>
        } />
        <Route path="/innovation" element={
          <ProtectedRoute><Innovation /></ProtectedRoute>
        } />
        <Route path="/commercialization" element={
          <ProtectedRoute><Commercialization /></ProtectedRoute>
        } />
        <Route path="/admin" element={
          <AdminRoute><AdminPanel /></AdminRoute>
        } />
      </Route>
    </Routes>
  )
}
