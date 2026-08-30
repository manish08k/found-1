import axios from 'axios'

export const BASE_URL = 'https://api.autoxflow.space'

const http = axios.create({ baseURL: BASE_URL + '/api' })

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Access tokens are short-lived (15 min) by design (see api/middleware/auth.py).
// On a 401, try exchanging the refresh token for a new access token ONCE
// before giving up and sending the person back to login — otherwise every
// user gets logged out every 15 minutes, which would make the refresh-token
// system pointless. Concurrent 401s while a refresh is already in flight
// share the same in-flight promise instead of each firing their own
// refresh call (which would race against the single-use rotation and
// trip the reuse-detection on the backend).
let refreshPromise: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null
  if (!refreshPromise) {
    refreshPromise = axios.post(BASE_URL + '/api/auth/refresh', { refresh_token: refreshToken })
      .then(r => {
        localStorage.setItem('token', r.data.access_token)
        localStorage.setItem('refresh_token', r.data.refresh_token)
        return r.data.access_token as string
      })
      .catch(() => {
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        return null
      })
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

http.interceptors.response.use(r => r, async err => {
  const original = err.config
  if (err.response?.status === 401 && !original?._retried && !original?.url?.includes('/auth/refresh')) {
    original._retried = true
    const newToken = await tryRefresh()
    if (newToken) {
      original.headers.Authorization = `Bearer ${newToken}`
      return http(original)
    }
    // Refresh itself failed (expired/revoked/reused) — this really is a logout.
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/'
  }
  return Promise.reject(err)
})

function storeSession(data: { access_token: string; refresh_token: string }) {
  localStorage.setItem('token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)
}

export const authApi = {
  register: (email: string, password: string) =>
    http.post('/auth/register', { email, password }).then(r => { storeSession(r.data); return r.data }),
  // Returns one of three shapes — the caller (LoginPage) branches on which:
  //   { access_token, refresh_token, ... }        -> logged in, done
  //   { mfa_code_required: true }                 -> re-submit with mfa_code
  //   { mfa_enrollment_required: true, setup_token } -> role requires MFA, not yet enrolled
  login: (email: string, password: string, mfa_code?: string) =>
    http.post('/auth/login', { email, password, mfa_code }).then(r => {
      if (r.data.access_token) storeSession(r.data)
      return r.data
    }),
  me: () => http.get('/auth/me').then(r => r.data),
  logout: async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    try { await http.post('/auth/logout', { refresh_token: refreshToken }) } catch { /* best-effort */ }
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
  },
  logoutEverywhere: () => http.post('/auth/logout-everywhere').then(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
  }),
  mfaSetup: (setupToken?: string) =>
    axios.post(BASE_URL + '/api/auth/mfa/setup', {}, { headers: { Authorization: `Bearer ${setupToken ?? localStorage.getItem('token')}` } }).then(r => r.data),
  mfaVerify: (code: string, setupToken?: string) =>
    axios.post(BASE_URL + '/api/auth/mfa/verify', { code }, { headers: { Authorization: `Bearer ${setupToken ?? localStorage.getItem('token')}` } }).then(r => {
      if (r.data.access_token) storeSession(r.data)
      return r.data
    }),
  mfaDisable: () => http.post('/auth/mfa/disable').then(r => r.data),
}

export const billingApi = {
  plans: () => http.get('/billing/plans').then(r => r.data.plans),
  usage: () => http.get('/billing/usage').then(r => r.data),
  checkout: (target_plan: string) => http.post('/billing/checkout', { target_plan }).then(r => r.data),
  requestUpgrade: (target_plan: string, note?: string) =>
    http.post('/billing/upgrade-request', { target_plan, note }).then(r => r.data),
}

export const marketplaceApi = {
  browse: (params: { category?: string; item_type?: string; search?: string; page?: number } = {}) =>
    http.get('/marketplace', { params }).then(r => r.data),
  get: (slug: string) => http.get(`/marketplace/${slug}`).then(r => r.data),
  install: (slug: string) => http.post(`/marketplace/${slug}/install`).then(r => r.data),
  rate: (slug: string, rating: number) => http.post(`/marketplace/${slug}/rate`, { rating }).then(r => r.data),
  publish: (data: { name: string; description?: string; category?: string; tags?: string[]; item_type?: string; content: any }) =>
    http.post('/marketplace/publish', data).then(r => r.data),
}

