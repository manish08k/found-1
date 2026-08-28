import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { triggersApi, schedulesApi, credentialsApi } from '../../api/client'
import toast from 'react-hot-toast'

interface Props { workflowId: string; onClose: () => void }

export default function TriggersPanel({ workflowId, onClose }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'triggers' | 'schedules'>('triggers')
  const [addingTrigger, setAddingTrigger] = useState(false)
  const [addingSchedule, setAddingSchedule] = useState(false)

  const { data: tData } = useQuery({ queryKey: ['triggers', workflowId], queryFn: () => triggersApi.list(workflowId) })
  const { data: sData } = useQuery({ queryKey: ['schedules', workflowId], queryFn: () => schedulesApi.list(workflowId) })
  const { data: credData } = useQuery({ queryKey: ['credentials'], queryFn: () => credentialsApi.list() })

  const triggers = tData?.triggers ?? []
  const schedules = sData?.schedules ?? []
  const credentials = credData?.credentials ?? []

  const delTrigger = useMutation({ mutationFn: triggersApi.delete, onSuccess: () => qc.invalidateQueries({ queryKey: ['triggers', workflowId] }) })
  const delSchedule = useMutation({ mutationFn: schedulesApi.delete, onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules', workflowId] }) })
  const toggleSched = useMutation({ mutationFn: schedulesApi.toggle, onSuccess: () => qc.invalidateQueries({ queryKey: ['schedules', workflowId] }) })

  return (
    <div style={{ width: 320, background: 'var(--bg1)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>Triggers & Schedules</span>
        <button onClick={onClose} aria-label="Close triggers panel" style={{ background: 'transparent', color: 'var(--text3)', border: 'none', cursor: 'pointer' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {(['triggers', 'schedules'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ flex: 1, padding: '9px 0', fontSize: 12, fontWeight: 500, background: 'transparent', color: tab === t ? 'var(--accent)' : 'var(--text3)', borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent', border: 'none', cursor: 'pointer', textTransform: 'capitalize' }}>{t}</button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
        {tab === 'triggers' && (
          <>
            {triggers.length === 0 && !addingTrigger && <Empty label="No triggers yet" />}
            {triggers.map((t: any) => (
              <div key={t.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{t.provider}</span>
                    <span style={{ fontSize: 11, color: 'var(--text3)', marginLeft: 6 }}>/ {t.event}</span>
                  </div>
                  <button onClick={() => delTrigger.mutate(t.id)} style={{ background: 'transparent', color: 'var(--red)', border: 'none', cursor: 'pointer' }}>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/></svg>
                  </button>
                </div>
                {t.webhook_url && <WebhookUrl url={t.webhook_url} />}
                <div style={{ fontSize: 10, color: t.is_active ? 'var(--green)' : 'var(--text3)', marginTop: 4 }}>● {t.is_active ? 'Active' : 'Inactive'} · {t.trigger_type}</div>
              </div>
            ))}
            {addingTrigger
              ? <AddTriggerForm workflowId={workflowId} credentials={credentials} onDone={() => { setAddingTrigger(false); qc.invalidateQueries({ queryKey: ['triggers', workflowId] }) }} onCancel={() => setAddingTrigger(false)} />
              : <AddBtn onClick={() => setAddingTrigger(true)} label="Add Trigger" />}
          </>
        )}
        {tab === 'schedules' && (
          <>
            {schedules.length === 0 && !addingSchedule && <Empty label="No schedules yet" />}
            {schedules.map((s: any) => (
              <div key={s.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--mono)' }}>
                      {s.cron_expression ?? `every ${s.interval_seconds}s`}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 2 }}>{s.timezone}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button onClick={() => toggleSched.mutate(s.id)} style={{ padding: '3px 8px', background: s.is_active ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)', color: s.is_active ? 'var(--red)' : 'var(--green)', borderRadius: 5, fontSize: 10, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                      {s.is_active ? 'Pause' : 'Resume'}
                    </button>
                    <button onClick={() => delSchedule.mutate(s.id)} style={{ background: 'transparent', color: 'var(--red)', border: 'none', cursor: 'pointer' }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/></svg>
                    </button>
                  </div>
                </div>
                {s.next_run_at && <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>Next: {new Date(s.next_run_at).toLocaleString()}</div>}
              </div>
            ))}
            {addingSchedule
              ? <AddScheduleForm workflowId={workflowId} onDone={() => { setAddingSchedule(false); qc.invalidateQueries({ queryKey: ['schedules', workflowId] }) }} onCancel={() => setAddingSchedule(false)} />
              : <AddBtn onClick={() => setAddingSchedule(true)} label="Add Schedule" />}
          </>
        )}
      </div>
    </div>
  )
}

function WebhookUrl({ url }: { url: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 3 }}>Webhook URL</div>
      <div style={{ display: 'flex', gap: 4 }}>
        <input readOnly value={url} style={{ fontSize: 10, fontFamily: 'var(--mono)', flex: 1, background: 'var(--bg)', padding: '4px 6px' }} />
        <button onClick={() => { navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
          style={{ padding: '4px 8px', background: 'var(--bg3)', color: copied ? 'var(--green)' : 'var(--text3)', borderRadius: 5, fontSize: 10, border: '1px solid var(--border)', cursor: 'pointer' }}>
          {copied ? '✓' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

function AddTriggerForm({ workflowId, credentials, onDone, onCancel }: any) {
  const [provider, setProvider] = useState('slack')
  const [event, setEvent] = useState('new_message')
  const [trigType, setTrigType] = useState('webhook')
  const [credId, setCredId] = useState('')
  const mut = useMutation({ mutationFn: triggersApi.create, onSuccess: onDone, onError: () => toast.error('Failed to create trigger') })
  const provCreds = credentials.filter((c: any) => c.provider === provider)
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>New Trigger</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <select value={trigType} onChange={e => setTrigType(e.target.value)}>
          <option value="webhook">Webhook</option>
          <option value="polling">Polling</option>
        </select>
        <input value={provider} onChange={e => setProvider(e.target.value)} placeholder="Provider (slack, github…)" />
        <input value={event} onChange={e => setEvent(e.target.value)} placeholder="Event (new_message, push…)" />
        {provCreds.length > 0 && (
          <select value={credId} onChange={e => setCredId(e.target.value)}>
            <option value="">— Credential (optional) —</option>
            {provCreds.map((c: any) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
        )}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <button onClick={() => mut.mutate({ workflow_id: workflowId, trigger_type: trigType, provider, event, credential_id: credId || undefined })}
          disabled={mut.isPending} style={{ flex: 1, padding: '7px 0', background: 'var(--accent)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
          {mut.isPending ? '…' : 'Create'}
        </button>
        <button onClick={onCancel} style={{ flex: 1, padding: '7px 0', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', cursor: 'pointer' }}>Cancel</button>
      </div>
    </div>
  )
}

function AddScheduleForm({ workflowId, onDone, onCancel }: any) {
  const [cron, setCron] = useState('0 9 * * 1-5')
  const [tz, setTz] = useState('UTC')
  const mut = useMutation({ mutationFn: schedulesApi.create, onSuccess: onDone, onError: () => toast.error('Invalid cron expression') })
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 8, padding: 12, marginBottom: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', marginBottom: 10 }}>New Schedule</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <input value={cron} onChange={e => setCron(e.target.value)} placeholder="Cron: 0 9 * * 1-5" style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
        <input value={tz} onChange={e => setTz(e.target.value)} placeholder="Timezone: UTC" />
        <div style={{ fontSize: 10, color: 'var(--text3)' }}>
          Common: <code style={{ color: 'var(--accent)' }}>0 9 * * 1-5</code> (weekdays 9am) · <code style={{ color: 'var(--accent)' }}>*/30 * * * *</code> (every 30min)
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        <button onClick={() => mut.mutate({ workflow_id: workflowId, cron_expression: cron, timezone: tz })}
          disabled={mut.isPending} style={{ flex: 1, padding: '7px 0', background: 'var(--accent)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
          {mut.isPending ? '…' : 'Create'}
        </button>
        <button onClick={onCancel} style={{ flex: 1, padding: '7px 0', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', cursor: 'pointer' }}>Cancel</button>
      </div>
    </div>
  )
}

function Empty({ label }: { label: string }) {
  return <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text3)', fontSize: 12 }}>{label}</div>
}

function AddBtn({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button onClick={onClick} style={{ width: '100%', padding: '9px 0', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 8, fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, border: '1px solid var(--border)', cursor: 'pointer' }}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      {label}
    </button>
  )
}
