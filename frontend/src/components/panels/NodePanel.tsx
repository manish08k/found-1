import React, { useState, useEffect, useMemo } from 'react'
import { getNodeDef } from '../../types/nodes'
import ExpressionInput, { ExpressionSuggestion } from '../common/ExpressionInput'
import type { WFNode, WFEdge } from '../../types'

interface Props {
  node: WFNode
  onChange: (updated: WFNode) => void
  onDelete: () => void
  onClose: () => void
  credentials: any[]
  allNodes?: WFNode[]
  edges?: WFEdge[]
}

/** Every node reachable by walking backwards through edges from `nodeId` — i.e. everything that could have already run before this node, and therefore has output this node could reference. */
function upstreamNodeIds(nodeId: string, edges: WFEdge[]): string[] {
  const bySourceTarget = edges
  const visited = new Set<string>()
  const queue = [nodeId]
  while (queue.length) {
    const current = queue.shift()!
    for (const e of bySourceTarget) {
      if (e.target === current && !visited.has(e.source)) {
        visited.add(e.source)
        queue.push(e.source)
      }
    }
  }
  return Array.from(visited)
}

function buildSuggestions(node: WFNode, allNodes: WFNode[], edges: WFEdge[]): ExpressionSuggestion[] {
  const suggestions: ExpressionSuggestion[] = [
    { insert: 'trigger.body', label: 'trigger.body', hint: 'Full payload from a webhook trigger' },
    { insert: 'trigger.query', label: 'trigger.query', hint: 'URL query params, for webhook triggers' },
    { insert: 'trigger.headers', label: 'trigger.headers', hint: 'HTTP headers, for webhook triggers' },
  ]
  const upstreamIds = upstreamNodeIds(node.id, edges)
  for (const id of upstreamIds) {
    const upNode = allNodes.find(n => n.id === id)
    if (!upNode) continue
    const def = getNodeDef(upNode.type)
    const displayLabel = upNode.label || def?.label || upNode.type
    suggestions.push({
      insert: `nodes.${id}.output`,
      label: `nodes.${id}.output`,
      hint: `Output of "${displayLabel}" (${def?.label ?? upNode.type})`,
    })
    // A couple of node types have a well-known, commonly-referenced shape —
    // surface those directly since typing them from scratch is the most
    // common thing people get wrong.
    if (upNode.type === 'database.query') {
      suggestions.push({ insert: `nodes.${id}.rows`, label: `nodes.${id}.rows`, hint: 'Array of result rows' })
      suggestions.push({ insert: `nodes.${id}.rows.0`, label: `nodes.${id}.rows.0`, hint: 'First result row' })
    }
    if (upNode.type === 'http.request') {
      suggestions.push({ insert: `nodes.${id}.status_code`, label: `nodes.${id}.status_code`, hint: 'HTTP status code' })
      suggestions.push({ insert: `nodes.${id}.body`, label: `nodes.${id}.body`, hint: 'Response body' })
    }
  }
  return suggestions
}

