import React, { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { workflowsApi, credentialsApi } from '../api/client'
import { useStore } from '../store'
import Sidebar from './sidebar/Sidebar'
import WorkflowList from './WorkflowList'
import WorkflowEditor from './canvas/WorkflowEditor'
import CredentialsPage from './pages/CredentialsPage'
import ExecutionsPage from './pages/ExecutionsPage'
import MarketplacePage from './pages/MarketplacePage'
import PricingPage from './pages/PricingPage'
import AssistantsPage from './pages/AssistantsPage'
import DocumentStoresPage from './pages/DocumentStoresPage'
import ApiKeysPage from './pages/ApiKeysPage'
import VariablesPage from './pages/VariablesPage'
import LeadsPage from './pages/LeadsPage'
// Feature pages for 10 advanced capabilities
import ApprovalsPage from './pages/ApprovalsPage'
import MCPPage from './pages/MCPPage'
import EvaluationsPage from './pages/EvaluationsPage'
import PoliciesPage from './pages/PoliciesPage'
import CostsPage from './pages/CostsPage'
import AIBuilderPage from './pages/AIBuilderPage'
import DebuggerPage from './pages/DebuggerPage'
import VersionsPage from './pages/VersionsPage'
import AgentFlowPage from './pages/AgentFlowPage'

export default function Dashboard() {
  const { activeWorkflow, setWorkflows, setCredentials, page } = useStore()

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list, refetchInterval: 30000 })
  const { data: credData } = useQuery({ queryKey: ['credentials'], queryFn: () => credentialsApi.list(), refetchInterval: 60000 })

  useEffect(() => { if (wfData?.workflows) setWorkflows(wfData.workflows) }, [wfData])
  useEffect(() => { if (credData?.credentials) setCredentials(credData.credentials) }, [credData])

  const renderMain = () => {
    if (activeWorkflow) return <WorkflowEditor />
    switch (page) {
      case 'credentials':     return <CredentialsPage />
      case 'executions':      return <ExecutionsPage />
      case 'marketplace':     return <MarketplacePage />
      case 'pricing':         return <PricingPage />
      case 'assistants':      return <AssistantsPage />
      case 'document-stores': return <DocumentStoresPage />
      case 'api-keys':        return <ApiKeysPage />
      case 'variables':       return <VariablesPage />
      case 'leads':           return <LeadsPage />
      // 10 advanced capability pages
      case 'approvals':       return <ApprovalsPage />
      case 'mcp':             return <MCPPage />
      case 'evaluations':     return <EvaluationsPage />
      case 'policies':        return <PoliciesPage />
      case 'costs':           return <CostsPage />
      case 'ai-builder':      return <AIBuilderPage />
      case 'debugger':        return <DebuggerPage />
      case 'versions':        return <VersionsPage />
      case 'agentflow':       return <AgentFlowPage />
      default:                return <WorkflowList />
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: 'var(--bg)' }}>
      <Sidebar />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {renderMain()}
      </main>
    </div>
  )
}
