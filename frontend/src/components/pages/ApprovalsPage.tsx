import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { approvalsApi } from '../../api/client'
import toast from 'react-hot-toast'

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  pending: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  approved: { color: 'var(--green)', bg: 'rgba(34,197,94,0.12)' },
  rejected: { color: 'var(--red)', bg: 'rgba(239,68,68,0.12)' },
  expired: { color: 'var(--text3)', bg: 'var(--bg3)' },
}

function Label({ s }: { s: string }) {
  const st = STATUS_STYLE[s] ?? STATUS_STYLE.pending
  return (
    <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700, color: st.color, background: st.bg, textTransform: 'uppercase', flexShrink: 0 }}>
      {s}
    </span>
  )
}

function DecideModal({ approval, onClose }: { approval: any; onClose: () => void }) {
  const qc = useQueryClient()
  const [action, setAction] = useState<'approve' | 'reject'>('approve')
  const [reason, setReason] = useState('')
  const [editedData, setEditedData] = useState(JSON.stringify(approval.trigger_data || {}, null, 2))

  const decideMut = useMutation({
    mutationFn: (d: any) => approvalsApi.decide(approval.id, d),
    onSuccess: () => {
      toast.success(`Execution ${action}d`)
      qc.invalidateQueries({ queryKey: ['approvals'] })
      onClose()
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const handleSubmit = () => {
    let edited: any = undefined
    if (action === 'approve') {
      try { edited = JSON.parse(editedData) } catch { toast.error('Invalid JSON in edited data'); return }
    }
    decideMut.mutate({ action, reason, edited_data: action === 'approve' ? edited : undefined })
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 12, width: 520, maxHeight: '80vh', overflow: 'auto', padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Review Approval</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Execution ID</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)' }}>{approval.execution_id}</div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Node</div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text2)' }}>{approval.node_id}</div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Action</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setAction('approve')}
              style={{ padding: '7px 16px', borderRadius: 8, border: `1px solid ${action === 'approve' ? 'var(--green)' : 'var(--border)'}`, background: action === 'approve' ? 'rgba(34,197,94,0.12)' : 'transparent', color: action === 'approve' ? 'var(--green)' : 'var(--text3)', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
              ✓ Approve
            </button>
            <button onClick={() => setAction('reject')}
              style={{ padding: '7px 16px', borderRadius: 8, border: `1px solid ${action === 'reject' ? 'var(--red)' : 'var(--border)'}`, background: action === 'reject' ? 'rgba(239,68,68,0.12)' : 'transparent', color: action === 'reject' ? 'var(--red)' : 'var(--text3)', cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
              ✗ Reject
            </button>
          </div>
        </div>

        {action === 'approve' && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Edit Payload (optional)</div>
            <textarea value={editedData} onChange={e => setEditedData(e.target.value)}
              style={{ width: '100%', minHeight: 120, padding: 10, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 11, resize: 'vertical', boxSizing: 'border-box' }} />
          </div>
        )}

        <div style={{ marginBottom: 20 }}>
          <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Reason (optional)</label>
          <input value={reason} onChange={e => setReason(e.target.value)} placeholder="Add a comment…"
            style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '8px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
            Cancel
          </button>
          <button onClick={handleSubmit} disabled={decideMut.isPending}
            style={{ padding: '8px 16px', background: action === 'approve' ? 'var(--green)' : 'var(--red)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, opacity: decideMut.isPending ? 0.6 : 1 }}>
            {decideMut.isPending ? 'Submitting…' : action === 'approve' ? '✓ Approve' : '✗ Reject'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ApprovalsPage() {
  const [filter, setFilter] = useState('pending')
  const [selected, setSelected] = useState<any>(null)
  const [tab, setTab] = useState<'pending' | 'history'>('pending')

  const { data, isLoading } = useQuery({
    queryKey: ['approvals', filter],
    queryFn: () => approvalsApi.list({ status: filter || undefined }),
    refetchInterval: 5000,
  })

  const { data: histData } = useQuery({
    queryKey: ['approvals-history'],
    queryFn: () => approvalsApi.history(),
    enabled: tab === 'history',
  })

  const approvals: any[] = data?.approvals ?? []
  const history: any[] = histData?.approvals ?? []

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Human Approvals</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Review and action pending workflow approval requests</p>
        </div>
        <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)' }}>
          {(['pending', 'history'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ padding: '7px 14px', background: 'transparent', color: tab === t ? 'var(--accent)' : 'var(--text3)', fontSize: 12, fontWeight: 500, cursor: 'pointer', border: 'none', borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent', textTransform: 'capitalize' }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '16px 32px' }}>
        {tab === 'pending' && (
          <>
            <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
              {['pending', 'approved', 'rejected', ''].map(s => (
                <button key={s} onClick={() => setFilter(s)}
                  style={{ padding: '4px 12px', borderRadius: 6, border: `1px solid ${filter === s ? 'var(--accent)' : 'var(--border)'}`, background: filter === s ? 'rgba(124,58,237,0.1)' : 'transparent', color: filter === s ? 'var(--accent)' : 'var(--text3)', fontSize: 11, cursor: 'pointer', textTransform: s ? 'capitalize' : 'none' }}>
                  {s || 'All'}
                </button>
              ))}
            </div>
            {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
            {!isLoading && approvals.length === 0 && (
              <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>
                No {filter || ''} approvals
              </div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {approvals.map((a: any) => (
                <div key={a.id}
                  style={{ padding: '14px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
                  <Label s={a.status} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.execution_id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                      Node: {a.node_id} · {a.created_at ? new Date(a.created_at).toLocaleString() : ''}
                    </div>
                  </div>
                  {a.expires_at && (
                    <div style={{ fontSize: 11, color: 'var(--yellow)', flexShrink: 0 }}>
                      Expires {new Date(a.expires_at).toLocaleString()}
                    </div>
                  )}
                  {a.status === 'pending' && (
                    <button onClick={() => setSelected(a)}
                      style={{ padding: '6px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
                      Review
                    </button>
                  )}
                </div>
              ))}
            </div>
          </>
        )}

        {tab === 'history' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(history.length === 0) && <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--text3)', fontSize: 13 }}>No history</div>}
            {history.map((a: any) => (
              <div key={a.id}
                style={{ padding: '12px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
                <Label s={a.status} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.execution_id}</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>
                    {a.decided_at ? `Decided: ${new Date(a.decided_at).toLocaleString()}` : ''}
                    {a.reason ? ` · ${a.reason}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text3)', flexShrink: 0 }}>{a.decided_by || ''}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {selected && <DecideModal approval={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
