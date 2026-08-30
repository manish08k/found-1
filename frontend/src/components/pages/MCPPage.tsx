import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { mcpApi } from '../../api/client'
import toast from 'react-hot-toast'

function AddServerModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [authType, setAuthType] = useState('none')
  const [apiKey, setApiKey] = useState('')

  const addMut = useMutation({
    mutationFn: (d: any) => mcpApi.registerServer(d),
    onSuccess: () => {
      toast.success('MCP server registered')
      qc.invalidateQueries({ queryKey: ['mcp-servers'] })
      onClose()
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to register'),
  })

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 12, width: 480, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Add MCP Server</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Name *</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="My MCP Server"
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Server URL *</label>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://mcp.example.com/sse"
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Authentication</label>
            <select value={authType} onChange={e => setAuthType(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              <option value="none">None</option>
              <option value="api_key">API Key</option>
            </select>
          </div>
          {authType === 'api_key' && (
            <div>
              <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>API Key</label>
              <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="sk-…"
                style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: '8px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
            Cancel
          </button>
          <button onClick={() => addMut.mutate({ name, url, auth_type: authType, api_key: apiKey || undefined })}
            disabled={!name || !url || addMut.isPending}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, opacity: (!name || !url || addMut.isPending) ? 0.5 : 1 }}>
            {addMut.isPending ? 'Registering…' : 'Register'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ServerCard({ server }: { server: any }) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [allowedTools, setAllowedTools] = useState<string[]>(server.allowed_tools || [])

  const deleteMut = useMutation({
    mutationFn: () => mcpApi.deleteServer(server.id),
    onSuccess: () => { toast.success('Server removed'); qc.invalidateQueries({ queryKey: ['mcp-servers'] }) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const connectMut = useMutation({
    mutationFn: () => mcpApi.connectServer(server.id),
    onSuccess: (data) => {
      toast.success(`Discovered ${data.tools?.length ?? 0} tools`)
      qc.invalidateQueries({ queryKey: ['mcp-servers'] })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Connection failed'),
  })

  const permMut = useMutation({
    mutationFn: (tools: string[]) => mcpApi.updatePermissions(server.id, { allowed_tools: tools }),
    onSuccess: () => { toast.success('Permissions updated'); qc.invalidateQueries({ queryKey: ['mcp-servers'] }) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const tools: any[] = server.discovered_tools || []

  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }} onClick={() => setExpanded(!expanded)}>
        <div style={{ width: 36, height: 36, background: 'rgba(124,58,237,0.12)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{server.name}</div>
          <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{server.url}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text3)', background: 'var(--bg3)', padding: '2px 8px', borderRadius: 6 }}>
            {tools.length} tool{tools.length !== 1 ? 's' : ''}
          </span>
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 6, background: server.is_active ? 'rgba(34,197,94,0.1)' : 'var(--bg3)', color: server.is_active ? 'var(--green)' : 'var(--text3)', fontWeight: 600 }}>
            {server.is_active ? 'Active' : 'Inactive'}
          </span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', color: 'var(--text3)' }}><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', padding: '16px 20px' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <button onClick={() => connectMut.mutate()} disabled={connectMut.isPending}
              style={{ padding: '7px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 12, opacity: connectMut.isPending ? 0.6 : 1 }}>
              {connectMut.isPending ? 'Connecting…' : '⟳ Connect & Discover'}
            </button>
            <button onClick={() => deleteMut.mutate()} disabled={deleteMut.isPending}
              style={{ padding: '7px 14px', background: 'rgba(239,68,68,0.08)', border: '1px solid var(--red)', color: 'var(--red)', borderRadius: 8, cursor: 'pointer', fontSize: 12, opacity: deleteMut.isPending ? 0.6 : 1 }}>
              Remove
            </button>
          </div>

          {tools.length > 0 && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                Discovered Tools — {allowedTools.length === 0 ? 'All allowed' : `${allowedTools.length} selected`}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {tools.map((tool: any) => {
                  const tname = typeof tool === 'string' ? tool : tool.name
                  const tdesc = typeof tool === 'object' ? tool.description : ''
                  const isAllowed = allowedTools.length === 0 || allowedTools.includes(tname)
                  return (
                    <div key={tname} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 10px', background: 'var(--bg)', borderRadius: 8 }}>
                      <input type="checkbox" checked={allowedTools.length === 0 || allowedTools.includes(tname)}
                        onChange={e => {
                          if (e.target.checked) {
                            const next = allowedTools.filter(t => t !== tname).concat(tname)
                            setAllowedTools(next)
                          } else {
                            // If currently "all allowed" (empty), switching off means selecting all others
                            const base = allowedTools.length === 0 ? tools.map((t: any) => typeof t === 'string' ? t : t.name) : allowedTools
                            setAllowedTools(base.filter((t: string) => t !== tname))
                          }
                        }} style={{ marginTop: 2 }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--mono)' }}>{tname}</div>
                        {tdesc && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{tdesc}</div>}
                      </div>
                    </div>
                  )
                })}
              </div>
              <button onClick={() => permMut.mutate(allowedTools)} disabled={permMut.isPending}
                style={{ marginTop: 12, padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, opacity: permMut.isPending ? 0.6 : 1 }}>
                {permMut.isPending ? 'Saving…' : 'Save Permissions'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function MCPPage() {
  const [showAdd, setShowAdd] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['mcp-servers'],
    queryFn: mcpApi.listServers,
  })

  const servers: any[] = data?.servers ?? []

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>MCP Servers</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Connect external Model Context Protocol servers to expose tools to agents</p>
          </div>
          <button onClick={() => setShowAdd(true)}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Add Server
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
        {!isLoading && servers.length === 0 && (
          <div style={{ textAlign: 'center', padding: '64px 0' }}>
            <div style={{ width: 48, height: 48, background: 'var(--bg2)', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4"/></svg>
            </div>
            <div style={{ color: 'var(--text2)', fontWeight: 600, marginBottom: 8 }}>No MCP servers</div>
            <div style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 20 }}>Add an external MCP server to expose its tools to your agents</div>
            <button onClick={() => setShowAdd(true)}
              style={{ padding: '8px 20px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
              Add Server
            </button>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {servers.map((s: any) => <ServerCard key={s.id} server={s} />)}
        </div>
      </div>

      {showAdd && <AddServerModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}
