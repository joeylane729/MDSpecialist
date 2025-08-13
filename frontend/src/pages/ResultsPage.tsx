import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Search, Filter, MapPin, Clock, Users } from 'lucide-react'
import DoctorCard from '../components/DoctorCard'
import { MatchResponse, Doctor } from '../services/api'

export default function ResultsPage() {
  const navigate = useNavigate()
  const [results, setResults] = useState<MatchResponse | null>(null)
  const [filteredDoctors, setFilteredDoctors] = useState<Doctor[]>([])
  const [sortBy, setSortBy] = useState<'rank' | 'grade' | 'experience' | 'location'>('rank')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Get results from session storage
    const storedResults = sessionStorage.getItem('matchResults')
    if (storedResults) {
      try {
        const parsedResults = JSON.parse(storedResults) as MatchResponse
        setResults(parsedResults)
        setFilteredDoctors(parsedResults.doctors)
      } catch (error) {
        console.error('Failed to parse stored results:', error)
        navigate('/')
      }
    } else {
      navigate('/')
    }
    setLoading(false)
  }, [navigate])

  const handleSort = (sortType: typeof sortBy) => {
    setSortBy(sortType)
    
    const sorted = [...filteredDoctors].sort((a, b) => {
      switch (sortType) {
        case 'rank':
          return (a.rank || 0) - (b.rank || 0)
        case 'grade':
          const gradeOrder = { 'A+': 13, 'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8, 'C+': 7, 'C': 6, 'C-': 5, 'D+': 4, 'D': 3, 'D-': 2, 'F': 1 }
          return (gradeOrder[b.overall_grade as keyof typeof gradeOrder] || 0) - (gradeOrder[a.overall_grade as keyof typeof gradeOrder] || 0)
        case 'experience':
          return (b.years_experience || 0) - (a.years_experience || 0)
        case 'location':
          // Simple location sorting - could be enhanced with actual distance calculation
          return (a.metro_area || '').localeCompare(b.metro_area || '')
        default:
          return 0
      }
    })
    
    setFilteredDoctors(sorted)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="text-center">
        <p className="text-gray-600 mb-4">No results found.</p>
        <Link to="/" className="btn-primary">
          Start New Search
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Search
        </button>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Search Results
          </h1>
          <p className="text-gray-600 mb-4">
            {results.search_summary}
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center text-gray-600">
              <Search className="h-4 w-4 mr-2" />
              <span>{results.total_doctors_found} doctors found</span>
            </div>
            <div className="flex items-center text-gray-600">
              <MapPin className="h-4 w-4 mr-2" />
              <span>{results.metro_area}</span>
            </div>
            {results.location_radius && (
              <div className="flex items-center text-gray-600">
                <MapPin className="h-4 w-4 mr-2" />
                <span>Within {results.location_radius} miles</span>
              </div>
            )}
            {results.search_duration_ms && (
              <div className="flex items-center text-gray-600">
                <Clock className="h-4 w-4 mr-2" />
                <span>{results.search_duration_ms}ms</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Filters and Sorting */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center space-y-4 sm:space-y-0">
          <div className="flex items-center space-x-2">
            <Filter className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">Sort by:</span>
          </div>
          
          <div className="flex space-x-2">
            <button
              onClick={() => handleSort('rank')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                sortBy === 'rank'
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Rank
            </button>
            <button
              onClick={() => handleSort('grade')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                sortBy === 'grade'
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Grade
            </button>
            <button
              onClick={() => handleSort('experience')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                sortBy === 'experience'
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Experience
            </button>
            <button
              onClick={() => handleSort('location')}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                sortBy === 'location'
                  ? 'bg-primary-100 text-primary-700'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Location
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {filteredDoctors.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredDoctors.map((doctor) => (
            <DoctorCard key={doctor.id} doctor={doctor} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No doctors found</h3>
          <p className="text-gray-600 mb-6">
            Try adjusting your search criteria or expanding your search radius.
          </p>
          <Link to="/" className="btn-primary">
            Start New Search
          </Link>
        </div>
      )}

      {/* Footer */}
      <div className="mt-12 text-center text-gray-500 text-sm">
        <p>
          Results are ranked based on objective criteria including training, experience, 
          publications, and location. Contact doctors directly for appointments.
        </p>
      </div>
    </div>
  )
}