export const workflowsApi = {
  list: () => http.get('/workflows').then(r => r.data),
  create: (data: any) => http.post('/workflows', data).then(r => r.data),
  get: (id: string) => http.get(`/workflows/${id}`).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/workflows/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/workflows/${id}`),
  activate: (id: string) => http.post(`/workflows/${id}/activate`).then(r => r.data),
  deactivate: (id: string) => http.post(`/workflows/${id}/deactivate`).then(r => r.data),
  execute: (id: string, triggerData?: any) =>
    http.post(`/workflows/${id}/execute`, triggerData || {}).then(r => r.data),
  publishAsTemplate: (id: string, data: { name?: string; description?: string; category?: string; tags?: string[] }) =>
    http.post(`/workflows/${id}/publish-as-template`, data).then(r => r.data),
}

export const executionsApi = {
  list: (workflowId?: string) =>
    http.get('/executions', { params: workflowId ? { workflow_id: workflowId } : {} }).then(r => r.data),
  get: (id: string) => http.get(`/executions/${id}`).then(r => r.data),
  cancel: (id: string) => http.post(`/executions/${id}/cancel`).then(r => r.data),
}

export const credentialsApi = {
  list: (provider?: string) =>
    http.get('/credentials', { params: provider ? { provider } : {} }).then(r => r.data),
  rename: (id: string, label: string) =>
    http.patch(`/credentials/${id}`, { label }).then(r => r.data),
  test: (id: string) => http.post(`/credentials/${id}/test`).then(r => r.data),
  delete: (id: string) => http.delete(`/oauth/credentials/${id}`),
  createManual: (data: {
    label: string; db_type: 'postgres' | 'mysql' | 'sqlite';
    host?: string; port?: number; database: string;
    username?: string; password?: string; ssl?: boolean;
  }) => http.post('/credentials/manual', data).then(r => r.data),
  createApiKey: (data: { provider: 'stripe' | 'sendgrid' | 'twilio' | 'jira' | 'trello' | 'pagerduty' | 'asana' | 'aws_s3' | 'mcp'; label: string; fields: Record<string, string> }) =>
    http.post('/credentials/api-key', data).then(r => r.data),
}

export const providersApi = {
  list: () => http.get('/providers').then(r => r.data),
}

export const triggersApi = {
  list: (workflowId?: string) =>
    http.get('/triggers', { params: workflowId ? { workflow_id: workflowId } : {} }).then(r => r.data),
  create: (data: any) => http.post('/triggers', data).then(r => r.data),
  delete: (id: string) => http.delete(`/triggers/${id}`),
}

export const schedulesApi = {
  list: (workflowId?: string) =>
    http.get('/schedules', { params: workflowId ? { workflow_id: workflowId } : {} }).then(r => r.data),
  create: (data: any) => http.post('/schedules', data).then(r => r.data),
  delete: (id: string) => http.delete(`/schedules/${id}`),
  toggle: (id: string) => http.patch(`/schedules/${id}/toggle`).then(r => r.data),
}

export const nodeTypesApi = {
  list: () => http.get('/node-types').then(r => r.data),
}

export const chatMessagesApi = {
  send: (workflowId: string, question: string, conversationId?: string, overrideConfig?: any) =>
    http.post(`/chat-messages/${workflowId}`, { question, conversationId, overrideConfig }).then(r => r.data),
  list: (workflowId: string, conversationId?: string) =>
    http.get(`/chat-messages/${workflowId}`, { params: conversationId ? { conversationId } : {} }).then(r => r.data),
  clear: (workflowId: string, conversationId?: string) =>
    http.delete(`/chat-messages/${workflowId}`, { params: conversationId ? { conversationId } : {} }).then(r => r.data),
  get: (workflowId: string, messageId: string) =>
    http.get(`/chat-messages/${workflowId}/${messageId}`).then(r => r.data),
}

export const assistantsApi = {
  list: () => http.get('/assistants').then(r => r.data),
  create: (data: { name: string; description?: string; system_prompt?: string; model?: string; provider?: string; tools?: string[]; temperature?: number; max_tokens?: number; document_store_id?: string }) =>
    http.post('/assistants', data).then(r => r.data),
  get: (id: string) => http.get(`/assistants/${id}`).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/assistants/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/assistants/${id}`),
  // Threads
  createThread: (id: string, metadata?: any) =>
    http.post(`/assistants/${id}/threads`, { metadata }).then(r => r.data),
  listThreads: (id: string) => http.get(`/assistants/${id}/threads`).then(r => r.data),
  // Messages within a thread
  addMessage: (id: string, threadId: string, content: string) =>
    http.post(`/assistants/${id}/threads/${threadId}/messages`, { content }).then(r => r.data),
  listMessages: (id: string, threadId: string) =>
    http.get(`/assistants/${id}/threads/${threadId}/messages`).then(r => r.data),
  runThread: (id: string, threadId: string) =>
    http.post(`/assistants/${id}/threads/${threadId}/run`).then(r => r.data),
}

