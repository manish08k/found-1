import React, { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { billingApi } from '../../api/client'
import toast from 'react-hot-toast'

interface PlanRow {
  plan: string
  price_inr_per_month: number | null
  max_executions_per_month: number | null
  max_active_workflows: number | null
  max_users: number | null
  execution_history_days: number | null
  integrations: string
  ai_workflow_builder: string
  ai_agents: string
  versioning: string
  analytics: string
  rbac_audit_logs: boolean
  sso_saml: boolean
  dedicated_workers: boolean
  on_premise: boolean
  support: string
}

const PLAN_LABELS: Record<string, string> = {
  free: 'Free', starter: 'Starter', pro: 'Pro', business: 'Business', enterprise: 'Enterprise',
}
const FEATURED_PLAN = 'pro' // matches the "Pro ⭐" highlight in the source table — the plan most solo/small-team users land on

function fmtNumber(n: number | null): string {
  if (n === null) return 'Custom'
  if (n >= 1000) return `${Math.round(n / 1000)}K`.replace('1000K', '1M')
  return String(n)
}

function fmtPrice(n: number | null): string {
  if (n === null) return '₹50K+'
  if (n === 0) return '₹0'
  return `₹${n.toLocaleString('en-IN')}`
}

function fmtBool(b: boolean): string {
  return b ? '✓' : '—'
}

function fmtTier(value: string): string {
  const map: Record<string, string> = {
    basic: 'Basic', standard: 'All standard', premium: 'Premium', custom: 'Custom',
    limited: 'Limited', full: '✓', none: '—',
    advanced: 'Advanced', community: 'Community', email: 'Email', priority: 'Priority', dedicated: 'Dedicated',
  }
  return map[value] ?? value
}

const ROWS: { label: string; render: (p: PlanRow) => string }[] = [
  { label: 'Price/month', render: p => fmtPrice(p.price_inr_per_month) },
  { label: 'Workflow executions', render: p => p.max_executions_per_month === null ? 'Custom' : fmtNumber(p.max_executions_per_month) },
  { label: 'Active workflows', render: p => p.max_active_workflows === null ? 'Unlimited' : String(p.max_active_workflows) },
  { label: 'Users', render: p => p.max_users === null ? 'Custom' : String(p.max_users) },
  { label: 'AI', render: p => p.plan === 'free' ? 'Trial credits' : (p.plan === 'enterprise' ? 'Custom' : 'PAYG/BYOK') },
  { label: 'Integrations', render: p => fmtTier(p.integrations) },
  { label: 'Execution history', render: p => p.execution_history_days === null ? 'Custom' : `${p.execution_history_days} day${p.execution_history_days === 1 ? '' : 's'}` },
  { label: 'AI Workflow Builder', render: p => fmtTier(p.ai_workflow_builder) },
  { label: 'AI Agents', render: p => fmtTier(p.ai_agents) },
  { label: 'Versioning', render: p => fmtTier(p.versioning) },
  { label: 'Analytics', render: p => fmtTier(p.analytics) },
  { label: 'RBAC/Audit logs', render: p => fmtBool(p.rbac_audit_logs) },
  { label: 'SSO/SAML', render: p => p.plan === 'business' ? 'Add-on' : fmtBool(p.sso_saml) },
  { label: 'Dedicated workers', render: p => p.plan === 'business' ? 'Add-on' : fmtBool(p.dedicated_workers) },
  { label: 'On-premise', render: p => fmtBool(p.on_premise) },
  { label: 'SLA/support', render: p => fmtTier(p.support) },
]

export default function PricingPage() {
  const [requestedPlan, setRequestedPlan] = useState<string | null>(null)
  const pendingCheckoutPlan = useRef<string | null>(null)

  const { data: plans, isLoading } = useQuery({ queryKey: ['billing-plans'], queryFn: billingApi.plans })
  const { data: usage } = useQuery({ queryKey: ['billing-usage'], queryFn: billingApi.usage })

  const checkoutMut = useMutation({
    mutationFn: (plan: string) => billingApi.checkout(plan),
    onSuccess: (data) => {
      // Real Stripe Checkout — redirect the browser to Stripe's hosted
      // page. No card data ever touches this app's own frontend/backend.
      window.location.href = data.checkout_url
    },
    onError: (e: any) => {
      if (e?.response?.status === 501) {
        // This deployment has no Stripe merchant account configured yet
        // (core/config.py's STRIPE_SECRET_KEY is empty) — fall back to
        // the manual request flow rather than showing a dead end.
        setRequestedPlan(pendingCheckoutPlan.current)
      } else {
        toast.error(e?.response?.data?.detail || 'Checkout failed')
        setRequestedPlan(null)
      }
    },
  })

  const upgradeMut = useMutation({
    mutationFn: (plan: string) => billingApi.requestUpgrade(plan),
    onSuccess: (_, plan) => {
      toast.success(`Upgrade request sent for ${PLAN_LABELS[plan]}. Our team will follow up.`)
      setRequestedPlan(null)
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || 'Failed to send request'),
  })

  const startUpgrade = (plan: string) => {
    if (plan === 'enterprise') {
      setRequestedPlan(plan) // Enterprise is always sales-assisted, matching the pricing table's "Contact Sales"
      return
    }
    pendingCheckoutPlan.current = plan
    checkoutMut.mutate(plan)
  }

  if (isLoading || !plans) {
    return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)' }}>Loading plans…</div>
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 32 }}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Plans &amp; Pricing</h1>
        <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Pick the plan that fits your team. Upgrade or downgrade anytime.</p>
      </div>

      {usage && (
        <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 24, display: 'flex', gap: 28, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <span style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current plan</span>
            <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--text)', marginTop: 2 }}>
              {usage.is_personal_account ? 'Personal (unmetered)' : PLAN_LABELS[usage.plan] ?? usage.plan}
            </div>
          </div>
          {!usage.is_personal_account && (
            <>
              <UsageBar label="Active workflows" used={usage.usage.active_workflows.used} limit={usage.usage.active_workflows.limit} />
              <UsageBar label="Executions this month" used={usage.usage.executions_this_month.used} limit={usage.usage.executions_this_month.limit} />
              <UsageBar label="Users" used={usage.usage.users.used} limit={usage.usage.users.limit} />
            </>
          )}
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 780 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '10px 14px', fontSize: 11, color: 'var(--text3)', borderBottom: '1px solid var(--border)' }} />
              {plans.map((p: PlanRow) => (
                <th key={p.plan} style={{
                  textAlign: 'center', padding: '10px 14px', borderBottom: `2px solid ${p.plan === FEATURED_PLAN ? 'var(--accent)' : 'var(--border)'}`,
                  background: p.plan === FEATURED_PLAN ? 'rgba(124,58,237,0.06)' : 'transparent',
                }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text)' }}>
                    {PLAN_LABELS[p.plan]} {p.plan === FEATURED_PLAN && '⭐'}
                  </div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: p.plan === FEATURED_PLAN ? 'var(--accent)' : 'var(--text)', marginTop: 4 }}>
                    {fmtPrice(p.price_inr_per_month)}{p.price_inr_per_month ? <span style={{ fontSize: 10, fontWeight: 500, color: 'var(--text3)' }}>/mo</span> : null}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => (
              <tr key={row.label} style={{ background: i % 2 === 0 ? 'transparent' : 'var(--bg2)' }}>
                <td style={{ padding: '9px 14px', fontSize: 12.5, color: 'var(--text2)', fontWeight: 600 }}>{row.label}</td>
                {plans.map((p: PlanRow) => (
                  <td key={p.plan} style={{
                    textAlign: 'center', padding: '9px 14px', fontSize: 12.5, color: 'var(--text)',
                    background: p.plan === FEATURED_PLAN ? 'rgba(124,58,237,0.04)' : 'transparent',
                  }}>
                    {row.render(p)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td />
              {plans.map((p: PlanRow) => (
                <td key={p.plan} style={{ padding: '16px 14px', textAlign: 'center', background: p.plan === FEATURED_PLAN ? 'rgba(124,58,237,0.04)' : 'transparent' }}>
                  {usage?.plan === p.plan && !usage?.is_personal_account ? (
                    <span style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 600 }}>Current plan</span>
                  ) : p.price_inr_per_month === null ? (
                    <button onClick={() => startUpgrade(p.plan)} style={{ padding: '7px 16px', background: 'var(--bg3)', color: 'var(--text2)', border: '1px solid var(--border)', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                      Contact Sales
                    </button>
                  ) : p.plan === 'free' ? (
                    <span style={{ fontSize: 11, color: 'var(--text3)' }}>Default plan</span>
                  ) : (
                    <button onClick={() => startUpgrade(p.plan)} disabled={checkoutMut.isPending}
                      style={{ padding: '7px 16px', background: p.plan === FEATURED_PLAN ? 'var(--accent)' : 'var(--bg3)', color: p.plan === FEATURED_PLAN ? '#fff' : 'var(--text2)', border: p.plan === FEATURED_PLAN ? 'none' : '1px solid var(--border)', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: checkoutMut.isPending ? 'not-allowed' : 'pointer', opacity: checkoutMut.isPending ? 0.7 : 1 }}>
                      {checkoutMut.isPending && pendingCheckoutPlan.current === p.plan ? 'Redirecting…' : 'Upgrade'}
                    </button>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {requestedPlan && (
        <div role="dialog" aria-label="Confirm upgrade request" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, width: 360 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text)', marginBottom: 8 }}>
              Request {PLAN_LABELS[requestedPlan]} plan
            </h3>
            <p style={{ fontSize: 12.5, color: 'var(--text3)', lineHeight: 1.6, marginBottom: 16 }}>
              {requestedPlan === 'enterprise'
                ? "Enterprise pricing is custom — this sends a request to our team, who'll follow up to discuss your needs."
                : "Self-serve checkout isn't available on this deployment yet — this sends a request to our team instead, who'll follow up to complete the upgrade."}
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setRequestedPlan(null)} style={{ flex: 1, padding: '9px 0', background: 'var(--bg3)', color: 'var(--text2)', border: '1px solid var(--border)', borderRadius: 7, fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={() => upgradeMut.mutate(requestedPlan)} disabled={upgradeMut.isPending}
                style={{ flex: 1, padding: '9px 0', background: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 7, fontSize: 12.5, fontWeight: 600, cursor: 'pointer', opacity: upgradeMut.isPending ? 0.7 : 1 }}>
                {upgradeMut.isPending ? 'Sending…' : 'Send Request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min((used / limit) * 100, 100) : 0
  const isNearLimit = limit !== null && used / limit > 0.8
  return (
    <div style={{ minWidth: 160 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, color: 'var(--text3)', marginBottom: 4 }}>
        <span>{label}</span>
        <span>{used}{limit !== null ? ` / ${limit}` : ' (unlimited)'}</span>
      </div>
      {limit !== null && (
        <div style={{ height: 5, background: 'var(--bg3)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${pct}%`, background: isNearLimit ? 'var(--red)' : 'var(--accent)', transition: 'width 0.3s' }} />
        </div>
      )}
    </div>
  )
}
