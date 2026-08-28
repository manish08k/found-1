import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { leadsApi } from '../../api/client'
import toast from 'react-hot-toast'

const STATUS_OPTIONS = ['new', 'contacted', 'qualified', 'converted', 'lost']
const STATUS_COLORS: Record<string, string> = {
  new: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  contacted: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
  qualified: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
  converted: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  lost: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
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
    !search || [l.name, l.email, l.phone].some(f => f?.toLowerCase().includes(search.toLowerCase()))
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
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Leads</h1>
          <p className="text-sm text-gray-500 mt-1">Contacts captured by your chat workflows.</p>
        </div>
        <div className="flex gap-3">
          <button onClick={exportCsv} className="px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-sm font-medium">
            Export CSV
          </button>
          <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
            + Add Lead
          </button>
        </div>
      </div>

      <div className="flex gap-3 mb-4 flex-wrap">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, email, phone…" className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 text-left">
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {leads.map((l: any) => (
              <tr key={l.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">{l.name ?? '—'}</td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{l.email ?? '—'}</td>
                <td className="px-4 py-3 text-gray-600 dark:text-gray-400">{l.phone ?? '—'}</td>
                <td className="px-4 py-3">
                  <select value={l.status} onChange={e => statusMut.mutate({ id: l.id, status: e.target.value })}
                    className={`text-xs font-medium px-2 py-1 rounded-full border-0 cursor-pointer ${STATUS_COLORS[l.status] ?? ''}`}>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">{l.created_at ? new Date(l.created_at).toLocaleDateString() : '—'}</td>
                <td className="px-4 py-3 text-right">
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => openEdit(l)} className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">Edit</button>
                    <button onClick={() => { if (confirm('Delete lead?')) deleteMut.mutate(l.id) }} className="text-xs text-red-400 hover:text-red-600">Del</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && leads.length === 0 && (
          <div className="py-12 text-center text-gray-400">
            <p className="text-4xl mb-3">👤</p>
            <p className="text-sm">{search || statusFilter ? 'No leads match your filter.' : 'No leads yet. They will appear here when captured by workflows.'}</p>
          </div>
        )}
      </div>

      {data?.total > 20 && (
        <div className="flex justify-center gap-3 mt-4">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-40">Previous</button>
          <span className="text-sm text-gray-500 self-center">Page {page}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={leads.length < 20} className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg disabled:opacity-40">Next</button>
        </div>
      )}

      {/* Create/Edit Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{editId ? 'Edit Lead' : 'Add Lead'}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Full name" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="Email address" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="Phone number" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="flex gap-3 mt-5 justify-end">
              <button onClick={() => { setFormOpen(false); setEditId(null) }} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={(!form.name && !form.email) || createMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Add Lead')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
