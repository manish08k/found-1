import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { evaluationsApi, workflowsApi } from '../../api/client'
import toast from 'react-hot-toast'

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  pending: { color: 'var(--yellow)', bg: 'rgba(245,158,11,0.12)' },
  running: { color: 'var(--accent)', bg: 'rgba(124,58,237,0.12)' },
  completed: { color: 'var(--green)', bg: 'rgba(34,197,94,0.12)' },
  failed: { color: 'var(--red)', bg: 'rgba(239,68,68,0.12)' },
}

function StatusBadge({ s }: { s: string }) {
  const st = STATUS_STYLE[s] ?? STATUS_STYLE.pending
  return <span style={{ padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700, color: st.color, background: st.bg, textTransform: 'uppercase' }}>{s}</span>
}

function DatasetDetail({ dataset, onBack }: { dataset: any; onBack: () => void }) {
  const qc = useQueryClient()
  const [showAddCase, setShowAddCase] = useState(false)
  const [showRunModal, setShowRunModal] = useState(false)
  const [inputData, setInputData] = useState('{}')
  const [expectedOutput, setExpectedOutput] = useState('{}')
  const [selectedRun, setSelectedRun] = useState<string | null>(null)

  const { data: casesData } = useQuery({
    queryKey: ['eval-cases', dataset.id],
    queryFn: () => evaluationsApi.listCases(dataset.id),
  })

  const { data: runData, refetch: refetchRun } = useQuery({
    queryKey: ['eval-run', selectedRun],
    queryFn: () => evaluationsApi.getRun(selectedRun!),
    enabled: !!selectedRun,
    refetchInterval: (d) => d && (d as any).status === 'running' ? 2000 : false,
  })

  const { data: resultsData } = useQuery({
    queryKey: ['eval-results', selectedRun],
    queryFn: () => evaluationsApi.getRunResults(selectedRun!),
    enabled: !!selectedRun && (runData as any)?.status === 'completed',
  })

  const addCaseMut = useMutation({
    mutationFn: () => {
      const input = JSON.parse(inputData)
      const expected = JSON.parse(expectedOutput)
      return evaluationsApi.createCase(dataset.id, { input_data: input, expected_output: expected })
    },
    onSuccess: () => {
      toast.success('Case added')
      qc.invalidateQueries({ queryKey: ['eval-cases', dataset.id] })
      setShowAddCase(false)
      setInputData('{}')
      setExpectedOutput('{}')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Invalid JSON'),
  })

  const deleteCaseMut = useMutation({
    mutationFn: (caseId: string) => evaluationsApi.deleteCase(dataset.id, caseId),
    onSuccess: () => { toast.success('Case removed'); qc.invalidateQueries({ queryKey: ['eval-cases', dataset.id] }) },
  })

  const cases: any[] = casesData?.cases ?? []
  const run: any = runData
  const results: any[] = resultsData?.results ?? []

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <button onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer', fontSize: 13, marginBottom: 12 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
          Datasets
        </button>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{dataset.name}</h1>
            {dataset.description && <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>{dataset.description}</p>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setShowAddCase(true)}
              style={{ padding: '7px 14px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 12 }}>
              + Add Case
            </button>
            <button onClick={() => setShowRunModal(true)} disabled={cases.length === 0}
              style={{ padding: '7px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, opacity: cases.length === 0 ? 0.5 : 1 }}>
              ▶ Run Evaluation
            </button>
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px', display: 'flex', gap: 24 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)', marginBottom: 10 }}>Test Cases ({cases.length})</div>
          {cases.length === 0 && !showAddCase && (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text3)', fontSize: 13 }}>
              No test cases yet. <button onClick={() => setShowAddCase(true)} style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 13, padding: 0 }}>Add one</button>
            </div>
          )}
          {showAddCase && (
            <div style={{ background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 10, padding: 16, marginBottom: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Input Data (JSON)</label>
                  <textarea value={inputData} onChange={e => setInputData(e.target.value)}
                    style={{ width: '100%', height: 100, padding: 8, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 11, resize: 'vertical', boxSizing: 'border-box' }} />
                </div>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Expected Output (JSON)</label>
                  <textarea value={expectedOutput} onChange={e => setExpectedOutput(e.target.value)}
                    style={{ width: '100%', height: 100, padding: 8, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontFamily: 'var(--mono)', fontSize: 11, resize: 'vertical', boxSizing: 'border-box' }} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => addCaseMut.mutate()} disabled={addCaseMut.isPending}
                  style={{ padding: '6px 14px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 7, cursor: 'pointer', fontSize: 12, fontWeight: 600 }}>
                  Save Case
                </button>
                <button onClick={() => setShowAddCase(false)}
                  style={{ padding: '6px 14px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)', borderRadius: 7, cursor: 'pointer', fontSize: 12 }}>
                  Cancel
                </button>
              </div>
            </div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cases.map((c: any, i: number) => (
              <div key={c.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)' }}>Case #{i + 1}</span>
                  <button onClick={() => deleteCaseMut.mutate(c.id)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 11 }}>✕</button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <pre style={{ margin: 0, fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 6, borderRadius: 4, overflow: 'auto', maxHeight: 80, fontFamily: 'var(--mono)' }}>
                    {JSON.stringify(c.input_data, null, 2)}
                  </pre>
                  <pre style={{ margin: 0, fontSize: 10, color: 'var(--text2)', background: 'var(--bg)', padding: 6, borderRadius: 4, overflow: 'auto', maxHeight: 80, fontFamily: 'var(--mono)' }}>
                    {JSON.stringify(c.expected_output, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Run results panel */}
        {selectedRun && run && (
          <div style={{ width: 360, flexShrink: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text2)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              Run Results
              <StatusBadge s={run.status} />
            </div>
            {run.summary && Object.keys(run.summary).length > 0 && (
              <div style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: 14, marginBottom: 12 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {[
                    { label: 'Pass Rate', value: `${run.summary.pass_rate ?? 0}%`, color: 'var(--green)' },
                    { label: 'Avg Score', value: `${run.summary.avg_score ?? 0}`, color: 'var(--accent)' },
                    { label: 'Passed', value: run.summary.pass_count ?? 0, color: 'var(--green)' },
                    { label: 'Failed', value: run.summary.fail_count ?? 0, color: 'var(--red)' },
                  ].map(m => (
                    <div key={m.label} style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 20, fontWeight: 700, color: m.color }}>{m.value}</div>
                      <div style={{ fontSize: 11, color: 'var(--text3)' }}>{m.label}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {run.status === 'running' && (
              <div style={{ color: 'var(--accent)', fontSize: 12, padding: '8px 0' }}>Running test cases…</div>
            )}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {results.map((r: any, i: number) => (
                <div key={r.id} style={{ background: 'var(--bg2)', border: `1px solid ${r.passed ? 'var(--green)' : 'var(--red)'}`, borderRadius: 8, padding: '8px 12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: r.passed ? 'var(--green)' : 'var(--red)' }}>
                      {r.passed ? '✓' : '✗'} Case #{i + 1}
                    </span>
                    <span style={{ fontSize: 10, color: 'var(--text3)' }}>Score: {r.score ?? 0}/100</span>
                  </div>
                  {r.error && <div style={{ fontSize: 10, color: 'var(--red)', fontFamily: 'var(--mono)', wordBreak: 'break-word' }}>{r.error.slice(0, 100)}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {showRunModal && <RunModal datasetId={dataset.id} onClose={() => setShowRunModal(false)} onStart={(runId) => { setSelectedRun(runId); setShowRunModal(false) }} />}
    </div>
  )
}

function RunModal({ datasetId, onClose, onStart }: { datasetId: string; onClose: () => void; onStart: (id: string) => void }) {
  const [workflowId, setWorkflowId] = useState('')
  const [scorer, setScorer] = useState('exact_match')

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list })
  const workflows: any[] = wfData?.workflows ?? []

  const startMut = useMutation({
    mutationFn: () => evaluationsApi.startRun({ dataset_id: datasetId, workflow_id: workflowId, scorer_type: scorer }),
    onSuccess: (data) => { toast.success('Evaluation started'); onStart(data.id) },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed to start'),
  })

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 12, width: 420, padding: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700 }}>Start Evaluation Run</h3>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text3)', cursor: 'pointer' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Workflow *</label>
            <select value={workflowId} onChange={e => setWorkflowId(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              <option value="">Select workflow…</option>
              {workflows.map((w: any) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 6 }}>Scoring Method</label>
            <select value={scorer} onChange={e => setScorer(e.target.value)}
              style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13 }}>
              <option value="exact_match">Exact Match</option>
              <option value="contains">Contains</option>
              <option value="regex">Regex</option>
              <option value="llm_judge">LLM Judge</option>
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: '8px 16px', background: 'var(--bg2)', border: '1px solid var(--border)', color: 'var(--text2)', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>Cancel</button>
          <button onClick={() => startMut.mutate()} disabled={!workflowId || startMut.isPending}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, opacity: (!workflowId || startMut.isPending) ? 0.5 : 1 }}>
            {startMut.isPending ? 'Starting…' : '▶ Start'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function EvaluationsPage() {
  const qc = useQueryClient()
  const [selectedDataset, setSelectedDataset] = useState<any>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['eval-datasets'],
    queryFn: evaluationsApi.listDatasets,
  })

  const createMut = useMutation({
    mutationFn: () => evaluationsApi.createDataset({ name: newName, description: newDesc || undefined }),
    onSuccess: (d) => {
      toast.success('Dataset created')
      qc.invalidateQueries({ queryKey: ['eval-datasets'] })
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
      setSelectedDataset(d)
    },
    onError: (e: any) => toast.error(e.response?.data?.detail || 'Failed'),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => evaluationsApi.deleteDataset(id),
    onSuccess: () => { toast.success('Dataset deleted'); qc.invalidateQueries({ queryKey: ['eval-datasets'] }) },
  })

  if (selectedDataset) {
    return <DatasetDetail dataset={selectedDataset} onBack={() => setSelectedDataset(null)} />
  }

  const datasets: any[] = data?.datasets ?? []

  return (
    <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '24px 32px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text)' }}>Evaluations</h1>
            <p style={{ color: 'var(--text3)', marginTop: 2, fontSize: 13 }}>Test workflow outputs against expected results using automated scoring</p>
          </div>
          <button onClick={() => setShowCreate(true)}
            style={{ padding: '8px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New Dataset
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '0 32px 32px' }}>
        {showCreate && (
          <div style={{ background: 'var(--bg2)', border: '1px solid var(--accent)', borderRadius: 10, padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 4 }}>Name *</label>
                <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="My eval dataset"
                  style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
              </div>
              <div style={{ flex: 2 }}>
                <label style={{ fontSize: 12, color: 'var(--text2)', display: 'block', marginBottom: 4 }}>Description</label>
                <input value={newDesc} onChange={e => setNewDesc(e.target.value)} placeholder="Optional description"
                  style={{ width: '100%', padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, color: 'var(--text)', fontSize: 13, boxSizing: 'border-box' }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => createMut.mutate()} disabled={!newName || createMut.isPending}
                style={{ padding: '7px 16px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, opacity: (!newName || createMut.isPending) ? 0.5 : 1 }}>
                Create
              </button>
              <button onClick={() => setShowCreate(false)}
                style={{ padding: '7px 16px', background: 'var(--bg3)', border: '1px solid var(--border)', color: 'var(--text3)', borderRadius: 8, cursor: 'pointer', fontSize: 12 }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {isLoading && <div style={{ color: 'var(--text3)', fontSize: 13 }}>Loading…</div>}
        {!isLoading && datasets.length === 0 && !showCreate && (
          <div style={{ textAlign: 'center', padding: '64px 0' }}>
            <div style={{ color: 'var(--text2)', fontWeight: 600, marginBottom: 8 }}>No evaluation datasets</div>
            <div style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 20 }}>Create a dataset with test cases and run evaluations against your workflows</div>
            <button onClick={() => setShowCreate(true)}
              style={{ padding: '8px 20px', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
              New Dataset
            </button>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {datasets.map((d: any) => (
            <div key={d.id} style={{ background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, cursor: 'pointer' }}
              onClick={() => setSelectedDataset(d)}>
              <div style={{ width: 36, height: 36, background: 'rgba(124,58,237,0.12)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{d.name}</div>
                {d.description && <div style={{ fontSize: 12, color: 'var(--text3)', marginTop: 2 }}>{d.description}</div>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text3)' }}>{d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}</div>
              <button onClick={e => { e.stopPropagation(); if (confirm('Delete dataset?')) deleteMut.mutate(d.id) }}
                style={{ background: 'transparent', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 13, padding: 4 }}>✕</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
