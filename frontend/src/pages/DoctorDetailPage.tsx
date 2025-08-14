import React from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { MapPin, Phone, Mail, Globe, Star, Award, Calendar, Building, ArrowLeft, CheckCircle, XCircle } from 'lucide-react';

interface Provider {
  id: string;
  npi: string;
  name: string;
  specialty: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  email?: string;
  website?: string;
  rating: number;
  yearsExperience: number;
  boardCertified: boolean;
  acceptingPatients: boolean;
  languages: string[];
  insurance: string[];
  education: {
    medicalSchool: string;
    graduationYear: number;
    residency: string;
  };
}

const DoctorDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const provider = location.state?.provider as Provider;

  if (!provider) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-gray-600 mb-4">Provider not found</p>
          <button
            onClick={() => navigate('/')}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
          >
            Back to Search
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Back Button */}
        <button
          onClick={() => navigate('/results')}
          className="text-blue-600 hover:text-blue-800 mb-6 flex items-center"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Results
        </button>

        {/* Provider Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 mb-8">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between">
            <div className="flex-1">
              <div className="flex items-center mb-4">
                <h1 className="text-4xl font-bold text-gray-900 mr-4">
                  {provider.name}
                </h1>
                <div className="flex items-center">
                  <Star className="h-6 w-6 text-yellow-400 fill-current" />
                  <span className="ml-2 text-xl text-gray-600">{provider.rating}</span>
                </div>
              </div>

              <div className="flex items-center text-gray-600 mb-4">
                <span className="text-xl font-medium">{provider.specialty}</span>
                <span className="mx-3 text-2xl">•</span>
                <Calendar className="h-5 w-5 mr-2" />
                <span className="text-lg">{provider.yearsExperience} years experience</span>
              </div>

              {provider.boardCertified && (
                <div className="flex items-center mb-4">
                  <Award className="h-5 w-5 text-blue-600 mr-2" />
                  <span className="text-blue-600 font-medium text-lg">Board Certified</span>
                </div>
              )}

              <div className="flex items-center text-gray-600 mb-6">
                <MapPin className="h-5 w-5 mr-2" />
                <span className="text-lg">{provider.address}, {provider.city}, {provider.state} {provider.zip}</span>
              </div>

              {/* Status Badge */}
              <div className="mb-6">
                <span className={`inline-flex items-center px-4 py-2 rounded-full text-lg font-medium ${
                  provider.acceptingPatients 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {provider.acceptingPatients ? (
                    <>
                      <CheckCircle className="h-5 w-5 mr-2" />
                      Accepting Patients
                    </>
                  ) : (
                    <>
                      <XCircle className="h-5 w-5 mr-2" />
                      Not Accepting Patients
                    </>
                  )}
                </span>
              </div>
            </div>

            {/* Contact Actions */}
            <div className="lg:ml-8 mt-6 lg:mt-0">
              <div className="bg-blue-50 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Contact Information</h3>
                
                {provider.phone && (
                  <div className="flex items-center mb-3">
                    <Phone className="h-5 w-5 text-blue-600 mr-3" />
                    <span className="text-gray-700">{provider.phone}</span>
                  </div>
                )}

                {provider.email && (
                  <div className="flex items-center mb-3">
                    <Mail className="h-5 w-5 text-blue-600 mr-3" />
                    <span className="text-gray-700">{provider.email}</span>
                  </div>
                )}

                {provider.website && (
                  <div className="flex items-center mb-4">
                    <Globe className="h-5 w-5 text-blue-600 mr-3" />
                    <a 
                      href={provider.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      Visit Website
                    </a>
                  </div>
                )}

                <button className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors font-medium">
                  Schedule Appointment
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Information */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Education & Experience */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Education & Experience</h2>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Medical School</h3>
                <div className="flex items-center">
                  <Building className="h-5 w-5 text-gray-500 mr-3" />
                  <div>
                    <p className="text-gray-900 font-medium">{provider.education.medicalSchool}</p>
                    <p className="text-gray-600">Graduated {provider.education.graduationYear}</p>
                  </div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Residency</h3>
                <div className="flex items-center">
                  <Building className="h-5 w-5 text-gray-500 mr-3" />
                  <p className="text-gray-900">{provider.education.residency}</p>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Experience</h3>
                <div className="flex items-center">
                  <Calendar className="h-5 w-5 text-gray-500 mr-3" />
                  <p className="text-gray-900">{provider.yearsExperience} years of clinical practice</p>
                </div>
              </div>
            </div>
          </div>

          {/* Languages & Insurance */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Languages & Insurance</h2>
            
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Languages Spoken</h3>
                <div className="flex flex-wrap gap-2">
                  {provider.languages.map((language, index) => (
                    <span
                      key={index}
                      className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm font-medium"
                    >
                      {language}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Insurance Accepted</h3>
                <div className="flex flex-wrap gap-2">
                  {provider.insurance.map((ins, index) => (
                    <span
                      key={index}
                      className="bg-green-100 text-green-800 px-3 py-1 rounded-full text-sm font-medium"
                    >
                      {ins}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Additional Information */}
        <div className="mt-8 bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Additional Information</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">NPI Number</h3>
              <p className="text-gray-600 font-mono">{provider.npi}</p>
            </div>
            
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Specialty</h3>
              <p className="text-gray-600">{provider.specialty}</p>
            </div>
          </div>
        </div>

        {/* Call to Action */}
        <div className="mt-8 bg-blue-600 rounded-lg p-8 text-center">
          <h2 className="text-2xl font-bold text-white mb-4">Ready to Schedule an Appointment?</h2>
          <p className="text-blue-100 mb-6">
            Contact {provider.name} directly to schedule your appointment or consultation.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            {provider.phone && (
              <a
                href={`tel:${provider.phone}`}
                className="bg-white text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-gray-100 transition-colors"
              >
                Call Now
              </a>
            )}
            {provider.email && (
              <a
                href={`mailto:${provider.email}`}
                className="bg-blue-700 text-white px-8 py-3 rounded-lg font-semibold hover:bg-blue-800 transition-colors"
              >
                Send Email
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DoctorDetailPage;
