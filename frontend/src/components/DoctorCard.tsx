import { Link } from 'react-router-dom'
import { MapPin, Phone, Mail, Globe, Star, Award, BookOpen, Users } from 'lucide-react'
import { Doctor } from '../services/api'

interface DoctorCardProps {
  doctor: Doctor
  showRank?: boolean
}

export default function DoctorCard({ doctor, showRank = true }: DoctorCardProps) {
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
    if (!doctor.patient_reviews || doctor.patient_reviews.length === 0) return null
    
    const totalRating = doctor.patient_reviews.reduce((sum, review) => sum + review.rating, 0)
    const averageRating = totalRating / doctor.patient_reviews.length
    
    return {
      rating: averageRating,
      count: doctor.patient_reviews.length
    }
  }

  const patientRating = getPatientRating()

  return (
    <div className="card hover:shadow-md transition-shadow duration-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-3 mb-2">
            {showRank && doctor.rank && (
              <div className="bg-primary-100 text-primary-800 rounded-full w-8 h-8 flex items-center justify-center text-sm font-bold">
                {doctor.rank}
              </div>
            )}
            <div>
              <h3 className="text-xl font-semibold text-gray-900">
                {doctor.display_name}
              </h3>
              <p className="text-gray-600">{doctor.specialty}</p>
              {doctor.subspecialty && (
                <p className="text-sm text-gray-500">{doctor.subspecialty}</p>
              )}
            </div>
          </div>
          
          {/* Grade */}
          {doctor.overall_grade && (
            <div className="flex items-center space-x-2 mb-3">
              <span className={`text-lg font-bold ${getGradeColor(doctor.overall_grade)}`}>
                Grade {doctor.overall_grade}
              </span>
              <span className={getGradeClass(doctor.overall_grade)}>
                {doctor.overall_grade}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Location */}
      <div className="flex items-center text-gray-600 mb-4">
        <MapPin className="h-4 w-4 mr-2" />
        <span>{doctor.location_summary}</span>
      </div>

      {/* Key Information */}
      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        <div>
          <span className="text-gray-500">Experience:</span>
          <span className="ml-2 font-medium">{formatExperience(doctor.years_experience)}</span>
        </div>
        <div>
          <span className="text-gray-500">Medical School:</span>
          <span className="ml-2 font-medium">{doctor.medical_school || 'N/A'}</span>
        </div>
        {doctor.board_certifications && doctor.board_certifications.length > 0 && (
          <div className="col-span-2">
            <span className="text-gray-500">Board Certifications:</span>
            <span className="ml-2 font-medium">
              {doctor.board_certifications.join(', ')}
            </span>
          </div>
        )}
      </div>

      {/* Patient Rating */}
      {patientRating && (
        <div className="flex items-center space-x-2 mb-4">
          <div className="flex items-center">
            {[...Array(5)].map((_, i) => (
              <Star
                key={i}
                className={`h-4 w-4 ${
                  i < Math.round(patientRating.rating)
                    ? 'text-yellow-400 fill-current'
                    : 'text-gray-300'
                }`}
              />
            ))}
          </div>
          <span className="text-sm text-gray-600">
            {patientRating.rating.toFixed(1)} ({patientRating.count} reviews)
          </span>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
        {doctor.website_mentions && (
          <div className="text-center">
            <div className="text-lg font-semibold text-primary-600">{doctor.website_mentions}</div>
            <div className="text-gray-500">Mentions</div>
          </div>
        )}
        {doctor.publications && doctor.publications.length > 0 && (
          <div className="text-center">
            <div className="text-lg font-semibold text-primary-600">{doctor.publications.length}</div>
            <div className="text-gray-500">Publications</div>
          </div>
        )}
        {doctor.talks && doctor.talks.length > 0 && (
          <div className="text-center">
            <div className="text-lg font-semibold text-primary-600">{doctor.talks.length}</div>
            <div className="text-gray-500">Presentations</div>
          </div>
        )}
      </div>

      {/* Contact Information */}
      <div className="border-t border-gray-200 pt-4 mb-4">
        <div className="flex flex-wrap gap-2">
          {doctor.phone && (
            <div className="flex items-center text-sm text-gray-600">
              <Phone className="h-3 w-3 mr-1" />
              <span>{doctor.phone}</span>
            </div>
          )}
          {doctor.email && (
            <div className="flex items-center text-sm text-gray-600">
              <Mail className="h-3 w-3 mr-1" />
              <span>{doctor.email}</span>
            </div>
          )}
          {doctor.website && (
            <div className="flex items-center text-sm text-gray-600">
              <Globe className="h-3 w-3 mr-1" />
              <a
                href={doctor.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 hover:underline"
              >
                Website
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex space-x-3">
        <Link
          to={`/doctor/${doctor.id}`}
          className="btn-primary flex-1 text-center"
        >
          View Details
        </Link>
        {doctor.phone && (
          <a
            href={`tel:${doctor.phone}`}
            className="btn-secondary flex items-center justify-center space-x-2"
          >
            <Phone className="h-4 w-4" />
            <span>Call</span>
          </a>
        )}
      </div>
    </div>
  )
}
