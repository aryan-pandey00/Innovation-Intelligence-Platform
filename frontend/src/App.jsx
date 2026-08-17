import { lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import ForgotPassword from './pages/ForgotPassword'
import Layout from './components/Layout'
import RequireAccess from './components/RequireAccess'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Profile = lazy(() => import('./pages/Profile'))
const Funding = lazy(() => import('./pages/Funding'))
const Trends = lazy(() => import('./pages/Trends'))
const PatentLandscape = lazy(() => import('./pages/PatentLandscape'))
const TechIntelligence = lazy(() => import('./pages/TechIntelligence'))
const Innovation = lazy(() => import('./pages/Innovation'))
const Commercialization = lazy(() => import('./pages/Commercialization'))
const Innovator = lazy(() => import('./pages/Innovator'))
const Reports = lazy(() => import('./pages/Reports'))
const Notifications = lazy(() => import('./pages/Notifications'))
const AdminPanel = lazy(() => import('./pages/AdminPanel'))
const AccountsPanel = lazy(() => import('./components/admin/AccountsPanel'))
const CataloguePanel = lazy(() => import('./components/admin/CataloguePanel'))
const SourcesPanel = lazy(() => import('./components/admin/SourcesPanel'))
const AnnouncementsPanel = lazy(() => import('./components/admin/AnnouncementsPanel'))
const ResetsPanel = lazy(() => import('./components/admin/ResetsPanel'))

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />

      <Route element={<RequireAccess><Layout /></RequireAccess>}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Navigate to="/profile" replace />} />
        <Route path="/funding" element={<Funding />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/patents" element={<PatentLandscape />} />
        <Route path="/technology" element={<TechIntelligence />} />
        <Route path="/innovation" element={<Innovation />} />
        <Route path="/innovator/:id" element={<Innovator />} />
        <Route path="/commercialization" element={<Commercialization />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/announcements" element={<AnnouncementsPanel />} />
        <Route path="/resets" element={<ResetsPanel />} />
        <Route path="/admin/resets" element={<Navigate to="/resets" replace />} />
        <Route path="/admin" element={<AdminPanel />}>
          <Route index element={<AccountsPanel />} />
          <Route path="funding" element={<CataloguePanel />} />
          <Route path="sources" element={<SourcesPanel />} />
        </Route>
      </Route>
    </Routes>
  )
}
