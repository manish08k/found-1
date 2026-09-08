import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { leadsApi } from '../../api/client'
import toast from 'react-hot-toast'

const STATUS_OPTIONS = ['new', 'contacted', 'qualified', 'converted', 'lost']
const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  new:       { color: 'var(--blue)',   bg: 'rgba(59,130,246,0.12)' },
  contacted: { color: 'var(--accent)', bg: 'rgba(124,58,237,0.12)' },
  qualified: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  converted: { color: 'var(--green)',  bg: 'rgba(34,197,94,0.12)'  },
  lost:      { color: 'var(--red)',    bg: 'rgba(239,68,68,0.12)'  },
}

const EMPTY_FORM = { name: '', email: '', phone: '', status: 'new', workflow_id: '', conversation_id: '' }

export default function LeadsPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['leads', statusFilter, page],
    queryFn: () => leadsApi.list({ status: statusFilter || undefined, page, page_size: 20 }),
  })
  const leads = (data?.leads ?? []).filter((l: any) =>
    !search || [l.name, l.email, l.phone].some((f: any) => f?.toLowerCase().includes(search.toLowerCase()))
  )

  const createMut = useMutation({
    mutationFn: (d: any) => editId ? leadsApi.update(editId, d) : leadsApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['leads'] }); setFormOpen(false); setEditId(null); setForm({ ...EMPTY_FORM }); toast.success(editId ? 'Updated' : 'Lead created') },
    onError: () => toast.error('Failed to save'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => leadsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['leads'] }); toast.success('Deleted') },
  })

  const statusMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => leadsApi.update(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['leads'] }),
    onError: () => toast.error('Failed to update status'),
  })

  async function exportCsv() {
    try {
      const blob = await leadsApi.exportCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'leads.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Export failed') }
  }

  function openCreate() { setEditId(null); setForm({ ...EMPTY_FORM }); setFormOpen(true) }
  function openEdit(l: any) { setEditId(l.id); setForm({ name: l.name ?? '', email: l.email ?? '', phone: l.phone ?? '', status: l.status, workflow_id: l.workflow_id ?? '', conversation_id: l.conversation_id ?? '' }); setFormOpen(true) }

  return (
    <div className="page-fade" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 20px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Leads</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Contacts captured by your chat workflows</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={exportCsv} style={{ padding: '7px 14px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>
              Export CSV
            </button>
            <button onClick={openCreate} style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
              + Add Lead
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, email, phone…" style={{ maxWidth: 240 }} />
          <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }} style={{ maxWidth: 160 }}>
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 24px' }}>
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: 8 }}>Loading…</div>}

        {!isLoading && leads.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '64px 0', color: 'var(--text3)', fontSize: 13 }}>
            {search || statusFilter ? 'No leads match your filter.' : 'No leads yet. They will appear here when captured by workflows.'}
          </div>
        ) : (
          <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: 'var(--bg2)' }}>
                  {['Name', 'Email', 'Phone', 'Status', 'Created', ''].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {leads.map((l: any) => {
                  const s = STATUS_STYLE[l.status] ?? STATUS_STYLE.new
                  return (
                    <tr key={l.id} style={{ borderTop: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text)' }}>{l.name ?? '—'}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text2)' }}>{l.email ?? '—'}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--text2)' }}>{l.phone ?? '—'}</td>
                      <td style={{ padding: '10px 14px' }}>
                        <select value={l.status} onChange={e => statusMut.mutate({ id: l.id, status: e.target.value })}
                          style={{ padding: '2px 7px', borderRadius: 10, fontSize: 10, fontWeight: 700, color: s.color, background: s.bg, border: 'none', cursor: 'pointer', width: 'auto', textTransform: 'capitalize' }}>
                          {STATUS_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--text3)', whiteSpace: 'nowrap' }}>
                        {l.created_at ? new Date(l.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                          <button onClick={() => openEdit(l)} style={{ padding: '3px 8px', background: 'transparent', border: 'none', color: 'var(--text3)', fontSize: 11, cursor: 'pointer' }}>Edit</button>
                          <button onClick={() => { if (confirm('Delete lead?')) deleteMut.mutate(l.id) }} style={{ padding: '3px 8px', background: 'transparent', border: 'none', color: 'var(--red)', fontSize: 11, cursor: 'pointer' }}>Del</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {(data as any)?.total > 20 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 16 }}>
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              style={{ padding: '5px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 7, fontSize: 12, cursor: 'pointer', opacity: page === 1 ? 0.4 : 1 }}>
              Previous
            </button>
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>Page {page}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={leads.length < 20}
              style={{ padding: '5px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 7, fontSize: 12, cursor: 'pointer', opacity: leads.length < 20 ? 0.4 : 1 }}>
              Next
            </button>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 440, boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{editId ? 'Edit Lead' : 'Add Lead'}</h2>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Full name" />
            <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="Email address" />
            <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="Phone number" />
            <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))}>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button onClick={() => { setFormOpen(false); setEditId(null) }} style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={(!form.name && !form.email) || createMut.isPending}
                style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: ((!form.name && !form.email) || createMut.isPending) ? 0.5 : 1 }}>
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Add Lead')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
