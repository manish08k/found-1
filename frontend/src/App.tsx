import React, { useEffect, useState } from 'react'
import { authApi } from './api/client'
import { useStore } from './store'
import LoginPage from './components/LoginPage'
import Dashboard from './components/Dashboard'

export default function App() {
  const { user, setUser } = useStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    // Handle OAuth callback params
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('connected')
    const error = params.get('error')
    if (connected) {
      window.history.replaceState({}, '', '/')
      setTimeout(() => {
        import('react-hot-toast').then(({ default: toast }) => toast.success(`${connected} connected!`))
      }, 500)
    }
    if (error) {
      window.history.replaceState({}, '', '/')
      setTimeout(() => {
        import('react-hot-toast').then(({ default: toast }) => toast.error(`OAuth error: ${error}`))
      }, 500)
    }

    const token = localStorage.getItem('token')
    if (!token) { setChecking(false); return }
    authApi.me()
      .then(u => { setUser(u); setChecking(false) })
      .catch(() => { localStorage.removeItem('token'); setChecking(false) })
  }, [])

  if (checking) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)', color: 'var(--text3)', fontSize: 13, gap: 10 }}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0" opacity={0.3}/><path d="M12 3a9 9 0 019 9"/>
      </svg>
      Loading…
    </div>
  )

  return user ? <Dashboard /> : <LoginPage />
}
