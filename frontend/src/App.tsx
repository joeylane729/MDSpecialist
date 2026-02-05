import { Routes, Route } from 'react-router-dom'
import { TestingModeProvider } from './contexts/TestingModeContext'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ResultsPage from './pages/ResultsPage'
import CPTTestingPage from './pages/CPTTestingPage'
import SpecialistResultsPage from './pages/SpecialistResultsPage'

function App() {
  return (
    <TestingModeProvider>
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/cpt-testing" element={<CPTTestingPage />} />
        <Route path="/specialist-results" element={<SpecialistResultsPage />} />

      </Routes>
    </Layout>
    </TestingModeProvider>
  )
}

export default App
