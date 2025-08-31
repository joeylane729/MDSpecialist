import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ResultsPage from './pages/ResultsPage'

import LangChainResultsPage from './pages/LangChainResultsPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/langchain-results" element={<LangChainResultsPage />} />

      </Routes>
    </Layout>
  )
}

export default App