export default function NodePanel({ node, onChange, onDelete, onClose, credentials, allNodes = [], edges = [] }: Props) {
  const def = getNodeDef(node.type)
  const [cfg, setCfg] = useState<Record<string, any>>(node.config ?? {})
  const [label, setLabel] = useState(node.label ?? def?.label ?? '')
  const [credId, setCredId] = useState(node.credential_id ?? '')
  const [retryEnabled, setRetryEnabled] = useState(!!node.retry)
  const [retryAttempts, setRetryAttempts] = useState(node.retry?.max_attempts ?? 3)

  const suggestions = useMemo(() => buildSuggestions(node, allNodes, edges), [node.id, allNodes, edges])

  useEffect(() => {
    setCfg(node.config ?? {})
    setLabel(node.label ?? def?.label ?? '')
    setCredId(node.credential_id ?? '')
    setRetryEnabled(!!node.retry)
  }, [node.id])

  const DB_PROVIDERS = ['postgres', 'mysql', 'sqlite']
  const needsCred = def && !['core', 'http'].includes(def.provider)
  const provCreds = def?.provider === 'database'
    ? credentials.filter(c => DB_PROVIDERS.includes(c.provider))
    : credentials.filter(c => c.provider === def?.provider)

  const save = () => onChange({
    ...node, label, config: cfg,
    credential_id: credId || undefined,
    retry: retryEnabled ? { max_attempts: retryAttempts, wait_min: 1, wait_max: 60 } : undefined,
  })

  return (
    <div style={{ width: 300, background: 'var(--bg1)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{def?.category ?? 'Node'}</div>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{def?.label ?? node.type}</div>
        </div>
        <button onClick={onClose} aria-label="Close node settings" style={{ background: 'transparent', color: 'var(--text3)', border: 'none', cursor: 'pointer', padding: 4 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Field label="Label">
          <input value={label} onChange={e => setLabel(e.target.value)} placeholder={def?.label} />
        </Field>

        {needsCred && (
          <Field label={`${def!.label} Account`}>
            {provCreds.length === 0 ? (
              <div style={{ fontSize: 11, color: 'var(--yellow)', lineHeight: 1.5 }}>
                No {def!.provider} accounts connected.{' '}
                <a href="#" onClick={e => { e.preventDefault(); window.open(`https://api.autoxflow.space/oauth/connect/${def!.provider}?token=${localStorage.getItem('token')}`) }}
                  style={{ color: 'var(--accent)' }}>Connect now →</a>
              </div>
            ) : (
              <select value={credId} onChange={e => setCredId(e.target.value)}>
                <option value="">— Select account —</option>
                {provCreds.map((c: any) => <option key={c.id} value={c.id}>{c.label} ({c.external_account_name || c.provider})</option>)}
              </select>
            )}
          </Field>
        )}

        {def?.configFields && def.configFields.length > 0 && (
          <div style={{ fontSize: 10.5, color: 'var(--text3)', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 6, padding: '6px 9px', lineHeight: 1.5 }}>
            Type <code style={{ fontFamily: 'var(--mono)', color: 'var(--text2)' }}>{'{{ '}</code> in any text field for suggestions from the trigger and earlier nodes.
          </div>
        )}

        {def?.configFields.map(field => (
          <Field key={field.key} label={field.label} required={field.required}>
            {field.type === 'select' ? (
              <select value={cfg[field.key] ?? ''} onChange={e => setCfg(p => ({ ...p, [field.key]: e.target.value }))}>
                <option value="">— Select —</option>
                {field.options?.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : field.type === 'boolean' ? (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={!!cfg[field.key]} onChange={e => setCfg(p => ({ ...p, [field.key]: e.target.checked }))} style={{ width: 'auto' }} />
                <span style={{ color: 'var(--text2)', fontSize: 12 }}>Enable</span>
              </label>
            ) : field.type === 'number' ? (
              <input type="number" value={cfg[field.key] ?? ''} placeholder={field.placeholder} onChange={e => setCfg(p => ({ ...p, [field.key]: Number(e.target.value) }))} />
            ) : field.type === 'json' ? (
              <textarea
                value={typeof cfg[field.key] === 'object' ? JSON.stringify(cfg[field.key], null, 2) : (cfg[field.key] ?? '')}
                placeholder={field.placeholder ?? '{ }'}
                onChange={e => {
                  try { setCfg(p => ({ ...p, [field.key]: JSON.parse(e.target.value) })) }
                  catch { setCfg(p => ({ ...p, [field.key]: e.target.value })) }
                }}
              />
            ) : field.type === 'textarea' ? (
              <ExpressionInput multiline value={cfg[field.key] ?? ''} placeholder={field.placeholder}
                onChange={v => setCfg(p => ({ ...p, [field.key]: v }))} suggestions={suggestions} />
            ) : (
              <ExpressionInput value={cfg[field.key] ?? ''} placeholder={field.placeholder}
                onChange={v => setCfg(p => ({ ...p, [field.key]: v }))} suggestions={suggestions} />
            )}
          </Field>
        ))}

        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: retryEnabled ? 10 : 0 }}>
            <input type="checkbox" checked={retryEnabled} onChange={e => setRetryEnabled(e.target.checked)} style={{ width: 'auto' }} />
            <span style={{ fontSize: 12, color: 'var(--text2)', fontWeight: 500 }}>Retry on failure</span>
          </label>
          {retryEnabled && (
            <Field label="Max Attempts">
              <input type="number" min={1} max={10} value={retryAttempts} onChange={e => setRetryAttempts(Number(e.target.value))} />
            </Field>
          )}
        </div>
      </div>

      <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
        <button onClick={save} style={{ flex: 1, padding: '9px 0', background: 'var(--accent)', color: '#fff', borderRadius: 7, fontWeight: 600, fontSize: 13, border: 'none', cursor: 'pointer' }}>
          Save Node
        </button>
        <button onClick={onDelete} aria-label="Delete this node" title="Delete node" style={{ width: 38, height: 38, background: 'rgba(239,68,68,0.1)', color: 'var(--red)', borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
        </button>
      </div>
    </div>
  )
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 10, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>
        {label}{required && <span style={{ color: 'var(--red)', marginLeft: 2 }}>*</span>}
      </label>
      {children}
    </div>
  )
}
