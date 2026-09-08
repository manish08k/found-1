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

  const TABS = [
    { key: 'chunks', label: 'Chunks' },
    { key: 'query', label: 'Search' },
    { key: 'upsert', label: 'Add Docs' },
  ] as const

  return (
    <div className="page-fade" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 20px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Document Stores</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Vector databases for RAG — ingest, search, and manage embedded documents</p>
        </div>
        <button onClick={openCreate} style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', flexShrink: 0 }}>
          + New Store
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: 0 }}>
        {/* Store List */}
        <div style={{ width: 280, borderRight: '1px solid var(--border)', overflow: 'auto', flexShrink: 0, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: 8 }}>Loading…</div>}
          {stores.map((s: any) => {
            const isSelected = selected?.id === s.id
            return (
              <div key={s.id} onClick={() => setSelected(s)}
                style={{ padding: '10px 12px', background: isSelected ? 'var(--bg3)' : 'var(--bg2)', border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 10, cursor: 'pointer', transition: 'all 0.1s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{s.embedding_provider} · {s.embedding_model}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>chunk {s.chunk_size} / overlap {s.chunk_overlap}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                    <button onClick={e => { e.stopPropagation(); openEdit(s) }} style={{ padding: '2px 6px', background: 'transparent', color: 'var(--text3)', border: 'none', fontSize: 11, cursor: 'pointer', borderRadius: 4 }}>Edit</button>
                    <button onClick={e => { e.stopPropagation(); if (confirm('Delete store and all its documents?')) deleteMut.mutate(s.id) }} style={{ padding: '2px 6px', background: 'transparent', color: 'var(--red)', border: 'none', fontSize: 11, cursor: 'pointer', borderRadius: 4 }}>Del</button>
                  </div>
                </div>
              </div>
            )
          })}
          {!isLoading && stores.length === 0 && (
            <div style={{ color: 'var(--text3)', fontSize: 13, textAlign: 'center', padding: '32px 0' }}>No document stores yet</div>
          )}
        </div>

        {/* Detail Panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {!selected ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 13 }}>
              Select a store to manage its documents
            </div>
          ) : (
            <>
              <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{selected.name}</span>
                  <button onClick={() => { if (confirm('Clear all documents?')) clearMut.mutate() }}
                    style={{ padding: '3px 8px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', border: 'none', borderRadius: 5, fontSize: 11, cursor: 'pointer' }}>
                    Clear All
                  </button>
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {TABS.map(tab => (
                    <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                      style={{ padding: '4px 12px', background: activeTab === tab.key ? 'var(--accent)' : 'var(--bg3)', color: activeTab === tab.key ? '#fff' : 'var(--text3)', border: 'none', borderRadius: 20, fontSize: 11, fontWeight: activeTab === tab.key ? 600 : 400, cursor: 'pointer' }}>
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ flex: 1, overflow: 'auto', padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activeTab === 'chunks' && (
                  chunks.length === 0
                    ? <div style={{ color: 'var(--text3)', fontSize: 13 }}>No documents stored. Use "Add Docs" to ingest text.</div>
                    : chunks.map((c: any, i: number) => (
                      <div key={i} style={{ padding: '8px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8 }}>
                        <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4, fontFamily: 'var(--mono)' }}>#{c.id?.slice(-8) ?? i}</div>
                        <div style={{ fontSize: 11, color: 'var(--text2)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                          {c.content?.slice(0, 200)}{(c.content?.length ?? 0) > 200 ? '…' : ''}
                        </div>
                      </div>
                    ))
                )}

                {activeTab === 'upsert' && (
                  <>
                    <p style={{ fontSize: 12, color: 'var(--text3)' }}>
                      Paste text below. Separate multiple documents with <code style={{ fontFamily: 'var(--mono)', background: 'var(--bg3)', padding: '1px 4px', borderRadius: 3 }}>---</code> on its own line.
                    </p>
                    <textarea value={upsertText} onChange={e => setUpsertText(e.target.value)} rows={10} placeholder="Paste your document text here…" />
                    <button onClick={() => upsertMut.mutate()} disabled={!upsertText.trim() || upsertMut.isPending}
                      style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (!upsertText.trim() || upsertMut.isPending) ? 0.5 : 1, alignSelf: 'flex-start' }}>
                      {upsertMut.isPending ? 'Upserting…' : 'Upsert Documents'}
                    </button>
                  </>
                )}

                {activeTab === 'query' && (
                  <>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input value={queryText} onChange={e => setQueryText(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && queryText.trim() && queryMut.mutate()}
                        placeholder="Enter search query…" style={{ flex: 1 }} />
                      <button onClick={() => queryMut.mutate()} disabled={!queryText.trim() || queryMut.isPending}
                        style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (!queryText.trim() || queryMut.isPending) ? 0.5 : 1, flexShrink: 0 }}>
                        {queryMut.isPending ? '…' : 'Search'}
                      </button>
                    </div>
                    {queryResults.map((r: any, i: number) => (
                      <div key={i} style={{ padding: '10px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8 }}>
                        <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4, fontFamily: 'var(--mono)' }}>Score: {r.score?.toFixed(4)}</div>
                        <div style={{ fontSize: 12, color: 'var(--text2)' }}>{r.content}</div>
                      </div>
                    ))}
                    {queryMut.isSuccess && queryResults.length === 0 && (
                      <div style={{ color: 'var(--text3)', fontSize: 13 }}>No results found.</div>
                    )}
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: 10 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{editId ? 'Edit Store' : 'New Document Store'}</h2>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Name *" />
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" rows={2} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <select value={form.embedding_provider} onChange={e => setForm(f => ({ ...f, embedding_provider: e.target.value, embedding_model: (EMBEDDING_MODELS[e.target.value] ?? [])[0] ?? '' }))}>
                {EMBEDDING_PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <select value={form.embedding_model} onChange={e => setForm(f => ({ ...f, embedding_model: e.target.value }))}>
                {(EMBEDDING_MODELS[form.embedding_provider] ?? [form.embedding_model]).map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Chunk Size</div>
                <input type="number" value={form.chunk_size} onChange={e => setForm(f => ({ ...f, chunk_size: parseInt(e.target.value) }))} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Overlap</div>
                <input type="number" value={form.chunk_overlap} onChange={e => setForm(f => ({ ...f, chunk_overlap: parseInt(e.target.value) }))} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button onClick={() => { setFormOpen(false); setEditId(null) }} style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => createMut.mutate(form)} disabled={!form.name.trim() || createMut.isPending}
                style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (!form.name.trim() || createMut.isPending) ? 0.5 : 1 }}>
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
