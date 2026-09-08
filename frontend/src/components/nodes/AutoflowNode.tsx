import React, { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { getNodeDef, PROVIDER_COLORS } from '../../types/nodes'

export default memo(function AutoflowNode({ data, selected }: NodeProps) {
  const def = getNodeDef(data.type)
  const color = PROVIDER_COLORS[def?.provider ?? 'core'] ?? '#6366f1'
  const label = data.label || def?.label || data.type
  const isTrigger = data.type?.startsWith('trigger.')
  const isRunning = data.status === 'running'
  const isSuccess = data.status === 'success'
  const isError = data.status === 'error' || data.status === 'failed'

  const borderColor = isError ? 'var(--red)'
    : isSuccess ? 'var(--green)'
    : selected ? color
    : 'var(--border)'

  const boxShadow = isError
    ? '0 0 0 1px rgba(239,68,68,0.3), 0 2px 8px rgba(0,0,0,0.35)'
    : isSuccess
    ? '0 0 0 1px rgba(34,197,94,0.2), 0 2px 8px rgba(0,0,0,0.35)'
    : selected
    ? `0 0 0 2px ${color}40, 0 4px 16px rgba(0,0,0,0.4)`
    : '0 1px 4px rgba(0,0,0,0.25), 0 2px 8px rgba(0,0,0,0.2)'

  return (
    <div style={{
      background: 'var(--bg2)',
      border: `1.5px solid ${borderColor}`,
      borderRadius: 10,
      minWidth: 192,
      maxWidth: 220,
      boxShadow,
      overflow: 'hidden',
      transition: 'border-color 0.15s, box-shadow 0.15s',
      fontFamily: 'var(--font)',
      position: 'relative',
    }}>
      {/* Provider color accent line */}
      <div style={{ height: 2.5, background: color, opacity: 0.9 }} />

      {/* Body */}
      <div style={{ padding: '10px 12px 10px', display: 'flex', alignItems: 'center', gap: 9 }}>
        {/* Icon area */}
        <div style={{
          width: 30, height: 30, borderRadius: 8,
          background: `${color}18`,
          border: `1px solid ${color}30`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          position: 'relative',
        }}>
          {isRunning ? (
            <NodeSpinner color={color} />
          ) : (
            <div style={{ width: 10, height: 10, borderRadius: 3, background: color, opacity: 0.9 }} />
          )}
        </div>

        {/* Text */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.3 }}>
            {label}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 1.5, lineHeight: 1 }}>
            {def?.category ?? 'Node'}
          </div>
        </div>

        {/* Status icon */}
        {isSuccess && (
          <div style={{ flexShrink: 0, width: 18, height: 18, borderRadius: '50%', background: 'rgba(34,197,94,0.15)', border: '1px solid rgba(34,197,94,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
        )}
        {isError && (
          <div style={{ flexShrink: 0, width: 18, height: 18, borderRadius: '50%', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </div>
        )}
      </div>

      {/* Error snippet */}
      {isError && data.error && (
        <div style={{ margin: '0 10px 9px', padding: '4px 8px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 5, fontSize: 10, color: 'var(--red)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.4 }}>
          {data.error}
        </div>
      )}

      {/* Credential badge */}
      {data.credential_id && !isError && (
        <div style={{ margin: '0 10px 9px', padding: '3px 7px', background: 'var(--bg3)', borderRadius: 4, fontSize: 9.5, color: 'var(--text3)', display: 'flex', alignItems: 'center', gap: 4, width: 'fit-content' }}>
          <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
          Connected
        </div>
      )}

      {/* Input handle */}
      {!isTrigger && (
        <Handle type="target" position={Position.Left}
          style={{ background: color, border: '2px solid var(--bg1)', width: 10, height: 10, left: -5 }} />
      )}
      {/* Output handle */}
      <Handle type="source" position={Position.Right}
        style={{ background: color, border: '2px solid var(--bg1)', width: 10, height: 10, right: -5 }} />
    </div>
  )
})

function NodeSpinner({ color }: { color: string }) {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5"
      style={{ animation: 'spin 0.8s linear infinite' }}>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      <path d="M12 3a9 9 0 019 9" strokeLinecap="round"/>
      <path d="M21 12a9 9 0 01-18 0 9 9 0 0118 0" opacity={0.2}/>
    </svg>
  )
}
