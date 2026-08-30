import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { versionsApi, workflowsApi } from '../../api/client'
import toast from 'react-hot-toast'

function DiffView({ diff }: { diff: any }) {
  if (!diff) return null

  const { nodes_added = [], nodes_removed = [], nodes_changed = [], edges_added = [], edges_removed = [], config_changes = {}, summary } = diff

  return (
    <div>
      {summary && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          {[
            { label: 'Nodes Added', value: summary.added, color: 'var(--green)' },
            { label: 'Nodes Removed', value: summary.removed, color: 'var(--red)' },
            { label: 'Nodes Changed', value: summary.changed, color: 'var(--yellow)' },
            { label: 'Edges Added', value: summary.edges_added, color: 'var(--green)' },
            { label: 'Edges Removed', value: summary.edges_removed, color: 'var(--red)' },
          ].map(m => (
            <div key={m.label} style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 14px', textAlign: 'center' }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: m.value > 0 ? m.color : 'var(--text3)' }}>{m.value}</div>
              <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{m.label}</div>
            </div>
          ))}
        </div>
      )}

      {nodes_added.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--green)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>+ Added Nodes</div>
          {nodes_added.map((n: any) => (
            <div key={n.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 10px', background: 'rgba(34,197,94,0.06)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 6, marginBottom: 4 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--green)' }}>{n.type}</span>
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>id: {n.id}</span>
            </div>
          ))}
        </div>
      )}

      {nodes_removed.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--red)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>- Removed Nodes</div>
          {nodes_removed.map((n: any) => (
            <div key={n.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '6px 10px', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 6, marginBottom: 4 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--red)' }}>{n.type}</span>
              <span style={{ fontSize: 11, color: 'var(--text3)' }}>id: {n.id}</span>
            </div>
          ))}
        </div>
      )}

      {nodes_changed.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--yellow)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>~ Modified Nodes</div>
          {nodes_changed.map((n: any) => {
            const changes = config_changes[n.id] || {}
            return (
              <div key={n.id} style={{ padding: '8px 10px', background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 6, marginBottom: 6 }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--yellow)', marginBottom: 4 }}>{n.type} ({n.id})</div>
                {Object.entries(changes).map(([field, ch]: [string, any]) => (
                  <div key={field} style={{ fontSize: 11, color: 'var(--text3)', paddingLeft: 8 }}>
                    <span style={{ color: 'var(--text2)' }}>{field}:</span>
                    {' '}
                    <span style={{ color: 'var(--red)', textDecoration: 'line-through', fontFamily: 'var(--mono)' }}>{JSON.stringify(ch.old)}</span>
                    {' → '}
                    <span style={{ color: 'var(--green)', fontFamily: 'var(--mono)' }}>{JSON.stringify(ch.new)}</span>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )}

      {edges_added.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--green)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>+ Added Edges</div>
          {edges_added.map((e: any, i: number) => (
            <div key={i} style={{ fontSize: 11, color: 'var(--green)', fontFamily: 'var(--mono)', padding: '3px 8px' }}>{e.source} → {e.target}</div>
          ))}
        </div>
      )}

      {edges_removed.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--red)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>- Removed Edges</div>
          {edges_removed.map((e: any, i: number) => (
            <div key={i} style={{ fontSize: 11, color: 'var(--red)', fontFamily: 'var(--mono)', padding: '3px 8px' }}>{e.source} → {e.target}</div>
          ))}
        </div>
      )}

      {nodes_added.length === 0 && nodes_removed.length === 0 && nodes_changed.length === 0 && edges_added.length === 0 && edges_removed.length === 0 && (
        <div style={{ color: 'var(--text3)', fontSize: 13 }}>No differences between these versions</div>
      )}
    </div>
  )
}

