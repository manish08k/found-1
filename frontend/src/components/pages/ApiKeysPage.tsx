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
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">API Keys</h1>
          <p className="text-sm text-gray-500 mt-1">Keys for authenticating programmatic access to your AutoFlow instance.</p>
        </div>
        <button onClick={() => setFormOpen(true)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
          + Create Key
        </button>
      </div>

      {/* One-time key display */}
      {newKeyValue && (
        <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-xl">
          <p className="text-sm font-semibold text-green-800 dark:text-green-300 mb-2">Your API key (copy it now — you won't see it again)</p>
          <div className="flex items-center gap-3">
            <code className="flex-1 text-sm font-mono bg-white dark:bg-gray-900 px-3 py-2 rounded-lg border border-green-300 dark:border-green-600 text-green-900 dark:text-green-100">{newKeyValue}</code>
            <button onClick={() => copyKey(newKeyValue)} className="px-3 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">Copy</button>
            <button onClick={() => setNewKeyValue(null)} className="px-3 py-2 text-green-700 dark:text-green-400 text-sm hover:bg-green-100 dark:hover:bg-green-900/40 rounded-lg">Dismiss</button>
          </div>
        </div>
      )}

      {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}

      <div className="space-y-3">
        {keys.map((k: any) => (
          <div key={k.id} className={`p-4 rounded-xl border ${k.revoked ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10 opacity-60' : 'border-gray-200 dark:border-gray-700'}`}>
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-gray-900 dark:text-white text-sm">{k.name}</h3>
                  {k.revoked && <span className="px-2 py-0.5 text-xs bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 rounded-full">Revoked</span>}
                </div>
                {k.description && <p className="text-xs text-gray-400 mt-0.5">{k.description}</p>}
                <div className="flex gap-4 mt-1">
                  <span className="text-xs text-gray-500 font-mono">Prefix: <code>{k.key_prefix}…</code></span>
                  {k.last_used_at && <span className="text-xs text-gray-400">Last used: {new Date(k.last_used_at).toLocaleDateString()}</span>}
                  {k.expires_at && <span className="text-xs text-gray-400">Expires: {new Date(k.expires_at).toLocaleDateString()}</span>}
                </div>
              </div>
              {!k.revoked && (
                <div className="flex gap-2">
                  <button onClick={() => { if (confirm('Rotate this key? The old key will stop working immediately.')) rotateMut.mutate(k.id) }} className="text-xs text-blue-600 hover:text-blue-700 px-2 py-1 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded">Rotate</button>
                  <button onClick={() => { if (confirm('Revoke this key? This cannot be undone.')) revokeMut.mutate(k.id) }} className="text-xs text-red-500 hover:text-red-600 px-2 py-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">Revoke</button>
                </div>
              )}
            </div>
          </div>
        ))}
        {!isLoading && keys.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-4xl mb-3">🔑</p>
            <p className="text-sm">No API keys yet. Create one to get started.</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Create API Key</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Key name *" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description (optional)" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Expiry (optional)</label>
                <input type="date" value={form.expires_at} onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div className="flex gap-3 mt-5 justify-end">
              <button onClick={() => { setFormOpen(false); setForm({ name: '', description: '', expires_at: '' }) }} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate()} disabled={!form.name.trim() || createMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                {createMut.isPending ? 'Creating…' : 'Create Key'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
