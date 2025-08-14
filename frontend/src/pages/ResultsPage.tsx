import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MapPin, Phone, Mail, Globe, Star, Award, Calendar, Building } from 'lucide-react';

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

interface SearchParams {
  state: string;
  city: string;
  taxonomy: string;
}

const ResultsPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchParams, setSearchParams] = useState<SearchParams | null>(null);

  useEffect(() => {
    if (location.state?.searchParams) {
      setSearchParams(location.state.searchParams);
      // Generate mock data based on search criteria
      generateMockProviders(location.state.searchParams);
    } else {
      // Fallback mock data
      generateMockProviders({
        state: 'CA',
        city: 'Los Angeles',
        taxonomy: '207Q00000X'
      });
    }
  }, [location.state]);

  const generateMockProviders = (params: SearchParams) => {
    setIsLoading(true);
    
    // Simulate API call delay
    setTimeout(() => {
      const mockProviders: Provider[] = [
        {
          id: '1',
          npi: '1234567890',
          name: 'Dr. Sarah Johnson',
          specialty: 'Family Medicine',
          address: '123 Medical Center Dr',
          city: params.city,
          state: params.state,
          zip: '90210',
          phone: '(555) 123-4567',
          email: 'sarah.johnson@healthcare.com',
          website: 'https://drjohnson.com',
          rating: 4.8,
          yearsExperience: 15,
          boardCertified: true,
          acceptingPatients: true,
          languages: ['English', 'Spanish'],
          insurance: ['Blue Cross', 'Aetna', 'Cigna'],
          education: {
            medicalSchool: 'Stanford University School of Medicine',
            graduationYear: 2008,
            residency: 'UCLA Medical Center'
          }
        },
        {
          id: '2',
          npi: '2345678901',
          name: 'Dr. Michael Chen',
          specialty: 'Family Medicine',
          address: '456 Health Plaza',
          city: params.city,
          state: params.state,
          zip: '90211',
          phone: '(555) 234-5678',
          email: 'mchen@familycare.com',
          website: 'https://drchen.com',
          rating: 4.6,
          yearsExperience: 12,
          boardCertified: true,
          acceptingPatients: true,
          languages: ['English', 'Mandarin'],
          insurance: ['Blue Cross', 'Kaiser', 'UnitedHealth'],
          education: {
            medicalSchool: 'UC San Francisco School of Medicine',
            graduationYear: 2011,
            residency: 'Cedars-Sinai Medical Center'
          }
        },
        {
          id: '3',
          npi: '3456789012',
          name: 'Dr. Emily Rodriguez',
          specialty: 'Family Medicine',
          address: '789 Wellness Way',
          city: params.city,
          state: params.state,
          zip: '90212',
          phone: '(555) 345-6789',
          email: 'erodriguez@wellness.com',
          website: 'https://drrodriguez.com',
          rating: 4.9,
          yearsExperience: 18,
          boardCertified: true,
          acceptingPatients: false,
          languages: ['English', 'Spanish', 'Portuguese'],
          insurance: ['Blue Cross', 'Aetna', 'Humana'],
          education: {
            medicalSchool: 'Harvard Medical School',
            graduationYear: 2005,
            residency: 'Johns Hopkins Hospital'
          }
        },
        {
          id: '4',
          npi: '4567890123',
          name: 'Dr. David Kim',
          specialty: 'Family Medicine',
          address: '321 Care Circle',
          city: params.city,
          state: params.state,
          zip: '90213',
          phone: '(555) 456-7890',
          email: 'dkim@carecircle.com',
          website: 'https://drkim.com',
          rating: 4.7,
          yearsExperience: 10,
          boardCertified: true,
          acceptingPatients: true,
          languages: ['English', 'Korean'],
          insurance: ['Blue Cross', 'Cigna', 'Anthem'],
          education: {
            medicalSchool: 'UCLA David Geffen School of Medicine',
            graduationYear: 2013,
            residency: 'UCLA Medical Center'
          }
        },
        {
          id: '5',
          npi: '5678901234',
          name: 'Dr. Lisa Thompson',
          specialty: 'Family Medicine',
          address: '654 Medical Blvd',
          city: params.city,
          state: params.state,
          zip: '90214',
          phone: '(555) 567-8901',
          email: 'lthompson@medical.com',
          website: 'https://drthompson.com',
          rating: 4.5,
          yearsExperience: 14,
          boardCertified: true,
          acceptingPatients: true,
          languages: ['English'],
          insurance: ['Blue Cross', 'Aetna', 'UnitedHealth'],
          education: {
            medicalSchool: 'UC Davis School of Medicine',
            graduationYear: 2009,
            residency: 'UC Davis Medical Center'
          }
        }
      ];
      
      setProviders(mockProviders);
      setIsLoading(false);
    }, 1000);
  };

  const handleProviderClick = (provider: Provider) => {
    navigate(`/doctor/${provider.id}`, { state: { provider } });
  };

  const getSpecialtyName = (taxonomyCode: string) => {
    const specialtyMap: { [key: string]: string } = {
      '207Q00000X': 'Family Medicine',
      '207R00000X': 'Internal Medicine',
      '207T00000X': 'Neurological Surgery',
      '207U00000X': 'Nuclear Medicine',
      '207V00000X': 'Obstetrics & Gynecology',
      '207W00000X': 'Ophthalmology',
      '207X00000X': 'Orthopaedic Surgery',
      '207Y00000X': 'Otolaryngology',
      '207ZP0102X': 'Pediatric Otolaryngology',
      '208000000X': 'Pediatrics'
    };
    return specialtyMap[taxonomyCode] || 'Medical Specialist';
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-xl text-gray-600">Finding specialists in your area...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/')}
            className="text-blue-600 hover:text-blue-800 mb-4 flex items-center"
          >
            ← Back to Search
          </button>
          
          <div className="bg-white rounded-lg p-6 shadow-sm">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {getSpecialtyName(searchParams?.taxonomy || '')} Specialists
            </h1>
            <p className="text-lg text-gray-600">
              Found {providers.length} providers in {searchParams?.city}, {searchParams?.state}
            </p>
          </div>
        </div>

        {/* Results */}
        <div className="space-y-6">
          {providers.map((provider) => (
            <div
              key={provider.id}
              onClick={() => handleProviderClick(provider)}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow cursor-pointer"
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
                    {provider.email && (
                      <div className="flex items-center">
                        <Mail className="h-4 w-4 mr-2" />
                        <span>{provider.email}</span>
                      </div>
                    )}
                    {provider.website && (
                      <div className="flex items-center">
                        <Globe className="h-4 w-4 mr-2" />
                        <span className="text-blue-600 hover:underline">{provider.website}</span>
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
          ))}
        </div>

        {/* Footer Info */}
        <div className="mt-12 text-center text-gray-500">
          <p>Showing {providers.length} of {providers.length} providers</p>
          <p className="mt-2 text-sm">
            Results are based on your search criteria. Click on any provider to see more details.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;
