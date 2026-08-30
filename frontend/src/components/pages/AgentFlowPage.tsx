import React, { useState } from 'react'
import { useStore } from '../../store'
import { useQuery } from '@tanstack/react-query'
import { workflowsApi } from '../../api/client'
import toast from 'react-hot-toast'

const AGENT_NODE_TYPES = [
  {
    type: 'agent.react',
    label: 'ReAct Agent',
    desc: 'Reasoning + Acting agent with tool-calling loop',
    color: '#7c3aed',
    config: { model: 'claude-sonnet-4-6', system_prompt: '', tools: [], max_iterations: 10 },
  },
  {
    type: 'agentflow.planner',
    label: 'Planner',
    desc: 'Breaks a goal into ordered subtasks',
    color: '#0ea5e9',
    config: { model: 'claude-sonnet-4-6', goal_field: 'goal', output_field: 'plan' },
  },
  {
    type: 'agentflow.router',
    label: 'Router',
    desc: 'Routes to different branches based on LLM decision',
    color: '#f59e0b',
    config: { model: 'gpt-4o-mini', routes: [], input_field: 'input' },
  },
  {
    type: 'agentflow.loop',
    label: 'Loop',
    desc: 'Repeats until condition is met (max iterations enforced)',
    color: '#84cc16',
    config: { max_iterations: 5, condition_field: 'done', condition_value: true },
  },
  {
    type: 'agentflow.memory_read',
    label: 'Memory Read',
    desc: 'Read agent state from conversation memory',
    color: '#06b6d4',
    config: { conversation_id_field: 'conversation_id', limit: 20 },
  },
  {
    type: 'agentflow.memory_write',
    label: 'Memory Write',
    desc: 'Persist data to agent memory for future turns',
    color: '#06b6d4',
    config: { conversation_id_field: 'conversation_id', role: 'assistant', content_field: 'output' },
  },
  {
    type: 'agentflow.parallel_agents',
    label: 'Parallel Agents',
    desc: 'Execute multiple sub-workflows concurrently',
    color: '#8b5cf6',
    config: { workflow_ids: [] },
  },
  {
    type: 'agentflow.sequential_agents',
    label: 'Sequential Agents',
    desc: 'Execute sub-workflows in sequence, passing output forward',
    color: '#8b5cf6',
    config: { workflow_ids: [] },
  },
  {
    type: 'agentflow.tool_caller',
    label: 'Tool Caller',
    desc: 'Call any registered tool by name with LLM-generated args',
    color: '#e11d48',
    config: { tool_name: '', tool_description: '' },
  },
  {
    type: 'multiagent.supervisor',
    label: 'Multi-Agent Supervisor',
    desc: 'Orchestrates a pool of worker agents',
    color: '#f97316',
    config: { model: 'claude-sonnet-4-6', system_prompt: '', worker_agents: [] },
  },
  {
    type: 'multiagent.worker',
    label: 'Agent Worker',
    desc: 'Executes tasks assigned by a supervisor',
    color: '#f97316',
    config: { model: 'gpt-4o-mini', system_prompt: '', tools: [] },
  },
  {
    type: 'approval.wait',
    label: 'Human Approval',
    desc: 'Pauses execution until a human approves or rejects',
    color: '#ef4444',
    config: { assigned_to: '', message: '', expires_in_hours: 24 },
  },
  {
    type: 'mcp.call_tool',
    label: 'MCP Tool Call',
    desc: 'Call a tool exposed by an external MCP server',
    color: '#6366f1',
    config: { server_url: '', tool_name: '', arguments: {} },
  },
]

