import React, { useState, useMemo, useEffect, useRef } from 'react'
import { NODE_CATALOG, CATEGORIES, PROVIDER_COLORS } from '../../types/nodes'

interface Props { onAdd: (type: string) => void; onClose: () => void }

export default function NodePicker({ onAdd, onClose }: Props) {
  const [search, setSearch] = useState('')
  const [cat, setCat] = useState('All')
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return NODE_CATALOG.filter(n => {
      const matchCat = cat === 'All' || n.category === cat
      const matchQ = !q
        || n.label.toLowerCase().includes(q)
        || n.type.toLowerCase().includes(q)
        || n.category.toLowerCase().includes(q)
        || n.description.toLowerCase().includes(q)
      return matchCat && matchQ
    })
  }, [search, cat])

  useEffect(() => { setHighlighted(0) }, [search, cat])

  const grouped = useMemo(() => {
    const g: Record<string, typeof NODE_CATALOG> = {}
    filtered.forEach(n => { (g[n.category] = g[n.category] ?? []).push(n) })
    return g
  }, [filtered])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (filtered.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlighted(h => Math.min(h + 1, filtered.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlighted(h => Math.max(h - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); onAdd(filtered[highlighted].type) }
    else if (e.key === 'Escape') { onClose() }
  }

  return (
    <div style={{ width: 276, background: 'var(--bg1)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}>
      <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>Add Node</span>
          <button onClick={onClose} aria-label="Close node picker" style={{ background: 'transparent', color: 'var(--text3)', border: 'none', cursor: 'pointer' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div style={{ position: 'relative' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" strokeWidth="2" style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input ref={inputRef} autoFocus value={search} onChange={e => setSearch(e.target.value)} onKeyDown={handleKeyDown} placeholder="Search nodes…" style={{ paddingLeft: 30 }} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, padding: '8px 10px', overflowX: 'auto', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {['All', ...CATEGORIES].map(c => (
          <button key={c} onClick={() => setCat(c)} style={{ whiteSpace: 'nowrap', padding: '3px 9px', borderRadius: 12, fontSize: 10, fontWeight: 600, background: cat === c ? 'var(--accent)' : 'var(--bg3)', color: cat === c ? '#fff' : 'var(--text3)', border: 'none', cursor: 'pointer', flexShrink: 0 }}>
            {c}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px 10px' }}>
        {Object.entries(grouped).map(([category, nodes]) => (
          <div key={category} style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6, padding: '0 4px' }}>{category}</div>
            {nodes.map(n => {
              const color = PROVIDER_COLORS[n.provider] ?? '#6366f1'
              const flatIndex = filtered.indexOf(n)
              const isHighlighted = flatIndex === highlighted
              return (
                <button key={n.type} onClick={() => onAdd(n.type)} onMouseEnter={() => setHighlighted(flatIndex)}
                  style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8, background: isHighlighted ? 'var(--bg3)' : 'transparent', color: 'var(--text)', textAlign: 'left', marginBottom: 2, transition: 'background 0.1s', border: 'none', cursor: 'pointer' }}>
                  <div style={{ width: 28, height: 28, borderRadius: 7, background: `${color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, border: `1px solid ${color}33` }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>{n.label}</div>
                    <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.description}</div>
                  </div>
                </button>
              )
            })}
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, textAlign: 'center', color: 'var(--text3)', padding: '24px 8px' }}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity={0.4}><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span style={{ fontSize: 12 }}>No nodes match "{search}"</span>
            <button onClick={() => { setSearch(''); setCat('All') }} style={{ fontSize: 11, color: 'var(--accent)', background: 'transparent', border: 'none', cursor: 'pointer', padding: 0 }}>Clear search</button>
          </div>
        )}
      </div>
      <div style={{ padding: '6px 12px', borderTop: '1px solid var(--border)', fontSize: 9.5, color: 'var(--text3)', flexShrink: 0 }}>
        ↑↓ to navigate · Enter to add
      </div>
    </div>
  )
}
