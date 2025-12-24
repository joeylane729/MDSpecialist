import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ResultsPage from './pages/ResultsPage'

import SpecialistResultsPage from './pages/SpecialistResultsPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/specialist-results" element={<SpecialistResultsPage />} />

      </Routes>
    </Layout>
  )
}

export default App
