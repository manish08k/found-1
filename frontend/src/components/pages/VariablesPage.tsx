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
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Variables</h1>
          <p className="text-sm text-gray-500 mt-1">Reusable values and secrets available across your workflows. Reference with <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">${'{'}VAR_NAME{'}'}</code></p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
          + Add Variable
        </button>
      </div>

      <div className="mb-4">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search variables…" className="w-full max-w-xs px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800 text-left">
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Value</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
              <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {variables.map((v: any) => (
              <tr key={v.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <code className="font-mono text-sm text-gray-900 dark:text-white">{v.name}</code>
                    {v.is_secret && <span className="px-1.5 py-0.5 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 rounded">secret</span>}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-sm text-gray-600 dark:text-gray-400">
                  {v.is_secret ? (
                    <div className="flex items-center gap-2">
                      <span>{showSecrets.has(v.id) ? v.value : '••••••••'}</span>
                      <button onClick={() => toggleReveal(v.id)} className="text-xs text-blue-500 hover:text-blue-600">{showSecrets.has(v.id) ? 'Hide' : 'Show'}</button>
                    </div>
                  ) : (
                    <span className="truncate max-w-xs inline-block">{v.value?.length > 60 ? v.value.slice(0, 60) + '…' : v.value}</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 rounded">{v.variable_type}</span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">{v.description}</td>
                <td className="px-4 py-3 text-right">
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => openEdit(v)} className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">Edit</button>
                    <button onClick={() => { if (confirm('Delete?')) deleteMut.mutate(v.id) }} className="text-xs text-red-400 hover:text-red-600">Del</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && variables.length === 0 && (
          <div className="py-12 text-center text-gray-400">
            <p className="text-4xl mb-3">📦</p>
            <p className="text-sm">{search ? 'No variables match your search.' : 'No variables yet. Create one to get started.'}</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{editId ? 'Edit Variable' : 'Add Variable'}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Variable name * (e.g. MY_API_KEY)" className="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <textarea value={form.value} onChange={e => setForm(f => ({ ...f, value: e.target.value }))} placeholder={editId && form.is_secret ? 'Leave empty to keep existing value' : 'Value *'} rows={3} className="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description (optional)" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.variable_type} onChange={e => setForm(f => ({ ...f, variable_type: e.target.value }))} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {VARIABLE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.is_secret} onChange={e => setForm(f => ({ ...f, is_secret: e.target.checked }))} className="rounded" />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Secret (encrypted)</span>
                </label>
              </div>
            </div>
            <div className="flex gap-3 mt-5 justify-end">
              <button onClick={() => { setFormOpen(false); setEditId(null) }} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={!form.name.trim() || (!form.value.trim() && !editId) || createMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Add')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
