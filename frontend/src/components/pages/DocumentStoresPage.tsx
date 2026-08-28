import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentStoresApi } from '../../api/client'
import toast from 'react-hot-toast'

const EMBEDDING_PROVIDERS = ['openai', 'cohere', 'huggingface', 'ollama']
const EMBEDDING_MODELS: Record<string, string[]> = {
  openai: ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
  cohere: ['embed-english-v3.0', 'embed-multilingual-v3.0'],
  huggingface: ['sentence-transformers/all-MiniLM-L6-v2', 'sentence-transformers/all-mpnet-base-v2'],
  ollama: ['nomic-embed-text', 'mxbai-embed-large'],
}

const EMPTY_FORM = { name: '', description: '', embedding_provider: 'openai', embedding_model: 'text-embedding-3-small', chunk_size: 1000, chunk_overlap: 200 }

export default function DocumentStoresPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [selected, setSelected] = useState<any | null>(null)
  const [queryText, setQueryText] = useState('')
  const [queryResults, setQueryResults] = useState<any[]>([])
  const [upsertText, setUpsertText] = useState('')
  const [activeTab, setActiveTab] = useState<'chunks' | 'query' | 'upsert'>('chunks')

  const { data, isLoading } = useQuery({ queryKey: ['document-stores'], queryFn: () => documentStoresApi.list() })
  const stores = data?.document_stores ?? []

  const { data: chunksData } = useQuery({
    queryKey: ['doc-chunks', selected?.id],
    queryFn: () => documentStoresApi.listChunks(selected!.id),
    enabled: !!selected && activeTab === 'chunks',
  })
  const chunks = chunksData?.chunks ?? []

  const createMut = useMutation({
    mutationFn: (d: any) => editId ? documentStoresApi.update(editId, d) : documentStoresApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['document-stores'] }); setFormOpen(false); setEditId(null); setForm({ ...EMPTY_FORM }); toast.success(editId ? 'Updated' : 'Created') },
    onError: () => toast.error('Failed to save'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => documentStoresApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['document-stores'] }); setSelected(null); toast.success('Deleted') },
  })

  const upsertMut = useMutation({
    mutationFn: async () => {
      const docs = upsertText.split('\n---\n').map(t => ({ text: t.trim() })).filter(d => d.text)
      return documentStoresApi.upsert(selected!.id, docs)
    },
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ['doc-chunks', selected?.id] }); toast.success(`Upserted ${r.upserted} chunks`); setUpsertText('') },
    onError: () => toast.error('Upsert failed'),
  })

  const queryMut = useMutation({
    mutationFn: () => documentStoresApi.query(selected!.id, queryText, 5),
    onSuccess: (r) => setQueryResults(r.results ?? []),
    onError: () => toast.error('Query failed'),
  })

  const clearMut = useMutation({
    mutationFn: () => documentStoresApi.clearDocuments(selected!.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['doc-chunks', selected?.id] }); toast.success('Cleared all documents') },
  })

  function openCreate() { setEditId(null); setForm({ ...EMPTY_FORM }); setFormOpen(true) }
  function openEdit(s: any) { setEditId(s.id); setForm({ name: s.name, description: s.description ?? '', embedding_provider: s.embedding_provider, embedding_model: s.embedding_model, chunk_size: s.chunk_size, chunk_overlap: s.chunk_overlap }); setFormOpen(true) }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Document Stores</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
          + New Store
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Store List */}
        <div className="lg:col-span-1 space-y-3">
          {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {stores.map((s: any) => (
            <div key={s.id} onClick={() => setSelected(s)}
              className={`p-4 rounded-xl border cursor-pointer transition-colors ${selected?.id === s.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'}`}>
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white text-sm">{s.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{s.embedding_provider} · {s.embedding_model}</p>
                  <p className="text-xs text-gray-400 mt-0.5">chunk {s.chunk_size} / overlap {s.chunk_overlap}</p>
                </div>
                <div className="flex gap-1 ml-2">
                  <button onClick={e => { e.stopPropagation(); openEdit(s) }} className="text-gray-400 hover:text-gray-600 text-xs px-1">Edit</button>
                  <button onClick={e => { e.stopPropagation(); if (confirm('Delete store and all its documents?')) deleteMut.mutate(s.id) }} className="text-red-400 hover:text-red-600 text-xs px-1">Del</button>
                </div>
              </div>
            </div>
          ))}
          {!isLoading && stores.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">No document stores yet.</p>
          )}
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-2 border border-gray-200 dark:border-gray-700 rounded-xl flex flex-col" style={{ minHeight: '500px' }}>
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Select a store to manage its documents</div>
          ) : (
            <>
              <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex justify-between items-center mb-3">
                  <h2 className="font-semibold text-gray-900 dark:text-white">{selected.name}</h2>
                  <button onClick={() => { if (confirm('Clear all documents?')) clearMut.mutate() }} className="text-xs text-red-500 hover:text-red-600">Clear All</button>
                </div>
                <div className="flex gap-2">
                  {(['chunks', 'query', 'upsert'] as const).map(tab => (
                    <button key={tab} onClick={() => setActiveTab(tab)}
                      className={`px-3 py-1 text-xs rounded-full font-medium ${activeTab === tab ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200'}`}>
                      {tab === 'chunks' ? 'Chunks' : tab === 'query' ? 'Search' : 'Add Docs'}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4">
                {activeTab === 'chunks' && (
                  <div className="space-y-2">
                    {chunks.length === 0 && <p className="text-gray-400 text-sm">No documents stored. Use "Add Docs" to ingest text.</p>}
                    {chunks.map((c: any, i: number) => (
                      <div key={i} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-xs text-gray-700 dark:text-gray-300 font-mono">
                        <div className="text-gray-400 mb-1">#{c.id?.slice(-8) ?? i} · score —</div>
                        {c.content?.slice(0, 200)}{(c.content?.length ?? 0) > 200 ? '…' : ''}
                      </div>
                    ))}
                  </div>
                )}
                {activeTab === 'upsert' && (
                  <div className="space-y-3">
                    <p className="text-xs text-gray-500">Paste text below. Separate multiple documents with <code>---</code> on its own line.</p>
                    <textarea value={upsertText} onChange={e => setUpsertText(e.target.value)} rows={10} placeholder="Paste your document text here…" className="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <button onClick={() => upsertMut.mutate()} disabled={!upsertText.trim() || upsertMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                      {upsertMut.isPending ? 'Upserting…' : 'Upsert Documents'}
                    </button>
                  </div>
                )}
                {activeTab === 'query' && (
                  <div className="space-y-3">
                    <div className="flex gap-2">
                      <input value={queryText} onChange={e => setQueryText(e.target.value)} onKeyDown={e => e.key === 'Enter' && queryText.trim() && queryMut.mutate()} placeholder="Enter search query…" className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      <button onClick={() => queryMut.mutate()} disabled={!queryText.trim() || queryMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50">
                        {queryMut.isPending ? '…' : 'Search'}
                      </button>
                    </div>
                    {queryResults.map((r: any, i: number) => (
                      <div key={i} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                        <div className="text-xs text-gray-400 mb-1">Score: {r.score?.toFixed(4)}</div>
                        <p className="text-sm text-gray-700 dark:text-gray-300">{r.content}</p>
                      </div>
                    ))}
                    {queryMut.isSuccess && queryResults.length === 0 && <p className="text-gray-400 text-sm">No results found.</p>}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{editId ? 'Edit Store' : 'New Document Store'}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Name *" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" rows={2} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.embedding_provider} onChange={e => setForm(f => ({ ...f, embedding_provider: e.target.value, embedding_model: (EMBEDDING_MODELS[e.target.value] ?? [])[0] ?? '' }))} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {EMBEDDING_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <select value={form.embedding_model} onChange={e => setForm(f => ({ ...f, embedding_model: e.target.value }))} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {(EMBEDDING_MODELS[form.embedding_provider] ?? [form.embedding_model]).map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Chunk Size</label>
                  <input type="number" value={form.chunk_size} onChange={e => setForm(f => ({ ...f, chunk_size: parseInt(e.target.value) }))} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Overlap</label>
                  <input type="number" value={form.chunk_overlap} onChange={e => setForm(f => ({ ...f, chunk_overlap: parseInt(e.target.value) }))} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
            </div>
            <div className="flex gap-3 mt-5 justify-end">
              <button onClick={() => { setFormOpen(false); setEditId(null) }} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={!form.name.trim() || createMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
