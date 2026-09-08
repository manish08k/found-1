import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assistantsApi } from '../../api/client'
import toast from 'react-hot-toast'

const PROVIDERS = ['openai', 'anthropic', 'gemini', 'ollama', 'groq', 'mistral', 'cohere', 'huggingface', 'azure', 'together_ai']
const MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
  gemini: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp'],
  ollama: ['llama3.2', 'mistral', 'codellama'],
  groq: ['llama3-70b-8192', 'llama3-8b-8192', 'mixtral-8x7b-32768'],
  mistral: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest'],
  cohere: ['command-r-plus', 'command-r', 'command'],
  huggingface: ['meta-llama/Meta-Llama-3-70B-Instruct'],
  azure: ['gpt-4o', 'gpt-4-turbo'],
  together_ai: ['meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo'],
}

const EMPTY_FORM = {
  name: '', description: '', system_prompt: 'You are a helpful assistant.',
  model: 'gpt-4o-mini', provider: 'openai', temperature: 0.7, max_tokens: 1024, document_store_id: '',
}

export default function AssistantsPage() {
  const qc = useQueryClient()
  const [formOpen, setFormOpen] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [selectedAssistant, setSelectedAssistant] = useState<string | null>(null)
  const [threadId, setThreadId] = useState<string | null>(null)
  const [chatInput, setChatInput] = useState('')

  const { data, isLoading } = useQuery({ queryKey: ['assistants'], queryFn: () => assistantsApi.list() })
  const assistants = data?.assistants ?? []

  const { data: threadData } = useQuery({
    queryKey: ['assistant-threads', selectedAssistant, threadId],
    queryFn: () => assistantsApi.listMessages(selectedAssistant!, threadId!),
    enabled: !!selectedAssistant && !!threadId,
  })
  const messages = threadData?.messages ?? []

  const createMut = useMutation({
    mutationFn: (d: any) => editId ? assistantsApi.update(editId, d) : assistantsApi.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assistants'] }); setFormOpen(false); setEditId(null); setForm({ ...EMPTY_FORM }); toast.success(editId ? 'Updated' : 'Created') },
    onError: () => toast.error('Failed to save assistant'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => assistantsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['assistants'] }); toast.success('Deleted') },
  })

  const sendMut = useMutation({
    mutationFn: async () => {
      let tid = threadId
      if (!tid) {
        const t = await assistantsApi.createThread(selectedAssistant!)
        tid = t.id
        setThreadId(tid)
      }
      await assistantsApi.addMessage(selectedAssistant!, tid!, chatInput)
      setChatInput('')
      await assistantsApi.runThread(selectedAssistant!, tid!)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant-threads', selectedAssistant, threadId] }),
    onError: () => toast.error('Send failed'),
  })

  function openCreate() { setEditId(null); setForm({ ...EMPTY_FORM }); setFormOpen(true) }
  function openEdit(a: any) { setEditId(a.id); setForm({ name: a.name, description: a.description ?? '', system_prompt: a.system_prompt, model: a.model, provider: a.provider, temperature: a.temperature, max_tokens: a.max_tokens, document_store_id: a.document_store_id ?? '' }); setFormOpen(true) }

  return (
    <div className="page-fade" style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 20px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Assistants</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Configure AI assistants powered by your preferred models</p>
        </div>
        <button onClick={openCreate} style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          + New Assistant
        </button>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: 0 }}>
        {/* Assistant List */}
        <div style={{ width: 280, borderRight: '1px solid var(--border)', overflow: 'auto', flexShrink: 0, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: 8 }}>Loading…</div>}
          {assistants.map((a: any) => {
            const isSelected = selectedAssistant === a.id
            return (
              <div key={a.id} onClick={() => { setSelectedAssistant(a.id); setThreadId(null) }}
                style={{ padding: '10px 12px', background: isSelected ? 'var(--bg3)' : 'var(--bg2)', border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 10, cursor: 'pointer', transition: 'all 0.1s' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.name}</div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{a.provider} / {a.model}</div>
                    {a.description && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description}</div>}
                  </div>
                  <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
                    <button onClick={e => { e.stopPropagation(); openEdit(a) }} style={{ padding: '2px 6px', background: 'transparent', color: 'var(--text3)', border: 'none', fontSize: 11, cursor: 'pointer', borderRadius: 4 }}>Edit</button>
                    <button onClick={e => { e.stopPropagation(); if (confirm('Delete?')) deleteMut.mutate(a.id) }} style={{ padding: '2px 6px', background: 'transparent', color: 'var(--red)', border: 'none', fontSize: 11, cursor: 'pointer', borderRadius: 4 }}>Del</button>
                  </div>
                </div>
              </div>
            )
          })}
          {!isLoading && assistants.length === 0 && (
            <div style={{ color: 'var(--text3)', fontSize: 13, textAlign: 'center', padding: '32px 0' }}>No assistants yet</div>
          )}
        </div>

        {/* Chat Panel */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {!selectedAssistant ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 13 }}>
              Select an assistant to start chatting
            </div>
          ) : (
            <>
              <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
                <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
                  {assistants.find((a: any) => a.id === selectedAssistant)?.name ?? 'Assistant'}
                </span>
                <button onClick={async () => {
                  const t = await assistantsApi.createThread(selectedAssistant)
                  setThreadId(t.id)
                }} style={{ padding: '4px 10px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 6, fontSize: 11, cursor: 'pointer' }}>
                  New Thread
                </button>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
                {messages.map((m: any) => (
                  <div key={m.id} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '70%', padding: '8px 12px', borderRadius: 10, fontSize: 13,
                      background: m.role === 'user' ? 'var(--accent)' : 'var(--bg3)',
                      color: m.role === 'user' ? '#fff' : 'var(--text)',
                    }}>
                      {m.content}
                    </div>
                  </div>
                ))}
                {messages.length === 0 && (
                  <div style={{ color: 'var(--text3)', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                    {threadId ? 'No messages yet. Start a conversation.' : 'Click "New Thread" to begin.'}
                  </div>
                )}
              </div>
              <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, flexShrink: 0 }}>
                <input value={chatInput} onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && chatInput.trim() && sendMut.mutate()}
                  placeholder="Type a message…" style={{ flex: 1, width: 'auto' }} />
                <button onClick={() => chatInput.trim() && sendMut.mutate()} disabled={sendMut.isPending || !chatInput.trim()}
                  style={{ padding: '7px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer', opacity: (sendMut.isPending || !chatInput.trim()) ? 0.5 : 1, flexShrink: 0 }}>
                  {sendMut.isPending ? '…' : 'Send'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, padding: 24, width: '100%', maxWidth: 500, boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', margin: 0 }}>{editId ? 'Edit Assistant' : 'New Assistant'}</h2>
            <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Name *" />
            <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" rows={2} />
            <textarea value={form.system_prompt} onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))} placeholder="System prompt" rows={3} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value, model: (MODELS[e.target.value] ?? [])[0] ?? '' }))}>
                {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <select value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))}>
                {(MODELS[form.provider] ?? [form.model]).map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Temperature: {form.temperature}</div>
                <input type="range" min="0" max="1" step="0.1" value={form.temperature}
                  onChange={e => setForm(f => ({ ...f, temperature: parseFloat(e.target.value) }))}
                  style={{ width: '100%', padding: 0, border: 'none', background: 'transparent' }} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Max Tokens</div>
                <input type="number" value={form.max_tokens} onChange={e => setForm(f => ({ ...f, max_tokens: parseInt(e.target.value) }))} />
              </div>
            </div>
            <input value={form.document_store_id} onChange={e => setForm(f => ({ ...f, document_store_id: e.target.value }))} placeholder="Document Store ID (optional, for RAG)" />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button onClick={() => { setFormOpen(false); setEditId(null) }} style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer' }}>Cancel</button>
              <button onClick={() => createMut.mutate({ ...form, document_store_id: form.document_store_id || undefined })} disabled={!form.name.trim() || createMut.isPending}
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
