import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { variablesApi } from '../../api/client'
import toast from 'react-hot-toast'

const VARIABLE_TYPES = ['string', 'number', 'boolean', 'json']

const EMPTY_FORM = { name: '', value: '', description: '', is_secret: false, variable_type: 'string' }

export default function VariablesPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [search, setSearch] = useState('')
  const [showSecrets, setShowSecrets] = useState<Set<string>>(new Set())

  const { data, isLoading } = useQuery({ queryKey: ['variables'], queryFn: () => variablesApi.list() })
  const variables = (data?.variables ?? []).filter((v: any) =>
    !search || v.name.toLowerCase().includes(search.toLowerCase()) || (v.description ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const createMut = useMutation({
    mutationFn: (d: any) => editId ? variablesApi.update(editId, d) : variablesApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['variables'] }); setFormOpen(false); setEditId(null); setForm({ ...EMPTY_FORM }); toast.success(editId ? 'Updated' : 'Created') },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? 'Failed to save'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => variablesApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['variables'] }); toast.success('Deleted') },
  })

  function openCreate() { setEditId(null); setForm({ ...EMPTY_FORM }); setFormOpen(true) }
  function openEdit(v: any) { setEditId(v.id); setForm({ name: v.name, value: v.is_secret ? '' : v.value, description: v.description ?? '', is_secret: v.is_secret, variable_type: v.variable_type }); setFormOpen(true) }
  function toggleReveal(id: string) { setShowSecrets(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n }) }

  return (
    <div className="page-fade" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 20px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Variables</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>
              Reusable values and secrets. Reference with{' '}
              <code style={{ fontFamily: 'var(--mono)', fontSize: 11, background: 'var(--bg3)', padding: '1px 5px', borderRadius: 4, color: 'var(--accent)' }}>{'${VAR_NAME}'}</code>
            </p>
          </div>
          <button onClick={openCreate} style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}>
            + Add Variable
          </button>
        </div>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search variables…" style={{ maxWidth: 280 }} />
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 24px' }}>
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: 8 }}>Loading…</div>}
        {!isLoading && variables.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text3)', fontSize: 13 }}>
            {search ? 'No variables match your search.' : 'No variables yet. Create one to get started.'}
          </div>
        ) : (
          <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: 'var(--bg2)' }}>
                  {['Name', 'Value', 'Type', 'Description', ''].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {variables.map((v: any) => (
                  <tr key={v.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <code style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text)', fontWeight: 600 }}>{v.name}</code>
                        {v.is_secret && (
                          <span style={{ padding: '1px 6px', fontSize: 10, background: 'rgba(245,158,11,0.12)', color: 'var(--yellow)', borderRadius: 4, fontWeight: 600 }}>secret</span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)', maxWidth: 240 }}>
                      {v.is_secret ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span>{showSecrets.has(v.id) ? v.value : '••••••••'}</span>
                          <button onClick={() => toggleReveal(v.id)} style={{ padding: '1px 6px', background: 'transparent', border: 'none', color: 'var(--accent)', fontSize: 10, cursor: 'pointer' }}>
                            {showSecrets.has(v.id) ? 'Hide' : 'Show'}
                          </button>
                        </div>
                      ) : (
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>
                          {v.value?.length > 60 ? v.value.slice(0, 60) + '…' : v.value}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                      <span style={{ padding: '2px 7px', background: 'var(--bg3)', color: 'var(--text3)', borderRadius: 4, fontSize: 11 }}>{v.variable_type}</span>
                    </td>
                    <td style={{ padding: '10px 14px', color: 'var(--text3)', fontSize: 12 }}>{v.description}</td>
                    <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                        <button onClick={() => openEdit(v)} style={{ padding: '3px 8px', background: 'transparent', border: 'none', color: 'var(--text3)', fontSize: 11, cursor: 'pointer' }}>Edit</button>
                        <button onClick={() => { if (confirm('Delete?')) deleteMut.mutate(v.id) }} style={{ padding: '3px 8px', background: 'transparent', border: 'none', color: 'var(--red)', fontSize: 11, cursor: 'pointer' }}>Del</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{editId ? 'Edit Variable' : 'Add Variable'}</h2>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Variable name * (e.g. MY_API_KEY)" style={{ fontFamily: 'var(--mono)' }} />
            <textarea value={form.value} onChange={e => setForm(f => ({ ...f, value: e.target.value }))}
              placeholder={editId && form.is_secret ? 'Leave empty to keep existing value' : 'Value *'}
              rows={3} style={{ fontFamily: 'var(--mono)' }} />
            <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description (optional)" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, alignItems: 'center' }}>
              <select value={form.variable_type} onChange={e => setForm(f => ({ ...f, variable_type: e.target.value }))}>
                {VARIABLE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text2)' }}>
                <input type="checkbox" checked={form.is_secret} onChange={e => setForm(f => ({ ...f, is_secret: e.target.checked }))} style={{ width: 'auto', cursor: 'pointer' }} />
                Secret (encrypted)
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button onClick={() => { setFormOpen(false); setEditId(null) }} style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={!form.name.trim() || (!form.value.trim() && !editId) || createMut.isPending}
                style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (!form.name.trim() || (!form.value.trim() && !editId) || createMut.isPending) ? 0.5 : 1 }}>
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Add')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