export const documentStoresApi = {
  list: () => http.get('/document-stores').then(r => r.data),
  create: (data: { name: string; description?: string; embedding_model?: string; embedding_provider?: string; chunk_size?: number; chunk_overlap?: number }) =>
    http.post('/document-stores', data).then(r => r.data),
  get: (id: string) => http.get(`/document-stores/${id}`).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/document-stores/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/document-stores/${id}`),
  upsert: (id: string, documents: Array<{ text: string; metadata?: any }>) =>
    http.post(`/document-stores/${id}/upsert`, { documents }).then(r => r.data),
  query: (id: string, query: string, topK?: number) =>
    http.post(`/document-stores/${id}/query`, { query, top_k: topK }).then(r => r.data),
  clearDocuments: (id: string) => http.delete(`/document-stores/${id}/documents`).then(r => r.data),
  listChunks: (id: string, page?: number, pageSize?: number) =>
    http.get(`/document-stores/${id}/chunks`, { params: { page, page_size: pageSize } }).then(r => r.data),
}

export const apiKeysApi = {
  list: () => http.get('/api-keys').then(r => r.data),
  create: (data: { name: string; description?: string; expires_at?: string }) =>
    http.post('/api-keys', data).then(r => r.data),
  rename: (id: string, name: string, description?: string) =>
    http.put(`/api-keys/${id}`, { name, description }).then(r => r.data),
  revoke: (id: string) => http.delete(`/api-keys/${id}`).then(r => r.data),
  rotate: (id: string) => http.post(`/api-keys/${id}/rotate`).then(r => r.data),
}

export const variablesApi = {
  list: () => http.get('/variables').then(r => r.data),
  create: (data: { name: string; value: string; description?: string; is_secret?: boolean; variable_type?: string }) =>
    http.post('/variables', data).then(r => r.data),
  get: (id: string) => http.get(`/variables/${id}`).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/variables/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/variables/${id}`),
}

