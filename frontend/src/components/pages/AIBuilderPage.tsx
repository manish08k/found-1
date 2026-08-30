import React, { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { aiBuilderApi, workflowsApi } from '../../api/client'
import { useStore } from '../../store'
import toast from 'react-hot-toast'

const EXAMPLE_PROMPTS = [
  'Receive a webhook, extract customer data, look up the customer in a database, then send a Slack message',
  'Every morning at 9am, query Airtable for new leads, use AI to score them, and create Jira tickets for hot leads',
  'When a GitHub issue is created, use AI to categorize it, assign to the right team in Slack, and add a Jira ticket',
  'Process a customer refund request: validate, look up order, approve or reject with human review, then email the customer',
]

function NodePreview({ nodes, edges }: { nodes: any[]; edges: any[] }) {
  if (nodes.length === 0) return null

  const TYPE_COLORS: Record<string, string> = {
    'ai.': '#7c3aed',
    'http.': '#0ea5e9',
    'slack.': '#e11d48',
    'core.': '#64748b',
    'webhook': '#f59e0b',
    'trigger.': '#f59e0b',
    'database.': '#84cc16',
    'agentflow.': '#8b5cf6',
    'agent.': '#8b5cf6',
    'approval.': '#f97316',
    'vector.': '#06b6d4',
    'notion.': '#a16207',
    'github.': '#334155',
    'google.': '#2563eb',
  }

  const getColor = (nodeType: string) => {
    for (const [prefix, color] of Object.entries(TYPE_COLORS)) {
      if (nodeType.startsWith(prefix)) return color
    }
    return '#6b7280'
  }

  // Build adjacency for layout
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]))
  const childrenOf: Record<string, string[]> = {}
  const parentCount: Record<string, number> = {}
  nodes.forEach(n => { childrenOf[n.id] = []; parentCount[n.id] = 0 })
  edges.forEach(e => {
    if (childrenOf[e.source]) childrenOf[e.source].push(e.target)
    if (e.target in parentCount) parentCount[e.target]++
  })

  // Simple topological layout
  const levels: string[][] = []
  let remaining = new Set(nodes.map(n => n.id))
  let currentLevel = nodes.filter(n => parentCount[n.id] === 0).map(n => n.id)
  while (currentLevel.length > 0 && remaining.size > 0) {
    levels.push(currentLevel)
    currentLevel.forEach(id => remaining.delete(id))
    const next: string[] = []
    currentLevel.forEach(id => {
      (childrenOf[id] || []).forEach(child => {
        if (remaining.has(child)) {
          parentCount[child]--
          if (parentCount[child] === 0) next.push(child)
        }
      })
    })
    currentLevel = next
  }
  // Add any remaining (cyclical) nodes
  if (remaining.size > 0) levels.push([...remaining])

  return (
    <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
      <div style={{ display: 'flex', gap: 32, alignItems: 'flex-start', minWidth: 'max-content', padding: '8px 4px' }}>
        {levels.map((level, li) => (
          <div key={li} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {level.map(nodeId => {
              const node = nodeMap[nodeId]
              if (!node) return null
              const color = getColor(node.type || '')
              return (
                <div key={nodeId} style={{ background: `${color}18`, border: `1.5px solid ${color}`, borderRadius: 8, padding: '8px 12px', minWidth: 140, maxWidth: 180 }}>
                  <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color, fontWeight: 600, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.type}</div>
                  <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {node.config?.name || node.id}
                  </div>
                </div>
              )
            })}
          </div>
        ))}
      </div>
      {edges.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text3)' }}>
          {nodes.length} nodes · {edges.length} connections
        </div>
      )}
    </div>
  )
}

