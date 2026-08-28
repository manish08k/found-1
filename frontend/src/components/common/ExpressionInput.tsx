import React, { useMemo, useRef, useState } from 'react'

export interface ExpressionSuggestion {
  /** What gets inserted between {{ and }}, e.g. "trigger.body.id" */
  insert: string
  /** Shown in the dropdown, e.g. "trigger.body.id — from the trigger payload" */
  label: string
  hint?: string
}

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  multiline?: boolean
  suggestions: ExpressionSuggestion[]
}

/**
 * A plain text/textarea input, except typing `{{` opens an autocomplete
 * popover of things you can reference (trigger fields, upstream node
 * outputs) instead of the person having to remember/guess node IDs.
 * Falls back to a completely normal input if there's nothing to
 * suggest — this never blocks typing a literal `{{ }}` by hand.
 */
export default function ExpressionInput({ value, onChange, placeholder, multiline, suggestions }: Props) {
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlighted, setHighlighted] = useState(0)

  const filtered = useMemo(() => {
    const q = query.toLowerCase()
    return suggestions.filter(s => !q || s.insert.toLowerCase().includes(q) || s.label.toLowerCase().includes(q)).slice(0, 8)
  }, [suggestions, query])

  const checkForTrigger = (text: string, cursor: number) => {
    // Look backwards from the cursor for an unterminated "{{" on this line.
    const uptoCursor = text.slice(0, cursor)
    const lastOpen = uptoCursor.lastIndexOf('{{')
    const lastClose = uptoCursor.lastIndexOf('}}')
    if (lastOpen > -1 && lastOpen > lastClose) {
      const partial = uptoCursor.slice(lastOpen + 2).trim()
      setQuery(partial)
      setOpen(true)
      setHighlighted(0)
    } else {
      setOpen(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    onChange(e.target.value)
    checkForTrigger(e.target.value, e.target.selectionStart ?? e.target.value.length)
  }

  const insertSuggestion = (s: ExpressionSuggestion) => {
    const el = ref.current
    if (!el) return
    const cursor = el.selectionStart ?? value.length
    const uptoCursor = value.slice(0, cursor)
    const lastOpen = uptoCursor.lastIndexOf('{{')
    const before = value.slice(0, lastOpen + 2)
    const after = value.slice(cursor)
    const newValue = `${before} ${s.insert} }}${after}`
    onChange(newValue)
    setOpen(false)
    requestAnimationFrame(() => {
      const newCursor = before.length + s.insert.length + 4
      el.setSelectionRange(newCursor, newCursor)
      el.focus()
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open || filtered.length === 0) return
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlighted(h => (h + 1) % filtered.length) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlighted(h => (h - 1 + filtered.length) % filtered.length) }
    else if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); insertSuggestion(filtered[highlighted]) }
    else if (e.key === 'Escape') { setOpen(false) }
  }

  const commonProps = {
    ref: ref as any,
    value,
    placeholder,
    onChange: handleChange,
    onKeyDown: handleKeyDown,
    onBlur: () => setTimeout(() => setOpen(false), 150), // delay so a click on a suggestion still registers
  }

  return (
    <div style={{ position: 'relative' }}>
      {multiline ? <textarea {...commonProps} /> : <input {...commonProps} />}
      {open && filtered.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 4, zIndex: 50,
          background: 'var(--bg2)', border: '1px solid var(--border2)', borderRadius: 8,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)', maxHeight: 220, overflow: 'auto', padding: 4,
        }}>
          {filtered.map((s, i) => (
            <div key={s.insert} onMouseDown={e => { e.preventDefault(); insertSuggestion(s) }}
              onMouseEnter={() => setHighlighted(i)}
              style={{
                padding: '7px 10px', borderRadius: 6, cursor: 'pointer',
                background: i === highlighted ? 'var(--accent)' : 'transparent',
              }}>
              <div style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--mono)', color: i === highlighted ? '#fff' : 'var(--text)' }}>
                {'{{ '}{s.insert}{' }}'}
              </div>
              {s.hint && (
                <div style={{ fontSize: 10, color: i === highlighted ? 'rgba(255,255,255,0.75)' : 'var(--text3)', marginTop: 1 }}>
                  {s.hint}
                </div>
              )}
            </div>
          ))}
          <div style={{ padding: '5px 10px', fontSize: 9.5, color: 'var(--text3)', borderTop: '1px solid var(--border)', marginTop: 2 }}>
            ↑↓ to navigate · Enter/Tab to insert · Esc to dismiss
          </div>
        </div>
      )}
    </div>
  )
}