export const leadsApi = {
  list: (params?: { status?: string; workflow_id?: string; page?: number; page_size?: number }) =>
    http.get('/leads', { params }).then(r => r.data),
  create: (data: { name?: string; email?: string; phone?: string; workflow_id?: string; conversation_id?: string; status?: string; metadata?: any }) =>
    http.post('/leads', data).then(r => r.data),
  get: (id: string) => http.get(`/leads/${id}`).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/leads/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/leads/${id}`),
  exportCsv: () => http.get('/leads/export/csv', { responseType: 'blob' }).then(r => r.data),
}

export const feedbackApi = {
  list: (params?: { workflow_id?: string; rating?: number; page?: number; page_size?: number }) =>
    http.get('/feedback', { params }).then(r => r.data),
  create: (data: { message_id: string; rating: 1 | -1; workflow_id?: string; conversation_id?: string; content?: string }) =>
    http.post('/feedback', data).then(r => r.data),
  get: (id: string) => http.get(`/feedback/${id}`).then(r => r.data),
  stats: (workflowId?: string) =>
    http.get('/feedback/stats', { params: workflowId ? { workflow_id: workflowId } : {} }).then(r => r.data),
}

// ─── Approvals ────────────────────────────────────────────────────────────────
export const approvalsApi = {
  list: (params?: { status?: string }) =>
    http.get('/approvals', { params }).then(r => r.data),
  get: (id: string) => http.get(`/approvals/${id}`).then(r => r.data),
  decide: (id: string, data: { action: 'approve' | 'reject'; reason?: string; edited_data?: any }) =>
    http.post(`/approvals/${id}/decide`, data).then(r => r.data),
  history: (params?: { page?: number; page_size?: number }) =>
    http.get('/approvals/history', { params }).then(r => r.data),
}

// ─── MCP Management ───────────────────────────────────────────────────────────
export const mcpApi = {
  listServers: () => http.get('/mcp/management/servers').then(r => r.data),
  registerServer: (data: { name: string; url: string; auth_type?: string; api_key?: string }) =>
    http.post('/mcp/management/servers', data).then(r => r.data),
  deleteServer: (id: string) => http.delete(`/mcp/management/servers/${id}`).then(r => r.data),
  connectServer: (id: string) => http.post(`/mcp/management/servers/${id}/connect`).then(r => r.data),
  getServerTools: (id: string) => http.get(`/mcp/management/servers/${id}/tools`).then(r => r.data),
  updatePermissions: (id: string, data: { allowed_tools: string[] }) =>
    http.put(`/mcp/management/servers/${id}/permissions`, data).then(r => r.data),
}

// ─── Evaluations ──────────────────────────────────────────────────────────────
export const evaluationsApi = {
  listDatasets: () => http.get('/evaluations/datasets').then(r => r.data),
  createDataset: (data: { name: string; workflow_id?: string; description?: string }) =>
    http.post('/evaluations/datasets', data).then(r => r.data),
  deleteDataset: (id: string) => http.delete(`/evaluations/datasets/${id}`).then(r => r.data),
  listCases: (datasetId: string, page?: number) =>
    http.get(`/evaluations/datasets/${datasetId}/cases`, { params: { page } }).then(r => r.data),
  createCase: (datasetId: string, data: { input_data: any; expected_output?: any; tags?: string[] }) =>
    http.post(`/evaluations/datasets/${datasetId}/cases`, data).then(r => r.data),
  bulkCreateCases: (datasetId: string, cases: Array<{ input_data: any; expected_output?: any }>) =>
    http.post(`/evaluations/datasets/${datasetId}/cases/bulk`, { cases }).then(r => r.data),
  deleteCase: (datasetId: string, caseId: string) =>
    http.delete(`/evaluations/datasets/${datasetId}/cases/${caseId}`).then(r => r.data),
  startRun: (data: { dataset_id: string; workflow_id: string; scorer_type?: string; scorer_config?: any }) =>
    http.post('/evaluations/runs', data).then(r => r.data),
  getRun: (runId: string) => http.get(`/evaluations/runs/${runId}`).then(r => r.data),
  getRunResults: (runId: string, page?: number) =>
    http.get(`/evaluations/runs/${runId}/results`, { params: { page } }).then(r => r.data),
  compareRuns: (run1: string, run2: string) =>
    http.get('/evaluations/compare', { params: { run1, run2 } }).then(r => r.data),
}

// ─── Policies / Guardrails ────────────────────────────────────────────────────
export const policiesApi = {
  list: () => http.get('/policies').then(r => r.data),
  create: (data: { name: string; description?: string; is_active?: boolean; rules?: any[]; action?: string }) =>
    http.post('/policies', data).then(r => r.data),
  update: (id: string, data: any) => http.patch(`/policies/${id}`, data).then(r => r.data),
  delete: (id: string) => http.delete(`/policies/${id}`).then(r => r.data),
  test: (id: string, data: { workflow: any; trigger_data?: any }) =>
    http.post(`/policies/${id}/test`, data).then(r => r.data),
}

// ─── Costs / Model Routing ────────────────────────────────────────────────────
export const costsApi = {
  getExecutionCosts: (executionId: string) =>
    http.get(`/costs/executions/${executionId}`).then(r => r.data),
  getWorkflowCosts: (workflowId: string, days?: number) =>
    http.get(`/costs/workflows/${workflowId}`, { params: { days } }).then(r => r.data),
  getSummary: (days?: number) =>
    http.get('/costs/summary', { params: { days } }).then(r => r.data),
  setBudget: (data: { workflow_id?: string; monthly_budget_usd: number; alert_threshold_pct?: number }) =>
    http.post('/costs/budgets', data).then(r => r.data),
  routeModel: (data: { preferred_model: string; budget_usd?: number; requirements?: any }) =>
    http.post('/costs/route-model', data).then(r => r.data),
}

// ─── Workflow Versions ────────────────────────────────────────────────────────
export const versionsApi = {
  list: (workflowId: string) =>
    http.get(`/workflows/${workflowId}/versions`).then(r => r.data),
  get: (workflowId: string, version: number) =>
    http.get(`/workflows/${workflowId}/versions/${version}`).then(r => r.data),
  rollback: (workflowId: string, version: number) =>
    http.post(`/workflows/${workflowId}/versions/${version}/rollback`).then(r => r.data),
  publish: (workflowId: string, version: number) =>
    http.post(`/workflows/${workflowId}/versions/${version}/publish`).then(r => r.data),
  diff: (workflowId: string, v1: number, v2: number) =>
    http.get(`/workflows/${workflowId}/versions/diff`, { params: { v1, v2 } }).then(r => r.data),
}

// ─── AI Builder ───────────────────────────────────────────────────────────────
export const aiBuilderApi = {
  generate: (data: { prompt: string; workflow_id?: string }) =>
    http.post('/ai-builder/generate', data).then(r => r.data),
  apply: (data: { workflow_id?: string; name?: string; nodes: any[]; edges: any[] }) =>
    http.post('/ai-builder/apply', data).then(r => r.data),
  validate: (data: { nodes: any[]; edges: any[] }) =>
    http.post('/ai-builder/validate', data).then(r => r.data),
}

// ─── Execution Debug ──────────────────────────────────────────────────────────
export const debugApi = {
  getDebugInfo: (executionId: string) =>
    http.get(`/executions/${executionId}/debug`).then(r => r.data),
  retryNode: (executionId: string, nodeId: string) =>
    http.post(`/executions/${executionId}/retry-node/${nodeId}`).then(r => r.data),
  replay: (executionId: string) =>
    http.post(`/executions/${executionId}/replay`).then(r => r.data),
  replayFrom: (executionId: string, nodeId: string) =>
    http.post(`/executions/${executionId}/replay-from/${nodeId}`).then(r => r.data),
}