function ValidationDisplay({ validation }: { validation: any }) {
  if (!validation) return null
  return (
    <div style={{ marginTop: 12 }}>
      {validation.valid ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--green)', fontSize: 12 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
          Workflow is valid
        </div>
      ) : (
        <div>
          <div style={{ color: 'var(--red)', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Validation errors:</div>
          {(validation.errors || []).map((err: string, i: number) => (
            <div key={i} style={{ fontSize: 12, color: 'var(--red)', paddingLeft: 12 }}>• {err}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AIBuilderPage() {
  const { setPage } = useStore()
  const [prompt, setPrompt] = useState('')
  const [targetWorkflowId, setTargetWorkflowId] = useState('')
  const [generated, setGenerated] = useState<any>(null)
  const [customName, setCustomName] = useState('')

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list })
  const workflows: any[] = wfData?.workflows ?? []

  const generateMut = useMutation({
    mutationFn: () => aiBuilderApi.generate({ prompt, workflow_id: targetWorkflowId || undefined }),
    onSuccess: (data) => {
      setGenerated(data)
      toast.success('Workflow generated — review and apply it below')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Generation failed. Ensure an AI API key is configured.'),
  })

  const applyMut = useMutation({
    mutationFn: () => aiBuilderApi.apply({
      workflow_id: targetWorkflowId || undefined,
      name: customName || prompt.slice(0, 60),
      nodes: generated.nodes,
      edges: generated.edges,
    }),
    onSuccess: (data) => {
      toast.success(`Workflow ${data.action} successfully`)
      setGenerated(null)
      setPrompt('')
      setTargetWorkflowId('')
      setPage('workflows')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to apply'),
  })

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>AI Workflow Builder</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Describe what you want in plain English — the AI will generate a real, runnable workflow</p>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        <div style={{ maxWidth: 800 }}>
          {/* Prompt area */}
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 16 }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', display: 'block', marginBottom: 10 }}>
              Describe your workflow
            </label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="e.g. When I receive a webhook with order data, validate it, look up the customer in Postgres, use AI to generate a personalized message, get human approval for orders over $500, then send a WhatsApp message..."
              style={{ width: '100%', minHeight: 100, padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit', lineHeight: 1.5 }}
            />

            <div style={{ display: 'flex', gap: 12, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <select value={targetWorkflowId} onChange={e => setTargetWorkflowId(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 12 }}>
                  <option value="">Create new workflow</option>
                  {workflows.map((w: any) => <option key={w.id} value={w.id}>Update: {w.name}</option>)}
                </select>
              </div>
              <button
                onClick={() => generateMut.mutate()}
                disabled={!prompt.trim() || generateMut.isPending}
                style={{ padding: '9px 20px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8, opacity: (!prompt.trim() || generateMut.isPending) ? 0.5 : 1, flexShrink: 0 }}>
                {generateMut.isPending ? (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ animation: 'spin 1s linear infinite' }}><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>
                    Generating…
                  </>
                ) : (
                  <>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                    Generate Workflow
                  </>
                )}
              </button>
            </div>

            {/* Example prompts */}
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6 }}>Try an example:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {EXAMPLE_PROMPTS.map((ex, i) => (
                  <button key={i} onClick={() => setPrompt(ex)}
                    style={{ padding: '4px 10px', background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text3)', fontSize: 11, cursor: 'pointer', textAlign: 'left', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Generated workflow preview */}
          {generated && (
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 12, overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
                <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)', flex: 1 }}>Proposed Workflow</span>
                <button onClick={() => generateMut.mutate()} disabled={generateMut.isPending}
                  style={{ padding: '5px 12px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)', borderRadius: 6, cursor: 'pointer', fontSize: 12 }}>
                  ↺ Regenerate
                </button>
              </div>

              <div style={{ padding: '16px 20px' }}>
                {/* Explanation */}
                {generated.explanation && (
                  <div style={{ background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 16, fontSize: 13, color: 'var(--text2)', lineHeight: 1.5 }}>
                    {generated.explanation}
                  </div>
                )}

                {/* Node graph preview */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)', marginBottom: 8 }}>Node Graph</div>
                  <NodePreview nodes={generated.nodes || []} edges={generated.edges || []} />
                </div>

                {/* Validation */}
                <ValidationDisplay validation={generated.validation} />

                {/* Node list */}
                <details style={{ marginTop: 12 }}>
                  <summary style={{ fontSize: 12, color: 'var(--text3)', cursor: 'pointer', userSelect: 'none' }}>
                    View raw node definitions ({(generated.nodes || []).length} nodes)
                  </summary>
                  <pre style={{ marginTop: 8, fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 200, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
                    {JSON.stringify({ nodes: generated.nodes, edges: generated.edges }, null, 2)}
                  </pre>
                </details>

                {/* Apply form */}
                {generated.validation?.valid !== false && (
                  <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>Apply this workflow</div>
                    {!targetWorkflowId && (
                      <div style={{ marginBottom: 10 }}>
                        <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 4 }}>Workflow name</label>
                        <input value={customName} onChange={e => setCustomName(e.target.value)}
                          placeholder={prompt.slice(0, 60) || 'AI-Generated Workflow'}
                          style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
                      </div>
                    )}
                    {targetWorkflowId && (
                      <div style={{ fontSize: 12, color: 'var(--yellow)', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 8, padding: '8px 12px', marginBottom: 10 }}>
                        ⚠ This will overwrite the existing workflow. A version snapshot will be saved first.
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => setGenerated(null)}
                        style={{ padding: '8px 16px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                        Discard
                      </button>
                      <button onClick={() => applyMut.mutate()} disabled={applyMut.isPending}
                        style={{ padding: '8px 20px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 13, opacity: applyMut.isPending ? 0.6 : 1 }}>
                        {applyMut.isPending ? 'Applying…' : `✓ Apply ${targetWorkflowId ? 'Update' : 'and Create'}`}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
