import React, { useCallback, useEffect, useRef, useState } from 'react'
import ReactFlow, {
  Background, Controls, MiniMap, BackgroundVariant,
  addEdge, applyNodeChanges, applyEdgeChanges,
  type Node, type Edge, type Connection, type NodeChange, type EdgeChange,
  MarkerType, ReactFlowProvider, useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'
import dagre from 'dagre'
import { useQueryClient } from '@tanstack/react-query'
import { workflowsApi, executionsApi } from '../../api/client'
import { useStore } from '../../store'
import { getNodeDef, PROVIDER_COLORS } from '../../types/nodes'
import AutoflowNode from '../nodes/AutoflowNode'
import NodePicker from '../panels/NodePicker'
import NodePanel from '../panels/NodePanel'
import ExecutionsPanel from '../panels/ExecutionsPanel'
import TriggersPanel from '../panels/TriggersPanel'
import type { WFNode } from '../../types'
import toast from 'react-hot-toast'

const NODE_TYPES = { autoflow: AutoflowNode }

function wfNodeToRF(n: WFNode, idx: number): Node {
  return {
    id: n.id,
    type: 'autoflow',
    position: n.position ?? { x: 120 + idx * 260, y: 200 },
    data: { ...n, type: n.type },
    draggable: true,
  }
}

function rfNodeToWF(n: Node): WFNode {
  return {
    id: n.id,
    type: n.data.type,
    label: n.data.label,
    config: n.data.config ?? {},
    credential_id: n.data.credential_id,
    retry: n.data.retry,
    position: n.position,
  }
}

function autoLayout(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 70, ranksep: 140 })
  nodes.forEach(n => g.setNode(n.id, { width: 210, height: 70 }))
  edges.forEach(e => g.setEdge(e.source, e.target))
  dagre.layout(g)
  return nodes.map(n => {
    const pos = g.node(n.id)
    return { ...n, position: { x: pos.x - 105, y: pos.y - 35 } }
  })
}

const EDGE_STYLE = {
  type: 'smoothstep',
  markerEnd: { type: MarkerType.ArrowClosed, color: '#7c3aed' },
  style: { stroke: '#7c3aed', strokeWidth: 2, opacity: 0.8 },
}

