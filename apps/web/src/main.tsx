import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { AppShell } from './app/AppShell'
import { FixtureLibrary } from './features/fixtures/FixtureLibrary'
import { FixtureSections } from './features/sections/FixtureSections'
import { FloorPlanner } from './features/floor/FloorPlanner'
import { ProductsPage } from './features/products/ProductsPage'
import { RulesPage } from './features/rules/RulesPage'
import { SectionPicker } from './features/shelf/SectionPicker'
import { ShelfPlanner } from './features/shelf/ShelfPlanner'
import { StoreOverview } from './features/store/StoreOverview'
import { StoresPage } from './features/store/StoresPage'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 5_000, retry: 1 } },
})

const router = createBrowserRouter([
  { path: '/design/:code', element: <div className="flex h-full flex-col"><FloorPlanner fullscreen /></div> },
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/stores" replace /> },
      { path: 'stores', element: <StoresPage /> },
      { path: 'stores/:code', element: <StoreOverview /> },
      { path: 'stores/:code/floor', element: <FloorPlanner /> },
      { path: 'stores/:code/plan', element: <SectionPicker /> },
      { path: 'stores/:code/fixtures/:fixtureCode', element: <FixtureSections /> },
      { path: 'fixtures/templates', element: <FixtureLibrary /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'rules', element: <RulesPage /> },
      { path: 'sections/:ref/plan', element: <ShelfPlanner /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