function NodeCard({ node, onClick }: { node: typeof AGENT_NODE_TYPES[0]; onClick: () => void }) {
  return (
    <div onClick={onClick}
      style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', cursor: 'pointer', transition: 'all 0.15s', display: 'flex', gap: 12, alignItems: 'flex-start' }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = node.color)}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
      <div style={{ width: 36, height: 36, background: `${node.color}18`, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, border: `1.5px solid ${node.color}40` }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={node.color} strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4"/></svg>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 3 }}>{node.label}</div>
        <div style={{ fontSize: 11, color: 'var(--text3)', lineHeight: 1.4 }}>{node.desc}</div>
        <div style={{ marginTop: 6, fontFamily: 'var(--mono)', fontSize: 10, color: node.color, opacity: 0.8 }}>{node.type}</div>
      </div>
    </div>
  )
}

function WorkflowWithAgents({ workflowId }: { workflowId: string }) {
  const { data } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
  })

  const wf = data
  if (!wf) return <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>

  const nodes = wf.definition?.nodes ?? []
  const agentNodes = nodes.filter((n: any) =>
    n.type?.startsWith('agent.') || n.type?.startsWith('agentflow.') || n.type?.startsWith('multiagent.')
  )

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>{wf.name}</div>
      {agentNodes.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--text3)' }}>No agent nodes in this workflow</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {agentNodes.map((n: any) => (
            <div key={n.id} style={{ padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7 }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--accent)' }}>{n.type}</div>
              <div style={{ fontSize: 11, color: 'var(--text2)', marginTop: 2 }}>id: {n.id}</div>
              {n.config?.model && <div style={{ fontSize: 10, color: 'var(--text3)' }}>model: {n.config.model}</div>}
              {n.config?.tools?.length > 0 && <div style={{ fontSize: 10, color: 'var(--text3)' }}>tools: {n.config.tools.join(', ')}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AgentFlowPage() {
  const { setActiveWorkflow, setPage } = useStore()
  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('')

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list })
  const workflows: any[] = wfData?.workflows ?? []

  const categories = [
    { id: 'all', label: 'All' },
    { id: 'agents', label: 'Agents' },
    { id: 'flow', label: 'Flow Control' },
    { id: 'memory', label: 'Memory' },
    { id: 'multi', label: 'Multi-Agent' },
  ]

  const categoryMap: Record<string, string[]> = {
    agents: ['agent.react', 'agentflow.tool_caller'],
    flow: ['agentflow.planner', 'agentflow.router', 'agentflow.loop'],
    memory: ['agentflow.memory_read', 'agentflow.memory_write'],
    multi: ['agentflow.parallel_agents', 'agentflow.sequential_agents', 'multiagent.supervisor', 'multiagent.worker', 'approval.wait', 'mcp.call_tool'],
  }

  const filtered = AGENT_NODE_TYPES.filter(n => {
    const matchesSearch = !search || n.label.toLowerCase().includes(search.toLowerCase()) || n.desc.toLowerCase().includes(search.toLowerCase()) || n.type.includes(search.toLowerCase())
    const matchesCategory = selectedCategory === 'all' || (categoryMap[selectedCategory] || []).includes(n.type)
    return matchesSearch && matchesCategory
  })

  const openWorkflowEditor = (wfId?: string) => {
    if (wfId) {
      const wf = workflows.find(w => w.id === wfId)
      if (wf) setActiveWorkflow(wf)
    } else {
      setPage('workflows')
    }
  }

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>AgentFlow</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Build autonomous AI agent workflows with planners, routers, memory, and multi-agent coordination</p>
          </div>
          <button onClick={() => setPage('workflows')}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Workflow
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: 0 }}>
        {/* Node catalog */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 32px 32px' }}>
          <div style={{ marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search node types…"
              style={{ flex: 1, minWidth: 200, padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }} />
            <div style={{ display: 'flex', gap: 4 }}>
              {categories.map(c => (
                <button key={c.id} onClick={() => setSelectedCategory(c.id)}
                  style={{ padding: '6px 12px', borderRadius: 6, border: `1px solid ${selectedCategory === c.id ? 'var(--accent)' : 'var(--border)'}`, background: selectedCategory === c.id ? 'rgba(124,58,237,0.1)' : 'transparent', color: selectedCategory === c.id ? 'var(--accent)' : 'var(--text3)', fontSize: 12, cursor: 'pointer' }}>
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
            {filtered.map(node => (
              <NodeCard
                key={node.type}
                node={node}
                onClick={() => {
                  // Navigate to workflow editor — user can drag nodes from the node picker
                  toast.success(`Add "${node.label}" to a workflow via the workflow editor`, { duration: 3000 })
                  setPage('workflows')
                }}
              />
            ))}
          </div>

          {filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text3)', fontSize: 13 }}>
              No node types match "{search}"
            </div>
          )}
        </div>

        {/* Existing agent workflows panel */}
        <div style={{ width: 300, borderLeft: '1px solid var(--border)', overflow: 'auto', flexShrink: 0 }}>
          <div style={{ padding: '16px 16px 8px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)', marginBottom: 10 }}>Workflows with Agents</div>
            <select value={selectedWorkflowId} onChange={e => setSelectedWorkflowId(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 12 }}>
              <option value="">Select a workflow…</option>
              {workflows.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div style={{ padding: 16 }}>
            {selectedWorkflowId ? (
              <>
                <WorkflowWithAgents workflowId={selectedWorkflowId} />
                <button onClick={() => openWorkflowEditor(selectedWorkflowId)}
                  style={{ marginTop: 12, width: '100%', padding: '8px 0', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                  Open in Editor →
                </button>
              </>
            ) : (
              <div style={{ color: 'var(--text3)', fontSize: 12 }}>Select a workflow to inspect its agent nodes</div>
            )}
          </div>

          {/* Architecture guide */}
          <div style={{ padding: '0 16px 16px' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Architecture Guide</div>
            {[
              { title: 'Single Agent', desc: 'ReAct or Tool Agent + tool nodes' },
              { title: 'Supervisor Pattern', desc: 'Supervisor → Workers (parallel or sequential)' },
              { title: 'Planner + Executor', desc: 'Planner → Router → specialized agents' },
              { title: 'Human-in-Loop', desc: 'Agent → Approval → Resume' },
              { title: 'RAG Agent', desc: 'Memory Read → Agent → Vector Search' },
            ].map(p => (
              <div key={p.title} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text2)' }}>{p.title}</div>
                <div style={{ fontSize: 10, color: 'var(--text3)' }}>{p.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
