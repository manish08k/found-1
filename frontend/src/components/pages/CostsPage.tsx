import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { costsApi } from '../../api/client'
import toast from 'react-hot-toast'

function MetricCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px' }}>
      <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: color || 'var(--text)' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

export default function CostsPage() {
  const [days, setDays] = useState(30)

  const { data: summary, isLoading } = useQuery({
    queryKey: ['cost-summary', days],
    queryFn: () => costsApi.getSummary(days),
    refetchInterval: 30000,
  })

  const totalCost: number = summary?.total_cost_usd ?? 0
  const totalTokens: number = summary?.total_tokens ?? 0
  const byModel: Record<string, any> = summary?.by_model ?? {}
  const budget: number = summary?.monthly_budget_usd ?? 0
  const budgetPct: number = budget > 0 ? Math.min(100, (totalCost / budget) * 100) : 0

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>AI Cost & Usage</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Track token usage and estimated cost across all AI nodes and executions</p>
          </div>
          <select value={days} onChange={e => setDays(parseInt(e.target.value))}
            style={{ padding: '7px 12px', background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text2)', fontSize: 12 }}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13, padding: '16px 0' }}>Loading…</div>}

        {/* Summary metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          <MetricCard label="Total Cost" value={`$${totalCost.toFixed(4)}`} sub={`Last ${days} days`} color="var(--accent)" />
          <MetricCard label="Total Tokens" value={totalTokens.toLocaleString()} sub="Input + output" />
          <MetricCard label="Avg Cost/Exec" value={`$${summary?.avg_cost_per_execution?.toFixed(6) ?? '0.000000'}`} />
          <MetricCard label="Executions" value={summary?.execution_count ?? 0} />
        </div>

        {/* Budget bar */}
        {budget > 0 && (
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>Monthly Budget</span>
              <span style={{ fontSize: 13, color: budgetPct > 80 ? 'var(--red)' : 'var(--text2)' }}>
                ${totalCost.toFixed(4)} / ${budget} ({budgetPct.toFixed(1)}%)
              </span>
            </div>
            <div style={{ height: 8, background: 'var(--bg3)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${budgetPct}%`, background: budgetPct > 80 ? 'var(--red)' : 'var(--accent)', borderRadius: 4, transition: 'width 0.3s' }} />
            </div>
            {budgetPct > 80 && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--red)' }}>⚠ Budget threshold reached</div>
            )}
          </div>
        )}

        {/* By model breakdown */}
        {Object.keys(byModel).length > 0 && (
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, marginBottom: 20, overflow: 'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 600, fontSize: 13, color: 'var(--text)' }}>
              Cost by Model
            </div>
            <div style={{ overflow: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Model', 'Input Tokens', 'Output Tokens', 'Total Tokens', 'Cost (USD)', 'Calls'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, color: 'var(--text3)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(byModel).sort(([, a]: any, [, b]: any) => b.cost_usd - a.cost_usd).map(([model, data]: [string, any]) => (
                    <tr key={model} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text)', fontFamily: 'var(--mono)' }}>{model}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text2)' }}>{(data.input_tokens || 0).toLocaleString()}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text2)' }}>{(data.output_tokens || 0).toLocaleString()}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text2)' }}>{(data.total_tokens || 0).toLocaleString()}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>${(data.cost_usd || 0).toFixed(6)}</td>
                      <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text2)' }}>{data.call_count || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Model Routing */}
        <ModelRoutingSection />
      </div>
    </div>
  )
}

function ModelRoutingSection() {
  const [preferred, setPreferred] = useState('gpt-4o')
  const [budget, setBudget] = useState('')
  const [prefer, setPrefer] = useState('capability')
  const [result, setResult] = useState<any>(null)

  const routeMut = useMutation({
    mutationFn: () => costsApi.routeModel({
      preferred_model: preferred,
      budget_usd: budget ? parseFloat(budget) : undefined,
      requirements: { prefer },
    }),
    onSuccess: (d) => setResult(d),
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  return (
    <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 20px' }}>
      <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)', marginBottom: 14 }}>Model Routing Advisor</div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap', marginBottom: 14 }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Preferred Model</label>
          <select value={preferred} onChange={e => setPreferred(e.target.value)}
            style={{ padding: '7px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 12 }}>
            {['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo', 'claude-opus-4-6', 'claude-sonnet-4-6', 'claude-3-5-haiku-20241022', 'gemini-1.5-pro', 'gemini-1.5-flash', 'mistral-large-latest', 'mistral-small-latest'].map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Budget/call (USD)</label>
          <input type="number" value={budget} onChange={e => setBudget(e.target.value)} placeholder="e.g. 0.01"
            style={{ width: 110, padding: '7px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 12 }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Optimize for</label>
          <select value={prefer} onChange={e => setPrefer(e.target.value)}
            style={{ padding: '7px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 7, color: 'var(--text)', fontSize: 12 }}>
            <option value="capability">Capability</option>
            <option value="cost">Cost</option>
            <option value="latency">Latency</option>
          </select>
        </div>
        <button onClick={() => routeMut.mutate()} disabled={routeMut.isPending}
          style={{ padding: '7px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 7, cursor: 'pointer', fontSize: 12, fontWeight: 600, opacity: routeMut.isPending ? 0.6 : 1 }}>
          {routeMut.isPending ? 'Routing…' : 'Get Recommendation'}
        </button>
      </div>
      {result && (
        <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
            Recommended: <span style={{ color: 'var(--accent)', fontFamily: 'var(--mono)' }}>{result.model}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 4 }}>{result.reason}</div>
          <div style={{ fontSize: 11, color: 'var(--text3)' }}>
            Est. cost per 1K tokens: ${(result.estimated_cost_1k || 0).toFixed(6)}
            {result.fallback_model && <> · Fallback: <span style={{ fontFamily: 'var(--mono)' }}>{result.fallback_model}</span></>}
          </div>
        </div>
      )}
    </div>
  )
}
