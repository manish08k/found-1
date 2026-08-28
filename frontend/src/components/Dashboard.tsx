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

export default function Dashboard() {
  const { activeWorkflow, setWorkflows, setCredentials, page } = useStore()

  const { data: wfData } = useQuery({ queryKey: ['workflows'], queryFn: workflowsApi.list, refetchInterval: 30000 })
  const { data: credData } = useQuery({ queryKey: ['credentials'], queryFn: () => credentialsApi.list(), refetchInterval: 60000 })

  useEffect(() => { if (wfData?.workflows) setWorkflows(wfData.workflows) }, [wfData])
  useEffect(() => { if (credData?.credentials) setCredentials(credData.credentials) }, [credData])

  const renderMain = () => {
    if (activeWorkflow) return <WorkflowEditor />
    if (page === 'credentials') return <CredentialsPage />
    if (page === 'executions') return <ExecutionsPage />
    if (page === 'marketplace') return <MarketplacePage />
    if (page === 'pricing') return <PricingPage />
    if (page === 'assistants') return <AssistantsPage />
    if (page === 'document-stores') return <DocumentStoresPage />
    if (page === 'api-keys') return <ApiKeysPage />
    if (page === 'variables') return <VariablesPage />
    if (page === 'leads') return <LeadsPage />
    return <WorkflowList />
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
