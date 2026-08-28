import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { credentialsApi, providersApi } from '../../api/client'
import { BASE_URL } from '../../api/client'
import toast from 'react-hot-toast'
import type { Credential, Provider } from '../../types'

const DB_TYPE_LABELS: Record<string, string> = {
  postgres: 'PostgreSQL', mysql: 'MySQL', sqlite: 'SQLite',
  stripe: 'Stripe', sendgrid: 'SendGrid', twilio: 'Twilio', jira: 'Jira',
  trello: 'Trello', pagerduty: 'PagerDuty', asana: 'Asana', aws_s3: 'AWS S3',
}

export default function CredentialsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [dbFormOpen, setDbFormOpen] = useState(false)
  const [apiKeyFormOpen, setApiKeyFormOpen] = useState(false)
  const [apiKeyProvider, setApiKeyProvider] = useState<'stripe' | 'sendgrid' | 'twilio' | 'jira' | 'trello' | 'pagerduty' | 'asana' | 'aws_s3' | 'mcp'>('stripe')
  const [apiKeyLabel, setApiKeyLabel] = useState('')
  const [apiKeyFields, setApiKeyFields] = useState<Record<string, string>>({})
  const [dbForm, setDbForm] = useState({
    label: '', db_type: 'postgres' as 'postgres' | 'mysql' | 'sqlite',
    host: '', port: '', database: '', username: '', password: '', ssl: false,
  })

  const { data: cData, isLoading } = useQuery({ queryKey: ['credentials'], queryFn: () => credentialsApi.list() })
  const { data: pData } = useQuery({ queryKey: ['providers'], queryFn: () => providersApi.list() })

  const credentials: Credential[] = cData?.credentials ?? []
  const providers: Provider[] = pData?.providers ?? []

  const deleteMut = useMutation({
    mutationFn: (id: string) => credentialsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['credentials'] }); toast.success('Disconnected') },
    onError: () => toast.error('Failed to disconnect'),
  })

  const testMut = useMutation({
    mutationFn: credentialsApi.test,
    onSuccess: (data: any) => toast(data.valid ? 'Credential valid ✓' : 'Credential invalid ✗'),
  })

  const API_KEY_FIELD_DEFS: Record<string, { key: string; label: string; secret?: boolean }[]> = {
    stripe: [{ key: 'api_key', label: 'Secret Key (sk_test_... or sk_live_...)', secret: true }],
    sendgrid: [{ key: 'api_key', label: 'API Key (SG....)', secret: true }],
    twilio: [
      { key: 'account_sid', label: 'Account SID (AC...)' },
      { key: 'auth_token', label: 'Auth Token', secret: true },
    ],
    jira: [
      { key: 'domain', label: 'Domain (yourcompany.atlassian.net)' },
      { key: 'email', label: 'Account Email' },
      { key: 'api_token', label: 'API Token', secret: true },
    ],
    trello: [
      { key: 'api_key', label: 'API Key' },
      { key: 'token', label: 'Token', secret: true },
    ],
    pagerduty: [
      { key: 'routing_key', label: 'Events API Routing Key (from a PagerDuty service)', secret: true },
    ],
    asana: [
      { key: 'access_token', label: 'Personal Access Token', secret: true },
    ],
    aws_s3: [
      { key: 'access_key_id', label: 'Access Key ID' },
      { key: 'secret_access_key', label: 'Secret Access Key', secret: true },
      { key: 'region', label: 'Region (e.g. us-east-1)' },
    ],
    mcp: [
      { key: 'server_url', label: 'MCP Server URL' },
      { key: 'auth_header', label: 'Authorization Header (optional, e.g. "Bearer ...")' },
    ],
  }

  const apiKeyMut = useMutation({
    mutationFn: credentialsApi.createApiKey,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['credentials'] })
      toast.success('Credential connected')
      setApiKeyFormOpen(false)
      setApiKeyLabel('')
      setApiKeyFields({})
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to connect'),
  })

  const submitApiKeyForm = () => {
    const requiredFields = API_KEY_FIELD_DEFS[apiKeyProvider]
    const missing = requiredFields.filter(f => !apiKeyFields[f.key]?.trim())
    if (!apiKeyLabel.trim() || missing.length > 0) {
      toast.error('Label and all fields are required')
      return
    }
    apiKeyMut.mutate({ provider: apiKeyProvider, label: apiKeyLabel, fields: apiKeyFields })
  }

  const dbMut = useMutation({
    mutationFn: credentialsApi.createManual,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['credentials'] })
      toast.success('Database connected')
      setDbFormOpen(false)
      setDbForm({ label: '', db_type: 'postgres', host: '', port: '', database: '', username: '', password: '', ssl: false })
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to connect database'),
  })

  const submitDbForm = () => {
    if (!dbForm.label || !dbForm.database || (dbForm.db_type !== 'sqlite' && !dbForm.host)) {
      toast.error('Label, database name, and host are required')
      return
    }
    dbMut.mutate({
      label: dbForm.label,
      db_type: dbForm.db_type,
      host: dbForm.host || undefined,
      port: dbForm.port ? Number(dbForm.port) : undefined,
      database: dbForm.database,
      username: dbForm.username || undefined,
      password: dbForm.password || undefined,
      ssl: dbForm.ssl,
    })
  }

  const filtered = credentials.filter(c =>
    !search || c.label.toLowerCase().includes(search.toLowerCase()) || c.provider.toLowerCase().includes(search.toLowerCase())
  )
  const connectedProviders = new Set(credentials.map(c => c.provider))

  const handleConnect = (provider: string, displayName: string) => {
    const token = localStorage.getItem('token')
    window.location.href = `${BASE_URL}/oauth/connect/${provider}?label=${encodeURIComponent(displayName)}&token=${token}`
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 32 }}>
      <div style={{ maxWidth: 800 }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Credentials</h1>
          <p style={{ color: 'var(--text3)', marginTop: 4, fontSize: 13 }}>Connect your accounts to use in workflows</p>
        </div>

        {/* Providers grid */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>Connect Account</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 8 }}>
            {providers.map((p: Provider) => {
              const connected = connectedProviders.has(p.name)
              return (
                <button key={p.name} onClick={() => handleConnect(p.name, p.display_name)}
                  style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', background: connected ? 'rgba(34,197,94,0.08)' : 'var(--bg3)', border: `1px solid ${connected ? 'var(--green)' : 'var(--border)'}`, borderRadius: 8, color: 'var(--text)', fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s', textAlign: 'left' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? 'var(--green)' : 'var(--border2)', flexShrink: 0 }} />
                  <span>{p.display_name}</span>
                  {connected && <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="3" style={{ marginLeft: 'auto' }}><polyline points="20 6 9 17 4 12"/></svg>}
                </button>
              )
            })}
          </div>
        </div>

        {/* Database connections */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: dbFormOpen ? 14 : 0 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Database Connection</div>
              <p style={{ color: 'var(--text3)', marginTop: 4, fontSize: 12 }}>Connect Postgres / MySQL / SQLite for the Database Query &amp; Execute nodes</p>
            </div>
            <button onClick={() => setDbFormOpen(v => !v)} style={{ padding: '6px 14px', background: 'var(--accent)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
              {dbFormOpen ? 'Cancel' : '+ Add Database'}
            </button>
          </div>

          {dbFormOpen && (
            <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <input placeholder="Label (e.g. Prod Postgres)" value={dbForm.label} onChange={e => setDbForm({ ...dbForm, label: e.target.value })} style={{ gridColumn: '1 / -1' }} />
              <select value={dbForm.db_type} onChange={e => setDbForm({ ...dbForm, db_type: e.target.value as any })}>
                <option value="postgres">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="sqlite">SQLite</option>
              </select>
              <input placeholder="Database name / file path" value={dbForm.database} onChange={e => setDbForm({ ...dbForm, database: e.target.value })} />
              {dbForm.db_type !== 'sqlite' && (
                <>
                  <input placeholder="Host" value={dbForm.host} onChange={e => setDbForm({ ...dbForm, host: e.target.value })} />
                  <input placeholder={dbForm.db_type === 'postgres' ? 'Port (5432)' : 'Port (3306)'} value={dbForm.port} onChange={e => setDbForm({ ...dbForm, port: e.target.value })} />
                  <input placeholder="Username" value={dbForm.username} onChange={e => setDbForm({ ...dbForm, username: e.target.value })} />
                  <input placeholder="Password" type="password" value={dbForm.password} onChange={e => setDbForm({ ...dbForm, password: e.target.value })} />
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text2)' }}>
                    <input type="checkbox" checked={dbForm.ssl} onChange={e => setDbForm({ ...dbForm, ssl: e.target.checked })} /> Require SSL
                  </label>
                </>
              )}
              <button onClick={submitDbForm} disabled={dbMut.isPending} style={{ gridColumn: '1 / -1', padding: '8px 14px', background: 'var(--green)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                {dbMut.isPending ? 'Connecting…' : 'Connect Database'}
              </button>
              <p style={{ gridColumn: '1 / -1', fontSize: 11, color: 'var(--text3)', margin: 0 }}>
                Credentials are encrypted at rest (AES-256-GCM) and only decrypted server-side when a workflow node runs.
              </p>
            </div>
          )}
        </div>

        {/* API-key connections (Stripe / SendGrid / Twilio / Jira) */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: apiKeyFormOpen ? 14 : 0 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>API Key Connection</div>
              <p style={{ color: 'var(--text3)', marginTop: 4, fontSize: 12 }}>Connect Stripe, SendGrid, Twilio, or Jira with an API key</p>
            </div>
            <button onClick={() => setApiKeyFormOpen(v => !v)} style={{ padding: '6px 14px', background: 'var(--accent)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
              {apiKeyFormOpen ? 'Cancel' : '+ Add API Key'}
            </button>
          </div>

          {apiKeyFormOpen && (
            <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <input placeholder="Label (e.g. Prod Stripe)" value={apiKeyLabel} onChange={e => setApiKeyLabel(e.target.value)} style={{ gridColumn: '1 / -1' }} />
              <select value={apiKeyProvider} onChange={e => { setApiKeyProvider(e.target.value as any); setApiKeyFields({}) }}>
                <option value="stripe">Stripe</option>
                <option value="sendgrid">SendGrid (Email)</option>
                <option value="twilio">Twilio (SMS)</option>
                <option value="jira">Jira</option>
                <option value="trello">Trello</option>
                <option value="pagerduty">PagerDuty</option>
                <option value="asana">Asana</option>
                <option value="aws_s3">AWS S3</option>
                <option value="mcp">MCP Server</option>
              </select>
              <div />
              {API_KEY_FIELD_DEFS[apiKeyProvider].map(f => (
                <input key={f.key} placeholder={f.label} type={f.secret ? 'password' : 'text'}
                  value={apiKeyFields[f.key] ?? ''}
                  onChange={e => setApiKeyFields(p => ({ ...p, [f.key]: e.target.value }))}
                  style={{ gridColumn: API_KEY_FIELD_DEFS[apiKeyProvider].length === 1 ? '1 / -1' : undefined }} />
              ))}
              <button onClick={submitApiKeyForm} disabled={apiKeyMut.isPending} style={{ gridColumn: '1 / -1', padding: '8px 14px', background: 'var(--green)', color: '#fff', borderRadius: 6, fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                {apiKeyMut.isPending ? 'Connecting…' : 'Connect'}
              </button>
              <p style={{ gridColumn: '1 / -1', fontSize: 11, color: 'var(--text3)', margin: 0 }}>
                Stored encrypted the same way as everything else — never shown again after saving.
              </p>
            </div>
          )}
        </div>

        {/* Connected list */}
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Connected ({credentials.length})
            </div>
            {credentials.length > 0 && (
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search…" style={{ width: 180, fontSize: 12, padding: '5px 10px' }} />
            )}
          </div>

          {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: '16px 0' }}>Loading…</div>}
          {!isLoading && filtered.length === 0 && (
            <div style={{ textAlign: 'center', padding: '28px 0', color: 'var(--text3)', fontSize: 13 }}>
              {credentials.length === 0 ? 'No accounts connected. Click a provider above to connect.' : 'No results'}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {filtered.map((c: Credential) => (
              <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--bg3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase' }}>{c.provider.slice(0, 2)}</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{c.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 1 }}>
                    {DB_TYPE_LABELS[c.provider] || c.provider} · {c.external_account_name || '—'} ·{' '}
                    {c.is_valid
                      ? <span style={{ color: 'var(--green)' }}>Valid</span>
                      : <span style={{ color: 'var(--red)' }}>Invalid — reconnect</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => testMut.mutate(c.id)} style={{ padding: '5px 12px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 6, fontSize: 11, fontWeight: 500, border: '1px solid var(--border)', cursor: 'pointer' }}>
                    Test
                  </button>
                  <button onClick={() => { if (confirm(`Disconnect ${c.label}?`)) deleteMut.mutate(c.id) }}
                    style={{ padding: '5px 10px', background: 'rgba(239,68,68,0.1)', color: 'var(--red)', borderRadius: 6, border: '1px solid rgba(239,68,68,0.2)', cursor: 'pointer' }}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
