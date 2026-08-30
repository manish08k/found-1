import { create } from 'zustand'
import type { Workflow, Credential, Execution } from '../types'

type Page = 'workflows' | 'credentials' | 'executions' | 'marketplace' | 'pricing' | 'assistants' | 'document-stores' | 'api-keys' | 'variables' | 'leads' | 'approvals' | 'mcp' | 'evaluations' | 'policies' | 'costs' | 'ai-builder' | 'debugger' | 'versions' | 'agentflow'

interface AppState {
  user: any | null
  setUser: (u: any) => void
  workflows: Workflow[]
  setWorkflows: (w: Workflow[]) => void
  activeWorkflow: Workflow | null
  setActiveWorkflow: (w: Workflow | null) => void
  credentials: Credential[]
  setCredentials: (c: Credential[]) => void
  executions: Execution[]
  setExecutions: (e: Execution[]) => void
  page: Page
  setPage: (p: Page) => void
  selectedNodeId: string | null
  setSelectedNodeId: (id: string | null) => void
}

export const useStore = create<AppState>(set => ({
  user: null,
  setUser: user => set({ user }),
  workflows: [],
  setWorkflows: workflows => set({ workflows }),
  activeWorkflow: null,
  setActiveWorkflow: activeWorkflow => set({ activeWorkflow }),
  credentials: [],
  setCredentials: credentials => set({ credentials }),
  executions: [],
  setExecutions: executions => set({ executions }),
  page: 'workflows',
  setPage: page => set({ page }),
  selectedNodeId: null,
  setSelectedNodeId: selectedNodeId => set({ selectedNodeId }),
}))
