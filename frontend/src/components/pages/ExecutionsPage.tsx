import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { executionsApi } from '../../api/client'
import type { Execution } from '../../types'

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  success: { color: 'var(--green)', bg: 'rgba(34,197,94,0.12)' },
  failed: { color: 'var(--red)', bg: 'rgba(239,68,68,0.12)' },
  running: { color: 'var(--accent)', bg: 'rgba(124,58,237,0.12)' },
  queued: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  cancelled: { color: 'var(--text3)', bg: 'var(--bg3)' },
}

export default function ExecutionsPage() {
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Execution | null>(null)
  const [filter, setFilter] = useState('')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['executions-all'],
    queryFn: () => executionsApi.list(),
    refetchInterval: 5000,
  })

  const cancelMut = useMutation({
    mutationFn: executionsApi.cancel,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['executions-all'] }),
  })

  const executions: Execution[] = (data?.executions ?? []).filter((e: Execution) =>
    !filter || e.status === filter
  )

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Executions</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>All workflow runs across all workflows</p>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => refetch()} style={{ padding: '7px 14px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
          {['', 'running', 'success', 'failed', 'queued', 'cancelled'].map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{ padding: '7px 14px', background: 'transparent', color: filter === s ? 'var(--accent)' : 'var(--text3)', fontSize: 12, fontWeight: 500, cursor: 'pointer', border: 'none', borderBottom: filter === s ? '2px solid var(--accent)' : '2px solid transparent', textTransform: s ? 'capitalize' : 'none' }}>
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', gap: 0 }}>
        {/* List */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 32px' }}>
          {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: 16 }}>Loading…</div>}
          {!isLoading && executions.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No executions yet</div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {executions.map((ex: Execution) => {
              const s = STATUS_STYLE[ex.status] ?? STATUS_STYLE.cancelled
              const dur = ex.started_at && ex.finished_at
                ? ((new Date(ex.finished_at).getTime() - new Date(ex.started_at).getTime()) / 1000).toFixed(1) + 's'
                : null
              const isSelected = selected?.id === ex.id
              return (
                <div key={ex.id} onClick={() => setSelected(isSelected ? null : ex)}
                  style={{ padding: '12px 16px', background: isSelected ? 'var(--bg3)' : 'var(--bg2)', border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 10, cursor: 'pointer', transition: 'all 0.1s' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700, color: s.color, background: s.bg, textTransform: 'uppercase', flexShrink: 0 }}>
                      {ex.status}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text)', fontFamily: 'var(--mono)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ex.id.slice(0, 8)}…
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>{ex.trigger_type}</span>
                    {dur && <span style={{ fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>{dur}</span>}
                    <span style={{ fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>{new Date(ex.created_at).toLocaleString()}</span>
                    {['queued', 'running'].includes(ex.status) && (
                      <button onClick={e => { e.stopPropagation(); cancelMut.mutate(ex.id) }}
                        style={{ padding: '3px 8px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', borderRadius: 5, fontSize: 10, border: 'none', cursor: 'pointer' }}>
                        Cancel
                      </button>
                    )}
                  </div>
                  {ex.error && <div style={{ marginTop: 8, fontSize: 11, color: 'var(--red)', fontFamily: 'var(--mono)', wordBreak: 'break-word' }}>{ex.error.slice(0, 200)}</div>}
                </div>
              )
            })}
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div style={{ width: 380, background: 'var(--bg1)', borderLeft: '1px solid var(--border)', overflow: 'auto', flexShrink: 0 }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>Execution Detail</span>
              <button onClick={() => setSelected(null)} style={{ background: 'transparent', color: 'var(--text3)', border: 'none', cursor: 'pointer' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>ID</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)', wordBreak: 'break-all' }}>{selected.id}</div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Trigger Data</div>
                <pre style={{ fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 120, margin: 0, fontFamily: 'var(--mono)' }}>
                  {JSON.stringify(selected.trigger_data, null, 2)}
                </pre>
              </div>
              {selected.error && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10, color: 'var(--red)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>Error</div>
                  <pre style={{ fontSize: 10, color: 'var(--red)', background: 'rgba(239,68,68,0.05)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 200, margin: 0, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
                    {selected.error}
                  </pre>
                </div>
              )}
              <div>
                <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Node Results</div>
                {Object.keys(selected.node_results ?? {}).length === 0
                  ? <div style={{ fontSize: 12, color: 'var(--text3)' }}>No results</div>
                  : Object.entries(selected.node_results ?? {}).map(([nodeId, result]: [string, any]) => (
                    <div key={nodeId} style={{ marginBottom: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: result.status === 'error' ? 'var(--red)' : 'var(--green)', marginBottom: 3 }}>
                        {nodeId} — {result.status}
                      </div>
                      <pre style={{ fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 8, borderRadius: 6, overflow: 'auto', maxHeight: 100, margin: 0, fontFamily: 'var(--mono)', whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(result.output ?? result.error, null, 2)}
                      </pre>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}