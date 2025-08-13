import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ResultsPage from './pages/ResultsPage'
import DoctorDetailPage from './pages/DoctorDetailPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/doctor/:id" element={<DoctorDetailPage />} />
      </Routes>
    </Layout>
  )
}

export default App
