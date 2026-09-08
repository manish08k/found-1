import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiKeysApi } from '../../api/client'
import toast from 'react-hot-toast'

export default function ApiKeysPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', expires_at: '' })
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['api-keys'], queryFn: () => apiKeysApi.list() })
  const keys = data?.api_keys ?? []

  const createMut = useMutation({
    mutationFn: () => apiKeysApi.create({ name: form.name, description: form.description || undefined, expires_at: form.expires_at || undefined }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ['api-keys'] })
      setNewKeyValue(r.key)
      setFormOpen(false)
      setForm({ name: '', description: '', expires_at: '' })
    },
    onError: () => toast.error('Failed to create API key'),
  })

  const revokeMut = useMutation({
    mutationFn: (id: string) => apiKeysApi.revoke(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['api-keys'] }); toast.success('Key revoked') },
  })

  const rotateMut = useMutation({
    mutationFn: (id: string) => apiKeysApi.rotate(id),
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['api-keys'] }); setNewKeyValue(r.key); toast.success('Key rotated') },
    onError: () => toast.error('Failed to rotate key'),
  })

  function copyKey(key: string) { navigator.clipboard.writeText(key); toast.success('Copied to clipboard') }

  return (
    <div className="page-fade" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 20px', flexShrink: 0, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>API Keys</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Keys for authenticating programmatic access to your AutoFlow instance</p>
        </div>
        <button onClick={() => setFormOpen(true)} style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}>
          + Create Key
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '20px 32px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* One-time key display */}
        {newKeyValue && (
          <div style={{ padding: '14px 16px', background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--green)', marginBottom: 8 }}>
              Your API key — copy it now, you won't see it again
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <code style={{ flex: 1, fontFamily: 'var(--mono)', fontSize: 12, background: 'var(--bg)', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', color: 'var(--text)', overflow: 'auto', whiteSpace: 'nowrap' }}>
                {newKeyValue}
              </code>
              <button onClick={() => copyKey(newKeyValue)} style={{ padding: '7px 12px', background: 'var(--green)', border: 'none', color: '#fff', borderRadius: 7, fontSize: 12, cursor: 'pointer', flexShrink: 0 }}>Copy</button>
              <button onClick={() => setNewKeyValue(null)} style={{ padding: '7px 12px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 7, fontSize: 12, cursor: 'pointer', flexShrink: 0 }}>Dismiss</button>
            </div>
          </div>
        )}

        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}

        {!isLoading && keys.length === 0 && (
          <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text3)', fontSize: 13 }}>
            No API keys yet. Create one to get started.
          </div>
        )}

        {keys.map((k: any) => (
          <div key={k.id} style={{
            padding: '14px 16px',
            background: 'var(--bg2)',
            border: `1px solid ${k.revoked ? 'rgba(239,68,68,0.3)' : 'var(--border)'}`,
            borderRadius: 10,
            opacity: k.revoked ? 0.6 : 1,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{k.name}</span>
                  {k.revoked && (
                    <span style={{ padding: '1px 7px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', borderRadius: 10, fontSize: 10, fontWeight: 700 }}>REVOKED</span>
                  )}
                </div>
                {k.description && <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 4 }}>{k.description}</div>}
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
                    Prefix: <span style={{ color: 'var(--text2)' }}>{k.key_prefix}…</span>
                  </span>
                  {k.last_used_at && (
                    <span style={{ fontSize: 11, color: 'var(--text3)' }}>Last used: {new Date(k.last_used_at).toLocaleDateString()}</span>
                  )}
                  {k.expires_at && (
                    <span style={{ fontSize: 11, color: 'var(--text3)' }}>Expires: {new Date(k.expires_at).toLocaleDateString()}</span>
                  )}
                </div>
              </div>
              {!k.revoked && (
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button onClick={() => { if (confirm('Rotate this key? The old key will stop working immediately.')) rotateMut.mutate(k.id) }}
                    style={{ padding: '4px 10px', background: 'rgba(124,58,237,0.1)', color: 'var(--accent)', border: 'none', borderRadius: 6, fontSize: 11, cursor: 'pointer' }}>
                    Rotate
                  </button>
                  <button onClick={() => { if (confirm('Revoke this key? This cannot be undone.')) revokeMut.mutate(k.id) }}
                    style={{ padding: '4px 10px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', border: 'none', borderRadius: 6, fontSize: 11, cursor: 'pointer' }}>
                    Revoke
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create Modal */}
      {formOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>Create API Key</h2>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Key name *" />
            <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description (optional)" />
            <div>
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Expiry (optional)</div>
              <input type="date" value={form.expires_at} onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))} />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button onClick={() => { setFormOpen(false); setForm({ name: '', description: '', expires_at: '' }) }}
                style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => createMut.mutate()} disabled={!form.name.trim() || createMut.isPending}
                style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (!form.name.trim() || createMut.isPending) ? 0.5 : 1 }}>
                {createMut.isPending ? 'Creating…' : 'Create Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