function EditorInner() {
  const qc = useQueryClient()
  const rf = useReactFlow()
  const { activeWorkflow, setActiveWorkflow, credentials } = useStore()
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [showPicker, setShowPicker] = useState(false)
  const [rightPanel, setRightPanel] = useState<'node' | 'executions' | 'triggers' | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const pollRef = useRef<any>(null)
  const wf = activeWorkflow!

  useEffect(() => {
    const def = wf.definition ?? { nodes: [], edges: [] }
    setNodes((def.nodes ?? []).map((n: WFNode, i: number) => wfNodeToRF(n, i)))
    setEdges((def.edges ?? []).map((e: any, i: number) => ({
      id: `e-${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      ...EDGE_STYLE,
    })))
  }, [wf.id])

  const onNodesChange = useCallback((c: NodeChange[]) => setNodes(n => applyNodeChanges(c, n)), [])
  const onEdgesChange = useCallback((c: EdgeChange[]) => setEdges(e => applyEdgeChanges(c, e)), [])
  const onConnect = useCallback((conn: Connection) => {
    setEdges(eds => addEdge({ ...conn, id: `e-${conn.source}-${conn.target}-${Date.now()}`, ...EDGE_STYLE }, eds))
  }, [])

  const onNodeClick = useCallback((_: any, node: Node) => {
    setSelectedNodeId(node.id)
    setRightPanel('node')
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
    if (rightPanel === 'node') setRightPanel(null)
  }, [rightPanel])

  const addNode = (type: string) => {
    const id = `node_${Date.now()}`
    const def = getNodeDef(type)
    const vp = rf.getViewport()
    const cx = (window.innerWidth / 2 - vp.x) / vp.zoom
    const cy = (300 - vp.y) / vp.zoom
    setNodes(ns => [...ns, {
      id, type: 'autoflow',
      position: { x: cx - 100, y: cy - 35 },
      data: { id, type, label: def?.label ?? type, config: {} },
      draggable: true,
    }])
    setSelectedNodeId(id)
    setRightPanel('node')
    setShowPicker(false)
  }

  const deleteNode = (nodeId: string) => {
    setNodes(ns => ns.filter(n => n.id !== nodeId))
    setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId))
    setSelectedNodeId(null)
    setRightPanel(null)
  }

  const updateNode = (updated: WFNode) => {
    setNodes(ns => ns.map(n => n.id === updated.id
      ? { ...n, data: { ...n.data, ...updated, type: updated.type } } : n))
    toast.success('Saved')
  }

  const buildDef = () => ({
    nodes: nodes.map(rfNodeToWF),
    edges: edges.map(e => ({ source: e.source, target: e.target })),
  })

  const save = async () => {
    setSaving(true)
    try {
      const definition = buildDef()
      const updated = await workflowsApi.update(wf.id, { definition })
      setActiveWorkflow({ ...wf, definition })
      qc.invalidateQueries({ queryKey: ['workflows'] })
      toast.success('Workflow saved')
    } catch { toast.error('Save failed') }
    finally { setSaving(false) }
  }

  const toggleActive = async () => {
    try {
      if (wf.status === 'active') {
        await workflowsApi.deactivate(wf.id)
        setActiveWorkflow({ ...wf, status: 'inactive' })
      } else {
        await workflowsApi.activate(wf.id)
        setActiveWorkflow({ ...wf, status: 'active' })
      }
      qc.invalidateQueries({ queryKey: ['workflows'] })
    } catch { toast.error('Failed') }
  }

  const runNow = async () => {
    setRunning(true)
    try {
      const { execution_id } = await workflowsApi.execute(wf.id)
      toast.success('Execution started')
      let attempts = 0
      pollRef.current = setInterval(async () => {
        attempts++
        try {
          const ex = await executionsApi.get(execution_id)
          const statuses: Record<string, string> = {}
          Object.entries(ex.node_results ?? {}).forEach(([nid, r]: [string, any]) => { statuses[nid] = r.status })
          setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, status: statuses[n.id] } })))
          if (['success', 'failed', 'cancelled'].includes(ex.status) || attempts > 60) {
            clearInterval(pollRef.current)
            setRunning(false)
            if (ex.status === 'success') toast.success('Execution completed')
            else if (ex.status === 'failed') toast.error('Execution failed')
          }
        } catch { clearInterval(pollRef.current); setRunning(false) }
      }, 2000)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Run failed')
      setRunning(false)
    }
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const selectedNode = nodes.find(n => n.id === selectedNodeId)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Toolbar */}
      <div style={{ height: 52, background: 'var(--bg1)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8, flexShrink: 0 }}>
        <button onClick={() => setActiveWorkflow(null)} style={{ background: 'transparent', color: 'var(--text3)', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, padding: '5px 8px', borderRadius: 6, border: 'none', cursor: 'pointer' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          Back
        </button>
        <div style={{ width: 1, height: 20, background: 'var(--border)' }} />
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)' }}>{wf.name}</span>
        <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700,
          background: wf.status === 'active' ? 'rgba(34,197,94,0.12)' : 'var(--bg3)',
          color: wf.status === 'active' ? 'var(--green)' : 'var(--text3)' }}>
          {wf.status}
        </span>
        <div style={{ flex: 1 }} />

        <Btn active={rightPanel === 'triggers'} onClick={() => setRightPanel(p => p === 'triggers' ? null : 'triggers')}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          Triggers
        </Btn>
        <Btn active={rightPanel === 'executions'} onClick={() => setRightPanel(p => p === 'executions' ? null : 'executions')}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          History
        </Btn>
        <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

        <Btn onClick={() => setNodes(ns => autoLayout(ns, edges))}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="21" y1="10" x2="3" y2="10"/><line x1="21" y1="6" x2="3" y2="6"/><line x1="21" y1="14" x2="3" y2="14"/><line x1="21" y1="18" x2="3" y2="18"/></svg>
          Layout
        </Btn>
        <button onClick={() => setShowPicker(p => !p)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', background: showPicker ? 'var(--bg3)' : 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add Node
        </button>
        <button onClick={runNow} disabled={running} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.25)', color: 'var(--green)', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: running ? 'not-allowed' : 'pointer', opacity: running ? 0.7 : 1 }}>
          {running
            ? <><Spin />Running</>
            : <><svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>Run</>}
        </button>
        <button onClick={toggleActive} style={{ padding: '6px 14px', background: wf.status === 'active' ? 'rgba(239,68,68,0.1)' : 'rgba(124,58,237,0.1)', border: `1px solid ${wf.status === 'active' ? 'rgba(239,68,68,0.25)' : 'rgba(124,58,237,0.25)'}`, color: wf.status === 'active' ? 'var(--red)' : 'var(--accent)', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          {wf.status === 'active' ? 'Deactivate' : 'Activate'}
        </button>
        <button onClick={save} disabled={saving} style={{ padding: '6px 18px', background: 'var(--accent)', color: '#fff', borderRadius: 7, fontSize: 12, fontWeight: 700, border: 'none', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>

      {/* Canvas + panels */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {showPicker && <NodePicker onAdd={addNode} onClose={() => setShowPicker(false)} />}

        <div style={{ flex: 1, position: 'relative' }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} onNodeClick={onNodeClick} onPaneClick={onPaneClick}
            nodeTypes={NODE_TYPES} fitView fitViewOptions={{ padding: 0.25 }}
            minZoom={0.15} maxZoom={2.5} deleteKeyCode="Delete"
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={EDGE_STYLE}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#252540" />
            <Controls showInteractive={false} />
            <MiniMap
              nodeColor={n => { const def = getNodeDef(n.data?.type); return def ? (PROVIDER_COLORS[def.provider] ?? '#6366f1') : '#6366f1' }}
              maskColor="rgba(10,10,20,0.7)"
            />
          </ReactFlow>

          {nodes.length === 0 && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', gap: 16 }}>
              <div style={{ width: 72, height: 72, border: '2px dashed var(--border2)', borderRadius: 18, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" strokeWidth="1.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              </div>
              <p style={{ color: 'var(--text3)', fontSize: 14 }}>Click <strong style={{ color: 'var(--text2)' }}>Add Node</strong> to build your workflow</p>
            </div>
          )}
        </div>

        {rightPanel === 'node' && selectedNode && (
          <NodePanel node={rfNodeToWF(selectedNode)} credentials={credentials}
            allNodes={nodes.map(rfNodeToWF)} edges={edges.map(e => ({ source: e.source, target: e.target }))}
            onChange={updateNode} onDelete={() => deleteNode(selectedNode.id)} onClose={() => setRightPanel(null)} />
        )}
        {rightPanel === 'executions' && <ExecutionsPanel workflowId={wf.id} onClose={() => setRightPanel(null)} />}
        {rightPanel === 'triggers' && <TriggersPanel workflowId={wf.id} onClose={() => setRightPanel(null)} />}
      </div>
    </div>
  )
}

function Btn({ children, onClick, active }: any) {
  return (
    <button onClick={onClick} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', background: active ? 'var(--bg3)' : 'transparent', border: `1px solid ${active ? 'var(--border2)' : 'transparent'}`, color: active ? 'var(--text)' : 'var(--text3)', borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>
      {children}
    </button>
  )
}

function Spin() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0" opacity={0.3}/><path d="M12 3a9 9 0 019 9"/>
    </svg>
  )
}

export default function WorkflowEditor() {
  return <ReactFlowProvider><EditorInner /></ReactFlowProvider>
}
