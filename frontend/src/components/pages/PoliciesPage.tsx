import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { policiesApi } from '../../api/client'
import toast from 'react-hot-toast'

const RULE_TYPES = [
  { value: 'node_allowlist', label: 'Node Allowlist', desc: 'Only allow specific node types' },
  { value: 'node_denylist', label: 'Node Denylist', desc: 'Block specific node types' },
  { value: 'keyword_block', label: 'Keyword Block', desc: 'Block executions containing specific keywords' },
  { value: 'require_approval', label: 'Require Approval', desc: 'Require human approval for specific node types' },
  { value: 'rate_limit', label: 'Rate Limit', desc: 'Limit executions per hour' },
]

function RuleEditor({ rule, onChange, onRemove }: { rule: any; onChange: (r: any) => void; onRemove: () => void }) {
  const ruleDef = RULE_TYPES.find(r => r.value === rule.type)

  const updateConfig = (key: string, value: any) => {
    onChange({ ...rule, config: { ...rule.config, [key]: value } })
  }

  return (
    <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <select value={rule.type} onChange={e => onChange({ type: e.target.value, config: {} })}
          style={{ flex: 1, padding: '6px 10px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 12 }}>
          {RULE_TYPES.map(rt => <option key={rt.value} value={rt.value}>{rt.label}</option>)}
        </select>
        <button onClick={onRemove} style={{ background: 'transparent', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 14 }}>✕</button>
      </div>
      {ruleDef && <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 10 }}>{ruleDef.desc}</div>}

      {(rule.type === 'node_allowlist' || rule.type === 'node_denylist' || rule.type === 'require_approval') && (
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Node types (comma-separated)</label>
          <input
            value={(rule.config?.allowed_node_types || rule.config?.denied_node_types || rule.config?.node_types || []).join(', ')}
            onChange={e => {
              const arr = e.target.value.split(',').map(s => s.trim()).filter(Boolean)
              const key = rule.type === 'node_allowlist' ? 'allowed_node_types' : rule.type === 'node_denylist' ? 'denied_node_types' : 'node_types'
              updateConfig(key, arr)
            }}
            placeholder="e.g. database.execute, core.run_code"
            style={{ width: '100%', padding: '6px 10px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 12, boxSizing: 'border-box' }}
          />
        </div>
      )}

      {rule.type === 'keyword_block' && (
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Keywords to block (comma-separated)</label>
          <input
            value={(rule.config?.keywords || []).join(', ')}
            onChange={e => updateConfig('keywords', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            placeholder="e.g. DROP TABLE, DELETE FROM"
            style={{ width: '100%', padding: '6px 10px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 12, boxSizing: 'border-box' }}
          />
        </div>
      )}

      {rule.type === 'rate_limit' && (
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Max executions per hour</label>
          <input type="number" min={1}
            value={rule.config?.max_executions_per_hour || 100}
            onChange={e => updateConfig('max_executions_per_hour', parseInt(e.target.value))}
            style={{ width: 120, padding: '6px 10px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 12 }}
          />
        </div>
      )}
    </div>
  )
}

function PolicyModal({ existing, onClose }: { existing?: any; onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState(existing?.name || '')
  const [description, setDescription] = useState(existing?.description || '')
  const [action, setAction] = useState(existing?.action || 'block')
  const [isActive, setIsActive] = useState(existing?.is_active ?? true)
  const [rules, setRules] = useState<any[]>(existing?.rules || [])

  const saveMut = useMutation({
    mutationFn: () => {
      const payload = { name, description: description || undefined, action, is_active: isActive, rules }
      return existing ? policiesApi.update(existing.id, payload) : policiesApi.create(payload)
    },
    onSuccess: () => {
      toast.success(existing ? 'Policy updated' : 'Policy created')
      qc.invalidateQueries({ queryKey: ['policies'] })
      onClose()
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const addRule = () => setRules(prev => [...prev, { type: 'node_denylist', config: {} }])
  const updateRule = (i: number, r: any) => setRules(prev => prev.map((p, idx) => idx === i ? r : p))
  const removeRule = (i: number) => setRules(prev => prev.filter((_, idx) => idx !== i))

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 12, width: 560, maxHeight: '85vh', overflow: 'auto', padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>{existing ? 'Edit Policy' : 'Create Policy'}</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Name *</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Policy name"
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Description</label>
            <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Optional description"
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Action when violated</label>
              <select value={action} onChange={e => setAction(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
                <option value="block">Block execution</option>
                <option value="warn">Warn only</option>
                <option value="require_approval">Require approval</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Active</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 36 }}>
                <button onClick={() => setIsActive(!isActive)}
                  style={{ width: 44, height: 22, borderRadius: 11, background: isActive ? 'var(--accent)' : 'var(--bg3)', border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s' }}>
                  <div style={{ width: 18, height: 18, background: '#fff', borderRadius: 9, position: 'absolute', top: 2, left: isActive ? 22 : 2, transition: 'left 0.2s' }} />
                </button>
                <span style={{ fontSize: 12, color: 'var(--text3)' }}>{isActive ? 'On' : 'Off'}</span>
              </div>
            </div>
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <label style={{ fontSize: 12, color: 'var(--text2)' }}>Rules ({rules.length})</label>
              <button onClick={addRule}
                style={{ padding: '4px 10px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}>
                + Add Rule
              </button>
            </div>
            {rules.length === 0 && (
              <div style={{ padding: '12px 16px', background: 'var(--bg)', border: '1px dashed var(--border)', borderRadius: 8, color: 'var(--text3)', fontSize: 12, textAlign: 'center' }}>
                No rules. Add a rule to define what this policy enforces.
              </div>
            )}
            {rules.map((r, i) => (
              <RuleEditor key={i} rule={r} onChange={u => updateRule(i, u)} onRemove={() => removeRule(i)} />
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: '8px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
            Cancel
          </button>
          <button onClick={() => saveMut.mutate()} disabled={!name || saveMut.isPending}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, opacity: (!name || saveMut.isPending) ? 0.5 : 1 }}>
            {saveMut.isPending ? 'Saving…' : 'Save Policy'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PoliciesPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['policies'],
    queryFn: policiesApi.list,
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => policiesApi.delete(id),
    onSuccess: () => { toast.success('Policy deleted'); qc.invalidateQueries({ queryKey: ['policies'] }) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      policiesApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['policies'] }),
  })

  const policies: any[] = data?.policies ?? []

  const ACTION_COLORS: Record<string, string> = {
    block: 'var(--red)',
    warn: 'var(--yellow)',
    require_approval: 'var(--accent)',
  }

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Policies & Guardrails</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Define rules that control what workflows can do and when approval is required</p>
          </div>
          <button onClick={() => setShowCreate(true)}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Policy
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
        {!isLoading && policies.length === 0 && (
          <div style={{ textAlign: 'center', padding: '64px 0' }}>
            <div style={{ color: 'var(--text2)', fontWeight: 600, marginBottom: 8 }}>No policies</div>
            <div style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 20 }}>Create policies to enforce security guardrails on workflow execution</div>
            <button onClick={() => setShowCreate(true)}
              style={{ padding: '8px 20px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
              New Policy
            </button>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {policies.map((p: any) => (
            <div key={p.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px', display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{p.name}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: `${ACTION_COLORS[p.action] || 'var(--text3)'}22`, color: ACTION_COLORS[p.action] || 'var(--text3)', textTransform: 'uppercase' }}>
                    {p.action}
                  </span>
                  {!p.is_active && (
                    <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'var(--bg3)', color: 'var(--text3)' }}>Disabled</span>
                  )}
                </div>
                {p.description && <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>{p.description}</div>}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(p.rules || []).map((r: any, i: number) => (
                    <span key={i} style={{ fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'var(--bg3)', color: 'var(--text3)', fontFamily: 'var(--mono)' }}>
                      {r.type}
                    </span>
                  ))}
                  {(p.rules || []).length === 0 && <span style={{ fontSize: 11, color: 'var(--text3)' }}>No rules</span>}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                <button onClick={() => toggleMut.mutate({ id: p.id, is_active: !p.is_active })}
                  style={{ width: 36, height: 20, borderRadius: 10, background: p.is_active ? 'var(--accent)' : 'var(--bg3)', border: 'none', cursor: 'pointer', position: 'relative' }}>
                  <div style={{ width: 16, height: 16, background: '#fff', borderRadius: 8, position: 'absolute', top: 2, left: p.is_active ? 18 : 2, transition: 'left 0.2s' }} />
                </button>
                <button onClick={() => setEditing(p)}
                  style={{ padding: '5px 10px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}>
                  Edit
                </button>
                <button onClick={() => { if (confirm('Delete policy?')) deleteMut.mutate(p.id) }}
                  style={{ padding: '5px 10px', background: 'rgba(239,68,68,0.08)', border: '1px solid var(--red)', color: 'var(--red)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {(showCreate || editing) && (
        <PolicyModal
          existing={editing}
          onClose={() => { setShowCreate(false); setEditing(null) }}
        />
      )}
    </div>
  )
}
