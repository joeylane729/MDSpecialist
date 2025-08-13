import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, MapPin, Heart, Brain, Bone, Pill } from 'lucide-react'
import { matchDoctors } from '../services/api'

interface MatchForm {
  diagnosis: string
  metro_area: string
  location_radius?: number
  specialty?: string
  subspecialty?: string
}

const specialties = [
  { id: 'cardiology', name: 'Cardiology', icon: Heart, description: 'Heart and cardiovascular health' },
  { id: 'neurology', name: 'Neurology', icon: Brain, description: 'Brain and nervous system' },
  { id: 'orthopedics', name: 'Orthopedics', icon: Bone, description: 'Bones, joints, and muscles' },
  { id: 'endocrinology', name: 'Endocrinology', icon: Pill, description: 'Hormones and metabolism' },
  { id: 'oncology', name: 'Oncology', description: 'Cancer treatment and care' },
  { id: 'dermatology', name: 'Dermatology', description: 'Skin, hair, and nails' },
  { id: 'psychiatry', name: 'Psychiatry', description: 'Mental health and behavior' },
  { id: 'pediatrics', name: 'Pediatrics', description: 'Child and adolescent health' }
]

export default function HomePage() {
  const navigate = useNavigate()
  const [form, setForm] = useState<MatchForm>({
    diagnosis: '',
    metro_area: '',
    location_radius: 25
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      const response = await matchDoctors(form)
      // Store results in session storage for the results page
      sessionStorage.setItem('matchResults', JSON.stringify(response))
      navigate('/results')
    } catch (err) {
      setError('Failed to find doctors. Please try again.')
      console.error('Match error:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (field: keyof MatchForm, value: string | number) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Find Your Perfect Medical Specialist
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          Get matched with top medical specialists based on objective criteria including training, 
          experience, publications, and location.
        </p>
        <div className="flex justify-center space-x-8 text-sm text-gray-500">
          <div className="flex items-center space-x-2">
            <Search className="h-4 w-4" />
            <span>Smart Matching</span>
          </div>
          <div className="flex items-center space-x-2">
            <MapPin className="h-4 w-4" />
            <span>Location Based</span>
          </div>
          <div className="flex items-center space-x-2">
            <Heart className="h-4 w-4" />
            <span>Quality Assured</span>
          </div>
        </div>
      </div>

      {/* Search Form */}
      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Diagnosis */}
          <div>
            <label htmlFor="diagnosis" className="block text-sm font-medium text-gray-700 mb-2">
              What's your diagnosis or condition? *
            </label>
            <input
              type="text"
              id="diagnosis"
              required
              value={form.diagnosis}
              onChange={(e) => handleInputChange('diagnosis', e.target.value)}
              placeholder="e.g., Type 2 Diabetes, Heart Disease, Depression..."
              className="input-field"
            />
            <p className="mt-1 text-sm text-gray-500">
              Be as specific as possible to get better matches
            </p>
          </div>

          {/* Metro Area */}
          <div>
            <label htmlFor="metro_area" className="block text-sm font-medium text-gray-700 mb-2">
              Where are you located? *
            </label>
            <input
              type="text"
              id="metro_area"
              required
              value={form.metro_area}
              onChange={(e) => handleInputChange('metro_area', e.target.value)}
              placeholder="e.g., New York, NY or Los Angeles, CA"
              className="input-field"
            />
            <p className="mt-1 text-sm text-gray-500">
              Enter your metropolitan area for location-based matching
            </p>
          </div>

          {/* Location Radius */}
          <div>
            <label htmlFor="location_radius" className="block text-sm font-medium text-gray-700 mb-2">
              Search radius (miles)
            </label>
            <select
              id="location_radius"
              value={form.location_radius}
              onChange={(e) => handleInputChange('location_radius', Number(e.target.value))}
              className="input-field"
            >
              <option value={10}>10 miles</option>
              <option value={25}>25 miles</option>
              <option value={50}>50 miles</option>
              <option value={100}>100 miles</option>
              <option value={500}>500 miles</option>
            </select>
          </div>

          {/* Specialty (Optional) */}
          <div>
            <label htmlFor="specialty" className="block text-sm font-medium text-gray-700 mb-2">
              Preferred specialty (optional)
            </label>
            <select
              id="specialty"
              value={form.specialty || ''}
              onChange={(e) => handleInputChange('specialty', e.target.value)}
              className="input-field"
            >
              <option value="">Any specialty</option>
              {specialties.map(specialty => (
                <option key={specialty.id} value={specialty.id}>
                  {specialty.name}
                </option>
              ))}
            </select>
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <p className="text-red-800 text-sm">{error}</p>
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary w-full py-3 text-lg disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <div className="flex items-center justify-center space-x-2">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>Finding Doctors...</span>
              </div>
            ) : (
              <div className="flex items-center justify-center space-x-2">
                <Search className="h-5 w-5" />
                <span>Find My Doctor</span>
              </div>
            )}
          </button>
        </form>
      </div>

      {/* Features Section */}
      <div className="mt-16 grid md:grid-cols-3 gap-8">
        <div className="text-center">
          <div className="bg-primary-100 rounded-full p-3 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <Search className="h-8 w-8 text-primary-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Smart Matching</h3>
          <p className="text-gray-600">
            Our algorithm considers training, experience, publications, and more to find the best specialists.
          </p>
        </div>
        <div className="text-center">
          <div className="bg-primary-100 rounded-full p-3 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <MapPin className="h-8 w-8 text-primary-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Location Based</h3>
          <p className="text-gray-600">
            Find doctors in your area with customizable search radius and metro area preferences.
          </p>
        </div>
        <div className="text-center">
          <div className="bg-primary-100 rounded-full p-3 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <Heart className="h-8 w-8 text-primary-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Quality Assured</h3>
          <p className="text-gray-600">
            All doctors are verified with objective criteria including board certifications and experience.
          </p>
        </div>
      </div>
    </div>
  )
}
