import React, { useState } from 'react';
import { MapPin, Phone, Star, Award, Calendar, Building } from 'lucide-react';
import { NPIProvider } from '../services/api';
import SchedulingModal from './SchedulingModal';

interface NPIProviderCardProps {
  provider: NPIProvider;
  onClick?: (provider: NPIProvider) => void;
  isHighlighted?: boolean;
  grade?: string;
}

export default function NPIProviderCard({ provider, onClick, isHighlighted = false, grade }: NPIProviderCardProps) {
  const [isSchedulingModalOpen, setIsSchedulingModalOpen] = useState(false);

  const handleClick = () => {
    if (onClick) {
      onClick(provider);
    }
  };

  const openSchedulingModal = () => {
    setIsSchedulingModalOpen(true);
  };

  // Get grade color based on letter grade
  const getGradeColor = (grade: string): string => {
    if (grade.startsWith('A')) return 'bg-gradient-to-r from-emerald-500 to-green-600';
    if (grade.startsWith('B')) return 'bg-gradient-to-r from-blue-500 to-indigo-600';
    if (grade.startsWith('C')) return 'bg-gradient-to-r from-amber-500 to-orange-500';
    if (grade.startsWith('D')) return 'bg-gradient-to-r from-orange-500 to-red-500';
    return 'bg-gradient-to-r from-red-500 to-pink-600';
  };

  return (
    <>
      <div 
        className={`rounded-lg shadow-sm border p-6 hover:shadow-md transition-all cursor-pointer ${
          isHighlighted 
            ? 'bg-white border-2 border-yellow-400 shadow-lg' 
            : 'bg-white border border-gray-200'
        }`}
        onClick={handleClick}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            {/* Provider Header */}
            <div className="flex items-center mb-3">
              <h2 className="text-xl font-semibold text-gray-900 mr-3">
                {provider.name}
              </h2>
              {grade && (
                <div className={`inline-flex items-center justify-center w-8 h-8 ${getGradeColor(grade)} text-white text-sm font-bold rounded-lg shadow-sm`}>
                  {grade}
                </div>
              )}
              <div className="ml-3 flex items-center">
                <Award className="h-4 w-4 text-gray-400" />
                <span className="ml-1 text-sm text-gray-500 font-medium">Board Certified</span>
              </div>
            </div>

            {/* Specialty and Experience */}
            <div className="flex items-center text-gray-600 mb-3">
              <span className="font-medium">{provider.specialty}</span>
              <span className="mx-2">•</span>
              <Calendar className="h-4 w-4 mr-1" />
              <span>-- years of experience</span>
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
            <div className="mt-4">
              <span className="font-medium text-gray-700">Education:</span>
              <p className="text-gray-600 mt-1">--</p>
            </div>

            {/* Status */}
            <div className="mt-4">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                Accepting Patients
              </span>
            </div>
          </div>

          {/* Action Button */}
          <div className="ml-6">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                openSchedulingModal();
              }}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Schedule Appointment
            </button>
          </div>
        </div>
      </div>

      {/* Scheduling Modal */}
      <SchedulingModal
        isOpen={isSchedulingModalOpen}
        onClose={() => setIsSchedulingModalOpen(false)}
        provider={provider}
      />
    </>
  );
}
