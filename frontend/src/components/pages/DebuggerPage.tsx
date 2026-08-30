import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { executionsApi, debugApi, costsApi } from '../../api/client'
import toast from 'react-hot-toast'

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  success: { color: 'var(--green)', bg: 'rgba(34,197,94,0.12)' },
  failed: { color: 'var(--red)', bg: 'rgba(239,68,68,0.12)' },
  error: { color: 'var(--red)', bg: 'rgba(239,68,68,0.12)' },
  running: { color: 'var(--accent)', bg: 'rgba(124,58,237,0.12)' },
  queued: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  waiting: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  cancelled: { color: 'var(--text3)', bg: 'var(--bg3)' },
}

function StatusBadge({ s }: { s: string }) {
  const st = STATUS_STYLE[s] ?? STATUS_STYLE.cancelled
  return <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700, color: st.color, background: st.bg, textTransform: 'uppercase', flexShrink: 0 }}>{s}</span>
}

function NodeDebugDetail({ nodeId, nodeData, executionId, onAction }: { nodeId: string; nodeData: any; executionId: string; onAction: () => void }) {
  const [tab, setTab] = useState<'input' | 'output' | 'error'>('output')

  const retryNodeMut = useMutation({
    mutationFn: () => debugApi.retryNode(executionId, nodeId),
    onSuccess: () => { toast.success('Node retried'); onAction() },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Retry failed'),
  })

  const replayFromMut = useMutation({
    mutationFn: () => debugApi.replayFrom(executionId, nodeId),
    onSuccess: () => { toast.success('Replay started from this node'); onAction() },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Replay failed'),
  })

  const status = nodeData?.status || 'unknown'
  const isFailed = status === 'error' || status === 'failed'

  return (
    <div style={{ background: 'var(--bg1)', border: '1px solid var(--accent)', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <StatusBadge s={status} />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{nodeId}</span>
        {nodeData?.duration_ms != null && (
          <span style={{ fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>{nodeData.duration_ms}ms</span>
        )}
      </div>

      {/* Timing */}
      {(nodeData?.started_at || nodeData?.finished_at) && (
        <div style={{ padding: '8px 14px', background: 'var(--bg)', borderBottom: '1px solid var(--border)', display: 'flex', gap: 20 }}>
          {nodeData.started_at && <div style={{ fontSize: 10, color: 'var(--text3)' }}>Start: <span style={{ color: 'var(--text2)', fontFamily: 'var(--mono)' }}>{new Date(nodeData.started_at).toLocaleTimeString()}</span></div>}
          {nodeData.finished_at && <div style={{ fontSize: 10, color: 'var(--text3)' }}>End: <span style={{ color: 'var(--text2)', fontFamily: 'var(--mono)' }}>{new Date(nodeData.finished_at).toLocaleTimeString()}</span></div>}
          {nodeData.retries > 0 && <div style={{ fontSize: 10, color: 'var(--yellow)' }}>Retries: {nodeData.retries}</div>}
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
        {(['output', 'input', 'error'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: '6px 14px', background: 'transparent', color: tab === t ? 'var(--accent)' : 'var(--text3)', fontSize: 11, fontWeight: 500, cursor: 'pointer', border: 'none', borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent', textTransform: 'capitalize' }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ padding: 12 }}>
        {tab === 'output' && (
          <pre style={{ margin: 0, fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 180, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
            {nodeData?.output_data != null ? JSON.stringify(nodeData.output_data, null, 2) : '(no output)'}
          </pre>
        )}
        {tab === 'input' && (
          <pre style={{ margin: 0, fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 180, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
            {nodeData?.input_data != null ? JSON.stringify(nodeData.input_data, null, 2) : '(no input)'}
          </pre>
        )}
        {tab === 'error' && (
          <pre style={{ margin: 0, fontSize: 10, color: isFailed ? 'var(--red)' : 'var(--text3)', background: 'rgba(239,68,68,0.05)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 180, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
            {nodeData?.error_traceback || nodeData?.error || '(no error)'}
          </pre>
        )}
      </div>

      {isFailed && (
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
          <button onClick={() => retryNodeMut.mutate()} disabled={retryNodeMut.isPending}
            style={{ padding: '5px 12px', background: 'rgba(245,158,11,0.1)', border: '1px solid var(--yellow)', color: 'var(--yellow)', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
            ↺ Retry Node
          </button>
          <button onClick={() => replayFromMut.mutate()} disabled={replayFromMut.isPending}
            style={{ padding: '5px 12px', background: 'rgba(124,58,237,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
            ▶ Replay from Here
          </button>
        </div>
      )}
    </div>
  )
}

export default function DebuggerPage() {
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const { data: listData, isLoading: listLoading } = useQuery({
    queryKey: ['executions-debug'],
    queryFn: () => executionsApi.list(),
    refetchInterval: 5000,
  })

  const { data: debugData, refetch: refetchDebug } = useQuery({
    queryKey: ['execution-debug', selectedId],
    queryFn: () => debugApi.getDebugInfo(selectedId!),
    enabled: !!selectedId,
    refetchInterval: (d) => (d as any)?.status === 'running' ? 2000 : false,
  })

  const { data: costData } = useQuery({
    queryKey: ['execution-cost', selectedId],
    queryFn: () => costsApi.getExecutionCosts(selectedId!),
    enabled: !!selectedId,
  })

  const replayMut = useMutation({
    mutationFn: () => debugApi.replay(selectedId!),
    onSuccess: () => { toast.success('Execution replayed'); qc.invalidateQueries({ queryKey: ['executions-debug'] }) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Replay failed'),
  })

  const executions: any[] = (listData?.executions ?? []).filter((e: any) => !filter || e.status === filter)
  const nodeResults: Record<string, any> = debugData?.node_results ?? {}
  const nodeList = Object.entries(nodeResults).sort(([, a]: any, [, b]: any) => {
    if (a?.started_at && b?.started_at) return new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    return 0
  })

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ marginBottom: 16 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Execution Debugger</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Inspect node-by-node execution details, inputs/outputs, errors, and timing</p>
        </div>
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)' }}>
          {['', 'running', 'success', 'failed', 'queued'].map(s => (
            <button key={s} onClick={() => setFilter(s)}
              style={{ padding: '7px 14px', background: 'transparent', color: filter === s ? 'var(--accent)' : 'var(--text3)', fontSize: 12, fontWeight: 500, cursor: 'pointer', border: 'none', borderBottom: filter === s ? '2px solid var(--accent)' : '2px solid transparent', textTransform: s ? 'capitalize' : 'none' }}>
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
        {/* Execution list */}
        <div style={{ width: 320, borderRight: '1px solid var(--border)', overflow: 'auto', flexShrink: 0 }}>
          {listLoading && <div style={{ padding: 16, color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
          {executions.map((ex: any) => {
            const s = STATUS_STYLE[ex.status] ?? STATUS_STYLE.cancelled
            const dur = ex.started_at && ex.finished_at
              ? ((new Date(ex.finished_at).getTime() - new Date(ex.started_at).getTime()) / 1000).toFixed(1) + 's'
              : null
            return (
              <div key={ex.id} onClick={() => { setSelectedId(ex.id); setSelectedNodeId(null) }}
                style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', cursor: 'pointer', background: selectedId === ex.id ? 'var(--bg3)' : 'transparent', borderLeft: selectedId === ex.id ? '3px solid var(--accent)' : '3px solid transparent' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <StatusBadge s={ex.status} />
                  {dur && <span style={{ fontSize: 10, color: 'var(--text3)' }}>{dur}</span>}
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ex.id}</div>
                <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 2 }}>{ex.created_at ? new Date(ex.created_at).toLocaleString() : ''}</div>
              </div>
            )
          })}
        </div>

        {/* Debug detail */}
        {selectedId && debugData ? (
          <div style={{ flex: 1, overflow: 'auto', display: 'flex', gap: 0 }}>
            {/* Node timeline */}
            <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <StatusBadge s={debugData.status} />
                  <span style={{ fontSize: 12, color: 'var(--text3)', marginLeft: 10 }}>
                    {nodeList.length} nodes · {costData ? `$${costData.total_cost_usd?.toFixed(6)}` : ''}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => replayMut.mutate()} disabled={replayMut.isPending}
                    style={{ padding: '6px 12px', background: 'rgba(124,58,237,0.1)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: 7, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                    ↺ Replay All
                  </button>
                </div>
              </div>

              {/* Node timeline list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {nodeList.map(([nodeId, data]: [string, any]) => {
                  const status = data?.status || 'unknown'
                  const st = STATUS_STYLE[status] ?? STATUS_STYLE.cancelled
                  const isSelected = selectedNodeId === nodeId
                  return (
                    <div key={nodeId}>
                      <div onClick={() => setSelectedNodeId(isSelected ? null : nodeId)}
                        style={{ padding: '10px 14px', background: isSelected ? 'var(--bg3)' : 'var(--bg2)', border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: st.color, flexShrink: 0 }} />
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{nodeId}</span>
                        {data?.duration_ms != null && <span style={{ fontSize: 10, color: 'var(--text3)', flexShrink: 0 }}>{data.duration_ms}ms</span>}
                        <StatusBadge s={status} />
                      </div>
                      {isSelected && (
                        <div style={{ marginTop: 4 }}>
                          <NodeDebugDetail
                            nodeId={nodeId}
                            nodeData={data}
                            executionId={selectedId}
                            onAction={() => { qc.invalidateQueries({ queryKey: ['execution-debug', selectedId] }); refetchDebug() }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {/* Cost breakdown */}
              {costData && costData.node_costs?.length > 0 && (
                <div style={{ marginTop: 24 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)', marginBottom: 10 }}>
                    AI Cost Breakdown — Total: ${costData.total_cost_usd?.toFixed(6)}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {costData.node_costs.map((nc: any) => (
                      <div key={nc.node_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 7 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text3)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{nc.node_id}</span>
                        <span style={{ fontSize: 10, color: 'var(--text2)', fontFamily: 'var(--mono)' }}>{nc.model}</span>
                        <span style={{ fontSize: 10, color: 'var(--text3)' }}>{(nc.total_tokens || 0).toLocaleString()} tok</span>
                        <span style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 600 }}>${(nc.cost_usd || 0).toFixed(6)}</span>
                        <span style={{ fontSize: 10, color: 'var(--text3)' }}>{nc.latency_ms}ms</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Global error */}
              {debugData.error && (
                <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(239,68,68,0.06)', border: '1px solid var(--red)', borderRadius: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--red)', marginBottom: 6 }}>Execution Error</div>
                  <pre style={{ margin: 0, fontSize: 10, color: 'var(--red)', fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>
                    {debugData.error}
                  </pre>
                </div>
              )}
            </div>
          </div>
        ) : selectedId ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 13 }}>
            Loading debug info…
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 13 }}>
            Select an execution to inspect
          </div>
        )}
      </div>
    </div>
  )
}
