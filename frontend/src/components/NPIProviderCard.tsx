import React from 'react';
import { MapPin, Phone, Star, Award, Calendar, Building } from 'lucide-react';
import { NPIProvider } from '../services/api';

interface NPIProviderCardProps {
  provider: NPIProvider;
  onClick?: (provider: NPIProvider) => void;
}

export default function NPIProviderCard({ provider, onClick }: NPIProviderCardProps) {
  const handleClick = () => {
    if (onClick) {
      onClick(provider);
    }
  };

  return (
    <div 
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
      onClick={handleClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Provider Header */}
          <div className="flex items-center mb-3">
            <h2 className="text-xl font-semibold text-gray-900 mr-3">
              {provider.name}
            </h2>
            <div className="flex items-center">
              <Star className="h-5 w-5 text-yellow-400 fill-current" />
              <span className="ml-1 text-gray-600">{provider.rating}</span>
            </div>
            {provider.boardCertified && (
              <div className="ml-3 flex items-center">
                <Award className="h-4 w-4 text-blue-600" />
                <span className="ml-1 text-sm text-blue-600 font-medium">Board Certified</span>
              </div>
            )}
          </div>

          {/* Specialty and Experience */}
          <div className="flex items-center text-gray-600 mb-3">
            <span className="font-medium">{provider.specialty}</span>
            <span className="mx-2">•</span>
            <Calendar className="h-4 w-4 mr-1" />
            <span>{provider.yearsExperience} years experience</span>
          </div>

          {/* Location */}
          <div className="flex items-center text-gray-600 mb-3">
            <MapPin className="h-4 w-4 mr-2" />
            <span>{provider.address}, {provider.city}, {provider.state} {provider.zip}</span>
          </div>

          {/* Contact Info */}
          <div className="flex items-center space-x-6 text-gray-600 mb-4">
            {provider.phone && (
              <div className="flex items-center">
                <Phone className="h-4 w-4 mr-2" />
                <span>{provider.phone}</span>
              </div>
            )}
          </div>

          {/* Additional Info */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-700">Languages:</span>
              <p className="text-gray-600">{provider.languages.join(', ')}</p>
            </div>
            <div>
              <span className="font-medium text-gray-700">Insurance:</span>
              <p className="text-gray-600">{provider.insurance.slice(0, 3).join(', ')}</p>
            </div>
            <div>
              <span className="font-medium text-gray-700">Education:</span>
              <p className="text-gray-600">{provider.education.medicalSchool}</p>
            </div>
          </div>

          {/* Status */}
          <div className="mt-4">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              provider.acceptingPatients 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              {provider.acceptingPatients ? 'Accepting Patients' : 'Not Accepting Patients'}
            </span>
          </div>
        </div>

        {/* Action Button */}
        <div className="ml-6">
          <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors">
            View Details
          </button>
        </div>
      </div>
    </div>
  );
}
