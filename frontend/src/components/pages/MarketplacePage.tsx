import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { marketplaceApi, workflowsApi } from '../../api/client'
import { useStore } from '../../store'
import toast from 'react-hot-toast'

interface MarketplaceItem {
  name: string
  slug: string
  description: string
  category: string
  tags: string[]
  item_type: string
  downloads: number
  avg_rating: number
  is_verified?: boolean
  content?: any
}

const CATEGORY_COLORS: Record<string, string> = {
  'Notifications': '#7c3aed', 'Dev Tools': '#24292e', 'Reporting': '#0ea5e9',
  'CRM': '#ff7a59', 'E-commerce': '#22c55e', 'Productivity': '#f59e0b', 'Monitoring': '#ef4444',
}

export default function MarketplacePage() {
  const qc = useQueryClient()
  const { setActiveWorkflow, setPage } = useStore()
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [category, setCategory] = useState<string>('All')
  const [selected, setSelected] = useState<MarketplaceItem | null>(null)

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 250)
    return () => clearTimeout(t)
  }, [search])

  const { data, isLoading, isError } = useQuery({
    queryKey: ['marketplace', debouncedSearch, category],
    queryFn: () => marketplaceApi.browse({ search: debouncedSearch || undefined, category: category === 'All' ? undefined : category }),
  })
  const items: MarketplaceItem[] = data ?? []
  const categories = ['All', ...Array.from(new Set(items.map(i => i.category).filter(Boolean)))]

  const { data: detail } = useQuery({
    queryKey: ['marketplace-item', selected?.slug],
    queryFn: () => marketplaceApi.get(selected!.slug),
    enabled: !!selected,
  })

  const installMut = useMutation({
    mutationFn: marketplaceApi.install,
    onSuccess: async (res: any) => {
      toast.success(`Installed "${res.name}"`)
      await qc.invalidateQueries({ queryKey: ['workflows'] })
      setSelected(null)
      if (res.workflow_id) {
        // Jump straight into editing the newly installed workflow —
        // installing something you then can't find defeats the point.
        // Fetch the real record rather than assembling a partial one
        // client-side, so status/settings/timestamps are all correct.
        try {
          const wf = await workflowsApi.get(res.workflow_id)
          setPage('workflows')
          setActiveWorkflow(wf)
        } catch {
          setPage('workflows')
        }
      }
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to install'),
  })

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 32, display: 'flex', gap: 24 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Marketplace</h1>
          <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>
            Starter templates you can install straight into your workspace, then customize.
          </p>
        </div>

        {/* Search + category filter */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '1 1 240px', minWidth: 220 }}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" strokeWidth="2"
              style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search templates…" style={{ paddingLeft: 34, width: '100%' }} />
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {categories.map(c => (
              <button key={c} onClick={() => setCategory(c)}
                style={{ padding: '7px 13px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                  background: category === c ? 'var(--accent)' : 'var(--bg2)',
                  color: category === c ? '#fff' : 'var(--text3)',
                  border: `1px solid ${category === c ? 'var(--accent)' : 'var(--border)'}`, cursor: 'pointer' }}>
                {c}
              </button>
            ))}
          </div>
        </div>

        {/* Loading */}
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading templates…</div>}

        {/* Error state */}
        {isError && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 260, color: 'var(--text3)', gap: 10 }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="1.5" opacity={0.6}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <p style={{ fontSize: 14 }}>Couldn't load the marketplace right now.</p>
            <button onClick={() => qc.invalidateQueries({ queryKey: ['marketplace'] })}
              style={{ padding: '7px 16px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 7, border: '1px solid var(--border)', cursor: 'pointer', fontSize: 12 }}>
              Try again
            </button>
          </div>
        )}

        {/* Empty state (no results for search/filter) */}
        {!isLoading && !isError && items.length === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 260, color: 'var(--text3)', gap: 10 }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity={0.3}><path d="M3 3h18l-2 9H5L3 3z"/><circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/></svg>
            <p style={{ fontSize: 14 }}>
              {debouncedSearch || category !== 'All' ? 'No templates match your search.' : 'No templates published yet.'}
            </p>
            {(debouncedSearch || category !== 'All') && (
              <button onClick={() => { setSearch(''); setCategory('All') }}
                style={{ padding: '7px 16px', background: 'var(--bg3)', color: 'var(--text2)', borderRadius: 7, border: '1px solid var(--border)', cursor: 'pointer', fontSize: 12 }}>
                Clear filters
              </button>
            )}
          </div>
        )}

        {/* Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {items.map(item => (
            <div key={item.slug} onClick={() => setSelected(item)}
              style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, cursor: 'pointer', transition: 'border-color 0.15s', display: 'flex', flexDirection: 'column', gap: 10 }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--border2)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <h3 style={{ fontWeight: 600, fontSize: 13.5, color: 'var(--text)', lineHeight: 1.3 }}>{item.name}</h3>
                {item.is_verified && (
                  <span title="Official AutoFlow template" style={{ flexShrink: 0, color: 'var(--accent)' }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.3 7.2 16.9l.9-5.4L4.2 7.7l5.4-.8L12 2z"/></svg>
                  </span>
                )}
              </div>
              <p style={{ fontSize: 12, color: 'var(--text3)', lineHeight: 1.5, flex: 1, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                {item.description}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--text3)' }}>
                <span style={{ padding: '2px 8px', borderRadius: 10, background: `${CATEGORY_COLORS[item.category] ?? '#6366f1'}22`, color: CATEGORY_COLORS[item.category] ?? '#6366f1', fontWeight: 600 }}>
                  {item.category}
                </span>
                <div style={{ display: 'flex', gap: 10 }}>
                  <span>↓ {item.downloads}</span>
                  {item.avg_rating > 0 && <span>★ {item.avg_rating.toFixed(1)}</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div style={{ width: 340, flexShrink: 0, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 20, height: 'fit-content', position: 'sticky', top: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 4 }}>
            <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)' }}>{selected.name}</h2>
            <button onClick={() => setSelected(null)} aria-label="Close template details" style={{ background: 'transparent', color: 'var(--text3)', border: 'none', cursor: 'pointer', padding: 4 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
          <p style={{ fontSize: 12.5, color: 'var(--text3)', lineHeight: 1.6, marginTop: 10 }}>{selected.description}</p>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14 }}>
            {selected.tags?.map(t => (
              <span key={t} style={{ fontSize: 10, padding: '3px 8px', background: 'var(--bg3)', color: 'var(--text3)', borderRadius: 10 }}>#{t}</span>
            ))}
          </div>

          <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text3)' }}>
            {detail ? `${detail.content?.nodes?.length ?? 0} nodes` : 'Loading preview…'} · {selected.downloads} installs
            {selected.avg_rating > 0 && ` · ★ ${selected.avg_rating.toFixed(1)}`}
          </div>

          <button onClick={() => installMut.mutate(selected.slug)} disabled={installMut.isPending}
            style={{ width: '100%', marginTop: 16, padding: '10px 0', background: 'var(--accent)', color: '#fff', borderRadius: 8, fontWeight: 600, fontSize: 13, border: 'none', cursor: 'pointer', opacity: installMut.isPending ? 0.7 : 1 }}>
            {installMut.isPending ? 'Installing…' : 'Install to my workspace'}
          </button>
          <p style={{ fontSize: 10.5, color: 'var(--text3)', marginTop: 8, textAlign: 'center' }}>
            Creates an editable copy — you'll need to connect your own accounts before it can run.
          </p>
        </div>
      )}
    </div>
  )
}
