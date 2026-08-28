import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 15000, refetchOnWindowFocus: false },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={qc}>
    <App />
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'var(--bg2)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          fontSize: '13px',
          fontFamily: 'var(--font)',
        },
        success: { iconTheme: { primary: '#22c55e', secondary: 'var(--bg2)' } },
        error: { iconTheme: { primary: '#ef4444', secondary: 'var(--bg2)' } },
      }}
    />
  </QueryClientProvider>
)
