import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider, theme } from 'antd'
import ruRU from 'antd/locale/ru_RU'

import App from './App'
import './style.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={ruRU}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            borderRadius: 8,
            colorPrimary: '#27272a',
            colorText: '#18181b',
            colorTextSecondary: '#71717a',
            colorBorder: '#e4e4e7',
            colorBgLayout: '#fafafa',
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          },
          components: {
            Card: { borderRadiusLG: 12, boxShadowTertiary: 'none' },
            Menu: { itemSelectedBg: '#e4e4e7', itemSelectedColor: '#18181b', itemBorderRadius: 6 },
            Table: { headerBg: '#fafafa', headerColor: '#71717a', rowHoverBg: '#fafafa' },
          },
        }}
      >
        <AntApp>
          <App />
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