export default function VersionsPage() {
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('')
  const [compareV1, setCompareV1] = useState<number | null>(null)
  const [compareV2, setCompareV2] = useState<number | null>(null)
  const [showDiff, setShowDiff] = useState(false)
  const qc = useQueryClient()

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list })
  const workflows: any[] = wfData?.workflows ?? []

  const { data: versions, isLoading } = useQuery({
    queryKey: ['versions', selectedWorkflowId],
    queryFn: () => versionsApi.list(selectedWorkflowId),
    enabled: !!selectedWorkflowId,
  })

  const { data: diff, refetch: fetchDiff, isFetching: diffLoading } = useQuery({
    queryKey: ['version-diff', selectedWorkflowId, compareV1, compareV2],
    queryFn: () => versionsApi.diff(selectedWorkflowId, compareV1!, compareV2!),
    enabled: false,
  })

  const rollbackMut = useMutation({
    mutationFn: (version: number) => versionsApi.rollback(selectedWorkflowId, version),
    onSuccess: () => {
      toast.success('Workflow rolled back')
      qc.invalidateQueries({ queryKey: ['workflows'] })
      qc.invalidateQueries({ queryKey: ['versions', selectedWorkflowId] })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Rollback failed'),
  })

  const publishMut = useMutation({
    mutationFn: (version: number) => versionsApi.publish(selectedWorkflowId, version),
    onSuccess: () => {
      toast.success('Version marked as production')
      qc.invalidateQueries({ queryKey: ['versions', selectedWorkflowId] })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const versionList: any[] = Array.isArray(versions) ? versions : []

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Version History</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Browse, compare, and rollback workflow versions. Each save creates a snapshot.</p>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ minWidth: 240 }}>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Select Workflow</label>
            <select value={selectedWorkflowId} onChange={e => { setSelectedWorkflowId(e.target.value); setCompareV1(null); setCompareV2(null); setShowDiff(false) }}
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              <option value="">Choose a workflow…</option>
              {workflows.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          {versionList.length >= 2 && (
            <>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Compare v</label>
                <select value={compareV1 ?? ''} onChange={e => setCompareV1(e.target.value ? parseInt(e.target.value) : null)}
                  style={{ padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
                  <option value="">—</option>
                  {versionList.map((v: any) => <option key={v.version} value={v.version}>v{v.version}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>with v</label>
                <select value={compareV2 ?? ''} onChange={e => setCompareV2(e.target.value ? parseInt(e.target.value) : null)}
                  style={{ padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
                  <option value="">—</option>
                  {versionList.map((v: any) => <option key={v.version} value={v.version}>v{v.version}</option>)}
                </select>
              </div>
              <button
                onClick={() => { fetchDiff(); setShowDiff(true) }}
                disabled={!compareV1 || !compareV2 || compareV1 === compareV2 || diffLoading}
                style={{ padding: '8px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 13, opacity: (!compareV1 || !compareV2 || compareV1 === compareV2) ? 0.5 : 1 }}>
                {diffLoading ? 'Comparing…' : 'Compare Diff'}
              </button>
            </>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '16px 32px 32px', display: 'flex', gap: 24 }}>
        {/* Version list */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {!selectedWorkflowId && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              Select a workflow to view its version history
            </div>
          )}
          {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
          {selectedWorkflowId && !isLoading && versionList.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
              No version history yet. Versions are created automatically when you save a workflow.
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {versionList.map((v: any) => (
              <div key={v.version} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{ width: 36, height: 36, background: v.is_published ? 'rgba(34,197,94,0.12)' : 'var(--bg3)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: v.is_published ? 'var(--green)' : 'var(--text3)' }}>v{v.version}</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>
                      {v.change_summary || 'Manual save'}
                    </span>
                    {v.is_published && (
                      <span style={{ fontSize: 10, padding: '1px 7px', background: 'rgba(34,197,94,0.12)', color: 'var(--green)', borderRadius: 5, fontWeight: 700 }}>PRODUCTION</span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                    {v.created_by ? `by ${v.created_by.slice(0, 8)}…` : ''}
                    {v.created_at ? ` · ${new Date(v.created_at).toLocaleString()}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  {!v.is_published && (
                    <button onClick={() => { if (confirm(`Mark v${v.version} as production?`)) publishMut.mutate(v.version) }}
                      style={{ padding: '5px 10px', background: 'rgba(34,197,94,0.08)', border: '1px solid var(--green)', color: 'var(--green)', borderRadius: 6, cursor: 'pointer', fontSize: 11, fontWeight: 600 }}>
                      Publish
                    </button>
                  )}
                  <button onClick={() => { if (confirm(`Rollback to v${v.version}? Current state will be saved first.`)) rollbackMut.mutate(v.version) }}
                    style={{ padding: '5px 10px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 6, cursor: 'pointer', fontSize: 11 }}>
                    Restore
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Diff panel */}
        {showDiff && diff && (
          <div style={{ width: 400, flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
                Diff: v{compareV1} → v{compareV2}
              </span>
              <button onClick={() => setShowDiff(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
              <DiffView diff={diff} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
