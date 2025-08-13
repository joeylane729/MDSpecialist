import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, MapPin, Phone, Mail, Globe, Star, Award, BookOpen, Users, Calendar, Building, GraduationCap } from 'lucide-react'
import { getDoctor, Doctor } from '../services/api'

export default function DoctorDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [doctor, setDoctor] = useState<Doctor | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return

    const fetchDoctor = async () => {
      try {
        const doctorData = await getDoctor(parseInt(id))
        setDoctor(doctorData)
      } catch (err) {
        setError('Failed to load doctor information')
        console.error('Error fetching doctor:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchDoctor()
  }, [id])

  const getGradeClass = (grade?: string) => {
    if (!grade) return 'grade-badge bg-gray-100 text-gray-800'
    return `grade-badge grade-${grade.toLowerCase().replace('+', '-plus')}`
  }

  const getGradeColor = (grade?: string) => {
    if (!grade) return 'text-gray-600'
    if (grade.startsWith('A')) return 'text-green-600'
    if (grade.startsWith('B')) return 'text-blue-600'
    if (grade.startsWith('C')) return 'text-yellow-600'
    if (grade.startsWith('D')) return 'text-orange-600'
    return 'text-red-600'
  }

  const formatExperience = (years?: number) => {
    if (!years) return 'N/A'
    if (years === 1) return '1 year'
    return `${years} years`
  }

  const getPatientRating = () => {
    if (!doctor?.patient_reviews || doctor.patient_reviews.length === 0) return null
    
    const totalRating = doctor.patient_reviews.reduce((sum, review) => sum + review.rating, 0)
    const averageRating = totalRating / doctor.patient_reviews.length
    
    return {
      rating: averageRating,
      count: doctor.patient_reviews.length
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error || !doctor) {
    return (
      <div className="text-center">
        <p className="text-red-600 mb-4">{error || 'Doctor not found'}</p>
        <Link to="/" className="btn-primary">
          Back to Search
        </Link>
      </div>
    )
  }

  const patientRating = getPatientRating()

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/results')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Results
        </button>
        
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {doctor.display_name}
              </h1>
              <p className="text-xl text-gray-600 mb-2">
                {doctor.specialty}
                {doctor.subspecialty && (
                  <span className="text-gray-500"> • {doctor.subspecialty}</span>
                )}
              </p>
              
              {/* Grade */}
              {doctor.overall_grade && (
                <div className="flex items-center space-x-3 mb-4">
                  <span className={`text-2xl font-bold ${getGradeColor(doctor.overall_grade)}`}>
                    Grade {doctor.overall_grade}
                  </span>
                  <span className={getGradeClass(doctor.overall_grade)}>
                    {doctor.overall_grade}
                  </span>
                </div>
              )}

              {/* Location */}
              <div className="flex items-center text-gray-600 mb-4">
                <MapPin className="h-5 w-5 mr-2" />
                <span className="text-lg">{doctor.location_summary}</span>
              </div>
            </div>

            {/* Contact Actions */}
            <div className="flex flex-col space-y-3 mt-4 lg:mt-0">
              {doctor.phone && (
                <a
                  href={`tel:${doctor.phone}`}
                  className="btn-primary flex items-center justify-center space-x-2"
                >
                  <Phone className="h-4 w-4" />
                  <span>Call Now</span>
                </a>
              )}
              {doctor.website && (
                <a
                  href={doctor.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary flex items-center justify-center space-x-2"
                >
                  <Globe className="h-4 w-4" />
                  <span>Visit Website</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Professional Information */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
              <GraduationCap className="h-5 w-5 mr-2" />
              Professional Information
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <span className="text-gray-500">Medical School:</span>
                <span className="ml-2 font-medium">{doctor.medical_school || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-500">Graduation Year:</span>
                <span className="ml-2 font-medium">{doctor.graduation_year || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-500">Residency Program:</span>
                <span className="ml-2 font-medium">{doctor.residency_program || 'N/A'}</span>
              </div>
              <div>
                <span className="text-gray-500">Years of Experience:</span>
                <span className="ml-2 font-medium">{formatExperience(doctor.years_experience)}</span>
              </div>
            </div>

            {doctor.board_certifications && doctor.board_certifications.length > 0 && (
              <div className="mt-4">
                <span className="text-gray-500">Board Certifications:</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {doctor.board_certifications.map((cert, index) => (
                    <span
                      key={index}
                      className="bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-sm"
                    >
                      {cert}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {doctor.fellowship_programs && doctor.fellowship_programs.length > 0 && (
              <div className="mt-4">
                <span className="text-gray-500">Fellowship Programs:</span>
                <div className="mt-2 space-y-1">
                  {doctor.fellowship_programs.map((fellowship, index) => (
                    <div key={index} className="text-sm">
                      <span className="font-medium">{fellowship.program}</span>
                      {fellowship.tier && (
                        <span className="text-gray-500 ml-2">({fellowship.tier})</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Experience Details */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
              <Users className="h-5 w-5 mr-2" />
              Experience & Leadership
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-600">{doctor.clinical_years || 0}</div>
                <div className="text-gray-500">Clinical Years</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-600">{doctor.research_years || 0}</div>
                <div className="text-gray-500">Research Years</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-600">{doctor.teaching_years || 0}</div>
                <div className="text-gray-500">Teaching Years</div>
              </div>
            </div>

            {doctor.leadership_roles && doctor.leadership_roles.length > 0 && (
              <div className="mt-4">
                <span className="text-gray-500">Leadership Roles:</span>
                <div className="mt-2 space-y-1">
                  {doctor.leadership_roles.map((role, index) => (
                    <div key={index} className="flex items-center text-sm">
                      <Award className="h-4 w-4 text-yellow-500 mr-2" />
                      <span>{role}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {doctor.awards && doctor.awards.length > 0 && (
              <div className="mt-4">
                <span className="text-gray-500">Awards & Honors:</span>
                <div className="mt-2 space-y-1">
                  {doctor.awards.map((award, index) => (
                    <div key={index} className="flex items-center text-sm">
                      <Award className="h-4 w-4 text-yellow-500 mr-2" />
                      <span>{award}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Patient Reviews */}
          {patientRating && (
            <div className="card">
              <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                <Star className="h-5 w-5 mr-2" />
                Patient Reviews
              </h2>
              
              <div className="flex items-center space-x-4 mb-4">
                <div className="flex items-center">
                  {[...Array(5)].map((_, i) => (
                    <Star
                      key={i}
                      className={`h-6 w-6 ${
                        i < Math.round(patientRating.rating)
                          ? 'text-yellow-400 fill-current'
                          : 'text-gray-300'
                      }`}
                    />
                  ))}
                </div>
                <div>
                  <div className="text-2xl font-bold text-gray-900">
                    {patientRating.rating.toFixed(1)}
                  </div>
                  <div className="text-gray-500">
                    {patientRating.count} review{patientRating.count !== 1 ? 's' : ''}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {doctor.patient_reviews?.map((review, index) => (
                  <div key={index} className="border-l-4 border-primary-200 pl-4">
                    <div className="flex items-center space-x-2 mb-1">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          className={`h-4 w-4 ${
                            i < review.rating
                              ? 'text-yellow-400 fill-current'
                              : 'text-gray-300'
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-gray-700">{review.comment}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Contact Information */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
            
            <div className="space-y-3">
              {doctor.phone && (
                <div className="flex items-center text-gray-600">
                  <Phone className="h-4 w-4 mr-3" />
                  <a href={`tel:${doctor.phone}`} className="text-primary-600 hover:underline">
                    {doctor.phone}
                  </a>
                </div>
              )}
              
              {doctor.email && (
                <div className="flex items-center text-gray-600">
                  <Mail className="h-4 w-4 mr-3" />
                  <a href={`mailto:${doctor.email}`} className="text-primary-600 hover:underline">
                    {doctor.email}
                  </a>
                </div>
              )}
              
              {doctor.website && (
                <div className="flex items-center text-gray-600">
                  <Globe className="h-4 w-4 mr-3" />
                  <a
                    href={doctor.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary-600 hover:underline"
                  >
                    Visit Website
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* Address */}
          {doctor.address_line1 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Address</h3>
              
              <div className="text-gray-600">
                <p>{doctor.address_line1}</p>
                {doctor.address_line2 && <p>{doctor.address_line2}</p>}
                <p>{doctor.city}, {doctor.state} {doctor.zip_code}</p>
              </div>
            </div>
          )}

          {/* Online Presence */}
          <div className="card">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Online Presence</h3>
            
            <div className="space-y-3">
              {doctor.website_mentions && (
                <div className="flex justify-between">
                  <span className="text-gray-600">Website Mentions:</span>
                  <span className="font-medium">{doctor.website_mentions}</span>
                </div>
              )}
              
              {doctor.directory_listings && doctor.directory_listings.length > 0 && (
                <div>
                  <span className="text-gray-600">Directory Listings:</span>
                  <div className="mt-2 space-y-1">
                    {doctor.directory_listings.map((listing, index) => (
                      <div key={index} className="text-sm text-primary-600">
                        {listing}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
