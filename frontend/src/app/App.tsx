import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { PlateProvider } from '@/app/plate/PlateProvider'
import { PlanProvider } from '@/app/plans/PlanProvider'
import { AppShell } from '@/components/AppShell'
import { AboutPage } from '@/pages/AboutPage'
import { AnalysisPage } from '@/pages/AnalysisPage'
import { ComparePage } from '@/pages/ComparePage'
import { DesignerPage } from '@/pages/DesignerPage'
import { ExplorePage } from '@/pages/ExplorePage'
import { TodayMenuPage } from '@/pages/TodayMenuPage'
import { WeeklyPlanPage } from '@/pages/WeeklyPlanPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <PlateProvider>
        <PlanProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<AppShell />}>
                <Route index element={<DesignerPage />} />
                <Route path="weekly" element={<WeeklyPlanPage />} />
                <Route path="today" element={<TodayMenuPage />} />
                <Route path="analysis" element={<AnalysisPage />} />
                <Route path="explore" element={<ExplorePage />} />
                <Route path="compare" element={<ComparePage />} />
                <Route path="about" element={<AboutPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </PlanProvider>
      </PlateProvider>
    </QueryClientProvider>
  )
}
