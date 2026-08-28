import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workflowsApi } from '../api/client'
import { useStore } from '../store'
import toast from 'react-hot-toast'
import type { Workflow } from '../types'

export default function WorkflowList() {
  const qc = useQueryClient()
  const { setActiveWorkflow, setPage } = useStore()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')

  const { data, isLoading } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list })
  const workflows: Workflow[] = data?.workflows ?? []

  const createMut = useMutation({
    mutationFn: (n: string) => workflowsApi.create({ name: n, definition: { nodes: [], edges: [] } }),
    onSuccess: wf => { qc.invalidateQueries({ queryKey: ['workflows'] }); setActiveWorkflow(wf); setCreating(false); setName('') },
    onError: () => toast.error('Failed to create'),
  })

  const deleteMut = useMutation({
    mutationFn: workflowsApi.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['workflows'] }); toast.success('Deleted') },
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      active ? workflowsApi.deactivate(id) : workflowsApi.activate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workflows'] }),
  })

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 32 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Workflows</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>{workflows.length} workflow{workflows.length !== 1 ? 's' : ''}</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => setPage('marketplace')} title="Browse ready-made templates you can install and customize"
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 8, fontWeight: 600, fontSize: 13, border: '1px solid var(--border)', cursor: 'pointer' }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 3h18l-2 9H5L3 3z"/><circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/></svg>
            Browse Templates
          </button>
          <button onClick={() => setCreating(true)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 18px', background: 'var(--accent)', color: '#fff', borderRadius: 8, fontWeight: 600, fontSize: 13, border: 'none', cursor: 'pointer' }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Workflow
          </button>
        </div>
      </div>

      {/* Create modal */}
      {creating && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }} onClick={e => { if (e.target === e.currentTarget) setCreating(false) }}>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 28, width: 380 }}>
            <h3 style={{ marginBottom: 16, fontWeight: 600, color: 'var(--text)' }}>New Workflow</h3>
            <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="Workflow name"
              onKeyDown={e => { if (e.key === 'Enter' && name.trim()) createMut.mutate(name.trim()); if (e.key === 'Escape') setCreating(false) }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setCreating(false)} style={{ padding: '8px 16px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => name.trim() && createMut.mutate(name.trim())} disabled={!name.trim() || createMut.isPending}
                style={{ padding: '8px 16px', background: 'var(--accent)', color: '#fff', borderRadius: 8, fontWeight: 600, opacity: !name.trim() ? 0.5 : 1, border: 'none', cursor: 'pointer' }}>
                {createMut.isPending ? 'Creating…' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}

      {/* Empty state */}
      {!isLoading && workflows.length === 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 320, color: 'var(--text3)', gap: 14 }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity={0.3}><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          <p style={{ fontSize: 15 }}>No workflows yet</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setPage('marketplace')} style={{ padding: '9px 20px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 8, fontWeight: 600, border: '1px solid var(--border)', cursor: 'pointer' }}>
              Browse Templates
            </button>
            <button onClick={() => setCreating(true)} style={{ padding: '9px 20px', background: 'var(--accent)', color: '#fff', borderRadius: 8, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
              Create your first workflow
            </button>
          </div>
        </div>
      )}

      {/* Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
        {workflows.map(wf => (
          <div key={wf.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: 18, transition: 'border-color 0.15s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border2)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => setActiveWorkflow(wf)}>
                <h3 style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)', marginBottom: 4 }}>{wf.name}</h3>
                <p style={{ color: 'var(--text3)', fontSize: 12 }}>{wf.definition?.nodes?.length ?? 0} nodes · {new Date(wf.updated_at).toLocaleDateString()}</p>
              </div>
              <span style={{ padding: '2px 9px', borderRadius: 12, fontSize: 10, fontWeight: 700,
                color: wf.status === 'active' ? 'var(--green)' : wf.status === 'error' ? 'var(--red)' : 'var(--text3)',
                background: wf.status === 'active' ? 'rgba(34,197,94,0.12)' : wf.status === 'error' ? 'rgba(239,68,68,0.12)' : 'var(--bg3)' }}>
                {wf.status}
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setActiveWorkflow(wf)} style={{ flex: 1, padding: '7px 0', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 7, fontSize: 12, fontWeight: 500, border: '1px solid var(--border)', cursor: 'pointer' }}>Edit</button>
              <button onClick={() => toggleMut.mutate({ id: wf.id, active: wf.status === 'active' })}
                style={{ flex: 1, padding: '7px 0', background: wf.status === 'active' ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)', color: wf.status === 'active' ? 'var(--red)' : 'var(--green)', borderRadius: 7, fontSize: 12, fontWeight: 500, border: 'none', cursor: 'pointer' }}>
                {wf.status === 'active' ? 'Deactivate' : 'Activate'}
              </button>
              <button onClick={() => { if (confirm('Delete this workflow?')) deleteMut.mutate(wf.id) }}
                style={{ width: 32, height: 32, background: 'transparent', color: 'var(--text3)', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border)', cursor: 'pointer' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/></svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
