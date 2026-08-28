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

  const runMut = useMutation({
    mutationFn: () => assistantsApi.runThread(selectedAssistant!, threadId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant-threads', selectedAssistant, threadId] }),
    onError: () => toast.error('Run failed'),
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
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Assistants</h1>
        <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
          + New Assistant
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Assistant List */}
        <div className="lg:col-span-1 space-y-3">
          {isLoading && <p className="text-gray-500 text-sm">Loading…</p>}
          {assistants.map((a: any) => (
            <div key={a.id} onClick={() => { setSelectedAssistant(a.id); setThreadId(null) }}
              className={`p-4 rounded-xl border cursor-pointer transition-colors ${selectedAssistant === a.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'}`}>
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-medium text-gray-900 dark:text-white text-sm">{a.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{a.provider} / {a.model}</p>
                  {a.description && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{a.description}</p>}
                </div>
                <div className="flex gap-1 ml-2">
                  <button onClick={e => { e.stopPropagation(); openEdit(a) }} className="text-gray-400 hover:text-gray-600 text-xs px-1">Edit</button>
                  <button onClick={e => { e.stopPropagation(); if (confirm('Delete?')) deleteMut.mutate(a.id) }} className="text-red-400 hover:text-red-600 text-xs px-1">Del</button>
                </div>
              </div>
            </div>
          ))}
          {!isLoading && assistants.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">No assistants yet. Create one to get started.</p>
          )}
        </div>

        {/* Chat Panel */}
        <div className="lg:col-span-2 border border-gray-200 dark:border-gray-700 rounded-xl flex flex-col" style={{ minHeight: '500px' }}>
          {!selectedAssistant ? (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">Select an assistant to start chatting</div>
          ) : (
            <>
              <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                <span className="font-medium text-sm text-gray-900 dark:text-white">
                  {assistants.find((a: any) => a.id === selectedAssistant)?.name ?? 'Assistant'}
                </span>
                <button onClick={async () => {
                  const t = await assistantsApi.createThread(selectedAssistant)
                  setThreadId(t.id)
                }} className="text-xs text-blue-600 hover:text-blue-700">New Thread</button>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((m: any) => (
                  <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-xs lg:max-w-md px-3 py-2 rounded-xl text-sm ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white'}`}>
                      {m.content}
                    </div>
                  </div>
                ))}
                {messages.length === 0 && <p className="text-gray-400 text-sm text-center">No messages yet. Start a conversation.</p>}
              </div>
              <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex gap-2">
                <input value={chatInput} onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && chatInput.trim() && sendMut.mutate()}
                  placeholder="Type a message…" className="flex-1 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                <button onClick={() => chatInput.trim() && sendMut.mutate()} disabled={sendMut.isPending || !chatInput.trim()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-blue-700">
                  {sendMut.isPending ? '…' : 'Send'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">{editId ? 'Edit Assistant' : 'New Assistant'}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="Name *" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Description" rows={2} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <textarea value={form.system_prompt} onChange={e => setForm(f => ({ ...f, system_prompt: e.target.value }))} placeholder="System prompt" rows={3} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <div className="grid grid-cols-2 gap-3">
                <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value, model: (MODELS[e.target.value] ?? [])[0] ?? '' }))} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <select value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))} className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {(MODELS[form.provider] ?? [form.model]).map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Temperature: {form.temperature}</label>
                  <input type="range" min="0" max="1" step="0.1" value={form.temperature} onChange={e => setForm(f => ({ ...f, temperature: parseFloat(e.target.value) }))} className="w-full" />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Max Tokens</label>
                  <input type="number" value={form.max_tokens} onChange={e => setForm(f => ({ ...f, max_tokens: parseInt(e.target.value) }))} className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <input value={form.document_store_id} onChange={e => setForm(f => ({ ...f, document_store_id: e.target.value }))} placeholder="Document Store ID (optional, for RAG)" className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-800 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-3 mt-5 justify-end">
              <button onClick={() => { setFormOpen(false); setEditId(null) }} className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">Cancel</button>
              <button onClick={() => createMut.mutate({ ...form, temperature: form.temperature, document_store_id: form.document_store_id || undefined })} disabled={!form.name.trim() || createMut.isPending} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg font-medium disabled:opacity-50 hover:bg-blue-700">
                {createMut.isPending ? 'Saving…' : (editId ? 'Update' : 'Create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
