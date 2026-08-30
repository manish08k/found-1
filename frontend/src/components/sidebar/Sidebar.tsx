import React from 'react'
import { useStore } from '../../store'
import { authApi } from '../../api/client'

const NAV = [
  {
    group: 'Build',
    items: [
      {
        id: 'workflows', label: 'Workflows',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
      },
      {
        id: 'ai-builder', label: 'AI Builder',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      },
      {
        id: 'agentflow', label: 'AgentFlow',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
      },
    ]
  },
  {
    group: 'Data',
    items: [
      {
        id: 'document-stores', label: 'Knowledge Bases',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="15" y2="17"/></svg>
      },
      {
        id: 'mcp', label: 'MCP Servers',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
      },
      {
        id: 'assistants', label: 'Assistants',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/><circle cx="18" cy="8" r="2"/></svg>
      },
    ]
  },
  {
    group: 'Ops',
    items: [
      {
        id: 'executions', label: 'Executions',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      },
      {
        id: 'debugger', label: 'Debugger',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      },
      {
        id: 'approvals', label: 'Approvals',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
      },
      {
        id: 'versions', label: 'Versions',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
      },
    ]
  },
  {
    group: 'Quality',
    items: [
      {
        id: 'evaluations', label: 'Evaluations',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
      },
      {
        id: 'policies', label: 'Guardrails',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      },
      {
        id: 'costs', label: 'Cost & Routing',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
      },
    ]
  },
  {
    group: 'Settings',
    items: [
      {
        id: 'credentials', label: 'Credentials',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
      },
      {
        id: 'marketplace', label: 'Marketplace',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 3h18l-2 9H5L3 3z"/><circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/></svg>
      },
      {
        id: 'api-keys', label: 'API Keys',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
      },
      {
        id: 'variables', label: 'Variables',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
      },
      {
        id: 'pricing', label: 'Pricing',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
      },
      {
        id: 'leads', label: 'Leads',
        icon: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
      },
    ]
  },
]

// Flattened list for nav lookups
const ALL_NAV = NAV.flatMap(g => g.items)

export default function Sidebar() {
  const { setUser, setActiveWorkflow, page, setPage } = useStore()
  const logout = () => { authApi.logout().finally(() => setUser(null)) }

  const handleNav = (id: string) => {
    setActiveWorkflow(null)
    setPage(id as any)
  }

  return (
    <nav style={{ width: 52, background: 'var(--bg1)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 0', gap: 2, flexShrink: 0, zIndex: 10, overflowY: 'auto' }}>
      {/* Logo */}
      <div style={{ width: 32, height: 32, background: 'var(--accent)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 8 }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
      </div>

      {NAV.map((group, gi) => (
        <React.Fragment key={group.group}>
          {gi > 0 && <div style={{ width: 28, height: 1, background: 'var(--border)', margin: '4px 0' }} />}
          {group.items.map(n => (
            <button key={n.id} title={n.label} aria-label={n.label} aria-current={page === n.id ? 'page' : undefined}
              onClick={() => handleNav(n.id)}
              style={{ width: 36, height: 36, borderRadius: 8, background: page === n.id ? 'var(--accent)' : 'transparent', color: page === n.id ? '#fff' : 'var(--text3)', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 0.15s', border: 'none', cursor: 'pointer', flexShrink: 0 }}>
              {n.icon}
            </button>
          ))}
        </React.Fragment>
      ))}

      <div style={{ flex: 1 }} />

      <button title="Logout" aria-label="Log out" onClick={logout}
        style={{ width: 36, height: 36, borderRadius: 8, background: 'transparent', color: 'var(--text3)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', cursor: 'pointer' }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      </button>
    </nav>
  )
}
