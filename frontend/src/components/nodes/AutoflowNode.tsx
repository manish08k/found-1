import React, { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { getNodeDef, PROVIDER_COLORS } from '../../types/nodes'

export default memo(function AutoflowNode({ data, selected }: NodeProps) {
  const def = getNodeDef(data.type)
  const color = PROVIDER_COLORS[def?.provider ?? 'core'] ?? '#6366f1'
  const label = data.label || def?.label || data.type
  const isTrigger = data.type?.startsWith('trigger.')

  const statusIcon = data.status === 'running'
    ? <Spin />
    : data.status === 'success'
    ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
    : data.status === 'error'
    ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="3"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    : null

  const borderColor = selected ? color
    : data.status === 'error' ? 'var(--red)'
    : data.status === 'success' ? 'var(--green)'
    : 'var(--border)'

  return (
    <div style={{
      background: 'var(--bg2)',
      border: `1.5px solid ${borderColor}`,
      borderRadius: 10,
      minWidth: 180,
      maxWidth: 220,
      boxShadow: selected ? `0 0 0 3px ${color}33, 0 4px 16px rgba(0,0,0,0.4)` : '0 2px 10px rgba(0,0,0,0.3)',
      overflow: 'hidden',
      transition: 'border-color 0.15s, box-shadow 0.15s',
      fontFamily: 'var(--font)',
    }}>
      {/* Color stripe top */}
      <div style={{ height: 3, background: color }} />

      {/* Body */}
      <div title={data.status === 'error' && data.error ? data.error : undefined}
        style={{ padding: '9px 12px 10px', display: 'flex', alignItems: 'center', gap: 9 }}>
        <div style={{ width: 28, height: 28, borderRadius: 7, background: `${color}20`, border: `1px solid ${color}33`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <div style={{ width: 9, height: 9, borderRadius: 3, background: color }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 1 }}>{def?.category ?? 'Node'}</div>
        </div>
        {statusIcon && <div style={{ flexShrink: 0 }}>{statusIcon}</div>}
      </div>

      {/* Error snippet — a red border alone doesn't tell you WHAT broke without opening the executions panel */}
      {data.status === 'error' && data.error && (
        <div style={{ margin: '0 10px 8px', padding: '5px 8px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 4, fontSize: 9.5, color: 'var(--red)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {data.error}
        </div>
      )}

      {/* Credential badge */}
      {data.credential_id && (
        <div style={{ margin: '0 10px 8px', padding: '3px 8px', background: 'var(--bg3)', borderRadius: 4, fontSize: 9, color: 'var(--text3)', display: 'flex', alignItems: 'center', gap: 4 }}>
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
          Account connected
        </div>
      )}

      {!isTrigger && (
        <Handle type="target" position={Position.Left}
          style={{ background: color, border: '2px solid var(--bg1)', width: 11, height: 11, left: -6 }} />
      )}
      <Handle type="source" position={Position.Right}
        style={{ background: color, border: '2px solid var(--bg1)', width: 11, height: 11, right: -6 }} />
    </div>
  )
})

function Spin() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      <path d="M21 12a9 9 0 11-18 0" opacity={0.3}/><path d="M12 3a9 9 0 019 9"/>
    </svg>
  )
}
