export interface Workflow {
  id: string
  name: string
  description?: string
  status: 'active' | 'inactive' | 'error'
  definition: WorkflowDefinition
  settings: Record<string, any>
  created_at: string
  updated_at: string
}

export interface WorkflowDefinition {
  nodes: WFNode[]
  edges: WFEdge[]
}

export interface WFNode {
  id: string
  type: string
  label?: string
  config: Record<string, any>
  credential_id?: string
  retry?: { max_attempts: number; wait_min: number; wait_max: number }
  required?: boolean
  position?: { x: number; y: number }
}

export interface WFEdge {
  source: string
  target: string
}

export interface Execution {
  id: string
  workflow_id: string
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled'
  trigger_type: string
  trigger_data: Record<string, any>
  node_results: Record<string, any>
  error?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface Credential {
  id: string
  provider: string
  label: string
  scope?: string
  external_account_id?: string
  external_account_name?: string
  is_valid: boolean
  created_at: string
  updated_at: string
}

export interface Provider {
  name: string
  display_name: string
  icon: string
  scopes: string[]
}

export interface Trigger {
  id: string
  workflow_id: string
  trigger_type: 'webhook' | 'polling' | 'event'
  provider: string
  event: string
  config: Record<string, any>
  credential_id?: string
  is_active: boolean
  last_triggered_at?: string
  webhook_url?: string
  webhook_secret?: string
}

export interface Schedule {
  id: string
  workflow_id: string
  cron_expression?: string
  interval_seconds?: number
  timezone: string
  is_active: boolean
  next_run_at?: string
  last_run_at?: string
}
