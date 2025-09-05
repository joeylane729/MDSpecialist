import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { NPIProvider, getSpecialistRecommendations, SpecialistRecommendationRequest, searchNPIProviders, rankNPIProviders, NPISearchRequest, NPIRankingRequest } from '../services/api';
import NPIProviderCard from '../components/NPIProviderCard';

interface Provider extends NPIProvider {
  email?: string;
  website?: string;
}

interface SearchParams {
  state: string;
  city: string;
  symptoms: string;
  diagnosis: string;
  determined_specialty?: string;
  predicted_icd10?: string;
  icd10_description?: string;
  differential_diagnoses?: Array<{
    code: string;
    description: string;
  }>;
  treatment_options?: Array<{
    name: string;
    outcomes: string;
    complications: string;
  }>;
  searchOptions?: {
    diagnosis: boolean;
    specialists: boolean;
  };
}

interface TreatmentOption {
  name: string;
  outcomes: string;
  complications: string;
}

// Function to get treatment options from GPT-generated data
const getTreatmentOptions = (searchParams: any, aiRecommendations?: any): TreatmentOption[] | null => {
  // Use GPT-generated treatment options if available from searchParams
  if (searchParams.treatment_options && Array.isArray(searchParams.treatment_options) && searchParams.treatment_options.length > 0) {
    return searchParams.treatment_options.map((option: any) => ({
      name: option.name || "Treatment Option",
      outcomes: option.outcomes || "Outcomes not specified",
      complications: option.complications || "Complications not specified"
    }));
  }

  // Fallback to AI recommendations if searchParams doesn't have treatment options
  if (aiRecommendations?.patient_profile?.treatment_options && Array.isArray(aiRecommendations.patient_profile.treatment_options) && aiRecommendations.patient_profile.treatment_options.length > 0) {
    return aiRecommendations.patient_profile.treatment_options.map((option: any) => ({
      name: option.name || "Treatment Option",
      outcomes: option.outcomes || "Outcomes not specified",
      complications: option.complications || "Complications not specified"
    }));
  }

  // Return null if no treatment options found
  return null;
};

const ResultsPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchParams, setSearchParams] = useState<SearchParams | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [providersPerPage, setProvidersPerPage] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTreatmentOptions, setSelectedTreatmentOptions] = useState<string[]>([]);
  const [isBackNavigation, setIsBackNavigation] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [rankedProviders, setRankedProviders] = useState<Provider[]>([]);
  const [providerLinks, setProviderLinks] = useState<{ [doctorName: string]: string }>({});
  const [activeView, setActiveView] = useState<'assessment' | 'specialists' | 'ai-recommendations'>('assessment');
  
  // Set initial view based on search options
  useEffect(() => {
    if (searchParams?.searchOptions) {
      if (searchParams.searchOptions.specialists) {
        setActiveView('specialists');
      } else if (searchParams.searchOptions.diagnosis) {
        setActiveView('assessment');
      } else {
        setActiveView('ai-recommendations');
      }
    }
  }, [searchParams?.searchOptions]);
  
  // Debug logging
  useEffect(() => {
    console.log('ResultsPage - location.state:', location.state);
    console.log('ResultsPage - aiRecommendations:', location.state?.aiRecommendations);
    if (location.state?.aiRecommendations) {
      console.log('ResultsPage - patient_profile:', location.state.aiRecommendations.patient_profile);
      console.log('ResultsPage - recommendations:', location.state.aiRecommendations.recommendations);
      
      // Debug treatment options specifically
      if (location.state.aiRecommendations.patient_profile?.treatment_options) {
        console.log('🔍 DEBUG: ResultsPage found treatment_options in aiRecommendations:', location.state.aiRecommendations.patient_profile.treatment_options);
      } else {
        console.log('🔍 DEBUG: ResultsPage - No treatment_options in aiRecommendations patient_profile');
      }
    }
    if (location.state?.providers) {
      console.log('ResultsPage - providers received:', location.state.providers.length);
      console.log('ResultsPage - first 5 provider NPIs:', location.state.providers.slice(0, 5).map((p: Provider) => p.npi));
    }
    
    // Debug searchParams treatment options
    if (searchParams?.treatment_options) {
      console.log('🔍 DEBUG: ResultsPage found treatment_options in searchParams:', searchParams.treatment_options);
    } else {
      console.log('🔍 DEBUG: ResultsPage - No treatment_options in searchParams');
      console.log('🔍 DEBUG: searchParams keys:', searchParams ? Object.keys(searchParams) : 'searchParams is null');
    }
  }, [location.state, searchParams]);



  // Convert rank to letter grade (F to A+)
  const getLetterGrade = (rank: number, totalResults: number): string => {
    if (totalResults === 0) return 'F';
    
    const percentage = (rank / totalResults) * 100;
    
    if (percentage <= 10) return 'A+';
    if (percentage <= 20) return 'A';
    if (percentage <= 30) return 'A-';
    if (percentage <= 40) return 'B+';
    if (percentage <= 50) return 'B';
    if (percentage <= 60) return 'B-';
    if (percentage <= 70) return 'C+';
    if (percentage <= 80) return 'C';
    if (percentage <= 85) return 'C-';
    if (percentage <= 90) return 'D+';
    if (percentage <= 95) return 'D';
    return 'F';
  };



  // Close filters dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Element;
      if (isFiltersOpen && !target.closest('.filters-dropdown')) {
        setIsFiltersOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isFiltersOpen]);

  useEffect(() => {
    // Scroll to top when component mounts or location.state changes
    window.scrollTo(0, 0);
    
    // Try to get data from location.state first (direct navigation)
    if (location.state?.searchParams && location.state.providers) {
      setSearchParams(location.state.searchParams);
      setProviders(location.state.providers);
      setRankedProviders(location.state.providers); // Set the ranked providers
      const links = location.state.providerLinks || {};
      console.log('DEBUG: Setting provider links:', links);
      console.log('DEBUG: Provider names:', location.state.providers.slice(0, 5).map((p: Provider) => p.name));
      setProviderLinks(links); // Set the provider links
      setIsLoading(false);
      setCurrentPage(1);
      
      // Save to localStorage for back navigation
      localStorage.setItem('concierge_search_results', JSON.stringify({
        searchParams: location.state.searchParams,
        providers: location.state.providers,
        filters: {
          searchTerm,
          currentPage,
          providersPerPage
        }
      }));
      return;
    }
    
    // Try to get data from localStorage (back navigation)
    const savedSearchData = localStorage.getItem('concierge_search_results');
    if (savedSearchData) {
      try {
        const parsed = JSON.parse(savedSearchData);
        console.log('🔍 DEBUG: Loading from localStorage - parsed data:', parsed);
        console.log('🔍 DEBUG: Loading from localStorage - searchParams:', parsed.searchParams);
        console.log('🔍 DEBUG: Loading from localStorage - treatment_options:', parsed.searchParams?.treatment_options);
        if (parsed.searchParams && parsed.providers && parsed.providers.length > 0) {
          setSearchParams(parsed.searchParams);
          setProviders(parsed.providers);
          
          // Restore filter state if available
          if (parsed.filters) {
            console.log('Restoring filters from localStorage:', parsed.filters);
            setSearchTerm(parsed.filters.searchTerm || '');
            setCurrentPage(parsed.filters.currentPage || 1);
            setProvidersPerPage(parsed.filters.providersPerPage || 20);
          } else {
            setCurrentPage(1);
          }
          
          setIsLoading(false);
          return;
        }
      } catch (error) {
        console.error('Error parsing saved search data:', error);
      }
    }
    
    // If no saved data, check if we have searchParams but need to regenerate providers
    if (location.state?.searchParams) {
      setSearchParams(location.state.searchParams);
      // Only generate mock data if we don't have real providers
      if (!location.state.providers || location.state.providers.length === 0) {
        generateMockProviders(location.state.searchParams);
      }
      setCurrentPage(1);
    } else {
      // Last resort: fallback mock data
      generateMockProviders({
        state: 'CA',
        city: 'Los Angeles',
        symptoms: 'Fever, cough',
        diagnosis: 'A000',
        determined_specialty: 'Neurological Surgery'  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
      });
      setCurrentPage(1);
    }
  }, [location.state]);

  // Separate useEffect to restore filter state from localStorage on component mount
  useEffect(() => {
    console.log('Component mount useEffect running...');
    const savedSearchData = localStorage.getItem('concierge_search_results');
    if (savedSearchData) {
      try {
        const parsed = JSON.parse(savedSearchData);
        console.log('Found saved data on mount:', parsed);
        if (parsed.filters && !location.state?.providers) {
          console.log('Restoring filters on mount:', parsed.filters);
          // Only restore filters if we don't have fresh data from navigation
          setSearchTerm(parsed.filters.searchTerm || '');
          setCurrentPage(parsed.filters.currentPage || 1);
          setProvidersPerPage(parsed.filters.providersPerPage || 20);
        }
      } catch (error) {
        console.error('Error parsing saved filter data:', error);
      }
    } else {
      console.log('No saved data found on mount');
    }
  }, []); // Empty dependency array - runs only on mount

  // Additional useEffect to handle back navigation and restore filters
  useEffect(() => {
    // If we have providers but no fresh location.state, we're likely coming from back navigation
    if (providers.length > 0 && !location.state?.providers && !isBackNavigation) {
      console.log('Detected back navigation, restoring filters...');
      setIsBackNavigation(true);
      const savedSearchData = localStorage.getItem('concierge_search_results');
      if (savedSearchData) {
        try {
          const parsed = JSON.parse(savedSearchData);
          if (parsed.filters) {
            console.log('Restoring filters on back navigation:', parsed.filters);
            setSearchTerm(parsed.filters.searchTerm || '');
            setCurrentPage(parsed.filters.currentPage || 1);
            setProvidersPerPage(parsed.filters.providersPerPage || 20);
            
            // Log the state after setting
            setTimeout(() => {
              console.log('State after restoration:', {
                searchTerm,
                currentPage,
                providersPerPage
              });
            }, 100);
          }
        } catch (error) {
          console.error('Error parsing saved filter data on back navigation:', error);
        }
      }
    }
  }, [providers, location.state, isBackNavigation]);

  // Debug useEffect to monitor filter state changes
  useEffect(() => {
    console.log('Filter state changed:', {
      searchTerm,
      currentPage,
      providersPerPage
    });
  }, [searchTerm, currentPage, providersPerPage]);

  // Effect to update ranked providers when filters change
  useEffect(() => {
    if (providers.length > 0) {
      const filtered = providers.filter(provider => {
        // Search filter
        if (searchTerm && !provider.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
            !provider.specialty.toLowerCase().includes(searchTerm.toLowerCase()) &&
            !provider.city.toLowerCase().includes(searchTerm.toLowerCase())) {
          return false;
        }
        
        
        return true;
      });
      
      // Use the providers as they are (already ranked from backend)
      // Don't apply random shuffle - use the ranking from Pinecone
      setRankedProviders(filtered);
      setCurrentPage(1); // Reset to first page when filters change
    }
  }, [providers, searchTerm]);

  const generateMockProviders = (params: SearchParams) => {
    setIsLoading(true);
    
    // Simulate API call delay
    setTimeout(() => {
      const mockProviders: Provider[] = [
        {
          id: '1',
          npi: '1234567890',
          name: 'Dr. Sarah Johnson',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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

  // Pagination logic
  const indexOfLastProvider = currentPage * providersPerPage;
  const indexOfFirstProvider = indexOfLastProvider - providersPerPage;
  const currentProviders = rankedProviders.slice(indexOfFirstProvider, indexOfLastProvider);
  const totalPages = Math.ceil(rankedProviders.length / providersPerPage);

  const handlePageChange = (pageNumber: number) => {
    setCurrentPage(pageNumber);
    // Scroll to top when page changes
    window.scrollTo({ top: 0, behavior: 'smooth' });
    saveFilterState();
  };

  const handleShowSpecialists = async () => {
    // If specialists are already available, just switch to the view
    if (searchParams?.searchOptions?.specialists && rankedProviders.length > 0) {
      setActiveView('specialists');
      return;
    }

    // If specialists haven't been generated yet, call the APIs
    try {
      setIsLoading(true);
      
      // Step 1: Get specialist recommendations
      const specialistRequest: SpecialistRecommendationRequest = {
        symptoms: searchParams?.symptoms || '',
        diagnosis: searchParams?.diagnosis || '',
        medical_history: location.state?.medicalHistory || '',
        medications: location.state?.medications || '',
        surgical_history: location.state?.surgicalHistory || '',
        files: []
      };

      const specialistResponse = await getSpecialistRecommendations(specialistRequest);
      
      // Step 2: Search for NPI providers
      const npiSearchRequest: NPISearchRequest = {
        state: searchParams?.state || '',
        city: searchParams?.city || '',
        zipCode: location.state?.zipCode || '',
        proximity: location.state?.proximity || 'statewide',
        diagnosis: searchParams?.diagnosis || '',
        symptoms: searchParams?.symptoms || '',
        uploadedFiles: [],
        limit: 10000  // Increase limit to get all available providers
      };

      const npiData = await searchNPIProviders(npiSearchRequest);
      
      // Step 3: Rank NPI providers using specialist information
      const rankingRequest: NPIRankingRequest = {
        npi_providers: npiData.providers,
        patient_input: `Symptoms: ${searchParams?.symptoms}\nDiagnosis: ${searchParams?.diagnosis}`,
        shared_specialist_information: specialistResponse.shared_specialist_information || []
      };

      const rankingResponse = await rankNPIProviders(rankingRequest);
      
      // Reorder providers based on ranking
      const rankedNPIs = rankingResponse.ranked_npis;
      let rankedNPIProviders: NPIProvider[] = [];
      if (Array.isArray(rankedNPIs)) {
        rankedNPIProviders = rankedNPIs.map(npi => 
          npiData.providers.find(provider => provider.npi === npi)
        ).filter((provider): provider is NPIProvider => provider !== undefined);
      }
      
      // Update state with ranked providers
      setRankedProviders(rankedNPIProviders);
      setProviderLinks(rankingResponse.provider_links || {});
      
      // Update the search params to include specialists
      // This will trigger the useEffect to switch to specialists view
      setSearchParams(prev => ({
        ...prev!,
        searchOptions: {
          ...prev!.searchOptions!,
          specialists: true
        }
      }));
      
    } catch (error) {
      console.error('Error fetching specialist recommendations:', error);
      // You might want to show an error message to the user here
    } finally {
      setIsLoading(false);
    }
  };

  const goToPreviousPage = () => {
    if (currentPage > 1) {
      handlePageChange(currentPage - 1);
    }
  };

  const goToNextPage = () => {
    if (currentPage < totalPages) {
      handlePageChange(currentPage + 1);
    }
  };

  const resetFilters = () => {
    setSearchTerm('');
    setSelectedTreatmentOptions([]);
    setCurrentPage(1);
    saveFilterState();
  };

  const saveFilterState = () => {
    console.log('saveFilterState called with current state:', {
      searchTerm,
      currentPage,
      providersPerPage
    });
    
    const savedData = localStorage.getItem('concierge_search_results');
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        const updatedData = {
          ...parsed,
          filters: {
            searchTerm,
            currentPage,
            providersPerPage
          }
        };
        localStorage.setItem('concierge_search_results', JSON.stringify(updatedData));
        console.log('Filter state saved successfully');
      } catch (error) {
        console.error('Error saving filter state:', error);
      }
    } else {
      console.log('No existing search data to update with filters');
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 flex items-center justify-center overflow-hidden">
        {/* Background decorative elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-blue-400/20 to-purple-400/20 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-tr from-indigo-400/20 to-blue-400/20 rounded-full blur-3xl"></div>
        </div>
        
        <div className="relative z-10 text-center max-w-lg mx-auto px-6">
          {/* Animated loading spinner */}
          <div className="mb-8">
            <div className="animate-spin rounded-full h-20 w-20 border-4 border-blue-200 border-t-blue-600 mx-auto"></div>
          </div>
          
          {/* Main heading */}
          <h2 className="text-3xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-6">
            Finding specialists in your area...
          </h2>
          
          {/* Sleek info card */}
          <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-white/20 p-6 mb-6">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div className="flex-1">
                <p className="text-gray-700 text-sm leading-relaxed">
                  <span className="font-semibold text-gray-900">Please wait...</span> This process may take 1-2 minutes as we analyze thousands of specialists and match them to your specific needs.
                </p>
              </div>
            </div>
          </div>
          
          {/* Important notice */}
          <div className="flex items-center justify-center space-x-2 text-gray-600">
            <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="text-sm font-medium">Please do not close this browser tab while we search</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 pb-8">
        {/* Header */}
        {/* Secondary Header Bar */}
        <div className="flex justify-between items-center mb-4 py-4 border-b border-gray-200">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/')}
              className="text-gray-900 hover:text-gray-700 flex items-center"
            >
              ← Back to Search
            </button>
            

          </div>
          
          {/* View Toggle */}
          <div className="flex space-x-8">
            {searchParams?.searchOptions?.diagnosis && (
              <button
                onClick={() => setActiveView('assessment')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'assessment'
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
                <span>Medical Assessment</span>
              </button>
            )}
            {searchParams?.searchOptions?.specialists && (
              <button
                onClick={() => setActiveView('specialists')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'specialists'
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <i className="fas fa-user-md h-4 w-4"></i>
                <span>Specialists</span>
              </button>
            )}
            <button
              onClick={() => setActiveView('ai-recommendations')}
              className={`hidden flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeView === 'ai-recommendations'
                  ? 'text-primary-600 bg-primary-50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span>AI Recommendations</span>
            </button>
          </div>
        </div>



                {/* Medical Assessment */}
        {activeView === 'assessment' && searchParams?.searchOptions?.diagnosis && (searchParams?.predicted_icd10 || location.state?.aiRecommendations?.patient_profile?.predicted_icd10) && (
          <>
            {/* Medical Assessment Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                Medical Assessment
              </h1>
              <button
                onClick={handleShowSpecialists}
                disabled={isLoading}
                className="inline-flex items-center gap-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 rounded-lg font-semibold text-lg hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    Generating specialists...
                  </>
                ) : (
                  <>
                    Show me suggested specialists
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </>
                )}
              </button>
            </div>
            
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Diagnosis */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h2 className="text-2xl font-semibold text-gray-900 mb-4">Diagnosis</h2>
              
              {/* Primary Diagnosis */}
              <div className="mb-4 pb-4 border-b border-gray-100">
                <h3 className="text-base font-medium text-gray-900 mb-3">Primary</h3>
                <div className="p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    <i className="fas fa-star text-gray-700 text-sm"></i>
                    <span className="font-mono text-sm text-gray-900 font-medium">{searchParams.predicted_icd10 || location.state?.aiRecommendations?.patient_profile?.predicted_icd10}</span>
                    <span className="text-gray-500">-</span>
                    <p className="text-gray-700 text-sm">{searchParams.icd10_description || location.state?.aiRecommendations?.patient_profile?.icd10_description || 'Description not available'}</p>
                  </div>
                </div>
              </div>

              {/* Differential Diagnosis */}
              <div>
                <h3 className="text-base font-medium text-gray-900 mb-3">Differential</h3>
                <div className="space-y-2">
                  {(searchParams.differential_diagnoses || location.state?.aiRecommendations?.patient_profile?.differential_diagnoses) && ((searchParams.differential_diagnoses?.length || 0) > 0 || (location.state?.aiRecommendations?.patient_profile?.differential_diagnoses?.length || 0) > 0) ? (
                    (searchParams.differential_diagnoses || location.state?.aiRecommendations?.patient_profile?.differential_diagnoses || []).map((diagnosis: any, index: number) => (
                      <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                        <span className="text-sm text-gray-700 font-bold">{index + 1}.</span>
                        <span className="font-mono text-sm text-gray-900 font-medium">{diagnosis.code}</span>
                        <span className="text-gray-500">-</span>
                        <span className="text-gray-700 text-sm">{diagnosis.description || 'Description not available'}</span>
                      </div>
                    ))
                  ) : (
                    <div className="text-gray-500 text-sm italic">No differential diagnoses available</div>
                  )}
                </div>
              </div>
            </div>

            {/* Treatment Options with Outcomes and Complications */}
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Treatment Options</h2>
              {(() => {
                const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
                if (treatmentOptions && treatmentOptions.length > 0) {
                  return (
                    <div className="space-y-3">
                      {treatmentOptions.map((treatment, index) => (
                        <div key={index} className="p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-start gap-3">
                            <span className="text-sm text-gray-700 font-bold">{index + 1}.</span>
                            <div className="flex-1">
                              <h4 className="font-medium text-gray-900 text-sm mb-2">{treatment.name}</h4>
                              <div className="grid grid-cols-2 gap-4 text-xs text-gray-600">
                                <div><span className="font-medium">Outcomes:</span> {treatment.outcomes}</div>
                                <div><span className="font-medium">Complications:</span> {treatment.complications}</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                } else {
                  return (
                    <div className="text-center py-8">
                      <div className="text-gray-500 mb-2">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <p className="text-gray-500 text-sm">No treatment options were generated for this case.</p>
                      <p className="text-gray-400 text-xs mt-1">Please consult with a healthcare provider for personalized treatment recommendations.</p>
                    </div>
                  );
                }
              })()}
            </div>
          </div>
        </>
        )}

        {/* Specialists Section */}
        {activeView === 'specialists' && searchParams?.searchOptions?.specialists && (
          <>
            {/* Specialists Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                {searchParams?.determined_specialty ? `${searchParams.determined_specialty} Specialists` : 'Specialists'}
              </h1>
              

        </div>

        {/* Search and Filter Controls */}
        <div className="py-2 mb-3">
          <div className="flex items-center gap-3 justify-center">
            {/* Search */}
            <div className="flex-1 max-w-md">
              <div className="relative">
                <input
                  type="text"
                  id="search"
                      placeholder="Search specialists..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1);
                    saveFilterState();
                  }}
                  className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 bg-white/50"
                />
                <svg className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
            </div>

            {/* Compare Outcomes Button */}
            <button
              onClick={() => {
                // TODO: Implement compare outcomes functionality
                console.log('Compare outcomes clicked');
              }}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 bg-white/50 border border-gray-300 rounded-lg hover:bg-gray-50 hover:text-gray-800 transition-colors"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Compare Outcomes
            </button>

            {/* Filters Dropdown */}
            <div className="relative filters-dropdown">
              <button
                onClick={() => setIsFiltersOpen(!isFiltersOpen)}
                className={`flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50 transition-colors bg-white/50 ${
                  selectedTreatmentOptions.length > 0
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-300'
                }`}
              >
                <svg className="h-4 w-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.414A1 1 0 013 6.707V4z" />
                </svg>
                <span className="text-sm font-medium text-gray-700">Filters</span>
                {selectedTreatmentOptions.length > 0 && (
                  <span className="bg-blue-500 text-white text-xs px-2 py-0.5 rounded-full">
                    {selectedTreatmentOptions.length}
                  </span>
                )}
                <svg className={`h-4 w-4 text-gray-600 transition-transform ${isFiltersOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Filters Dropdown Content */}
              {isFiltersOpen && (
                <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-10 p-4">
                  <div className="space-y-4">
                    {/* Treatment Options Filter */}
                    {(() => {
                      const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
                      if (treatmentOptions && treatmentOptions.length > 0) {
                        return (
                          <div>
                            <h3 className="text-sm font-semibold text-gray-900 mb-2">Treatment Options</h3>
                            <div className="space-y-2 max-h-48 overflow-y-auto">
                              {treatmentOptions.map((option, index) => (
                                <label key={index} className="flex items-start space-x-2 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={selectedTreatmentOptions.includes(option.name)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setSelectedTreatmentOptions(prev => [...prev, option.name]);
                                      } else {
                                        setSelectedTreatmentOptions(prev => prev.filter(name => name !== option.name));
                                      }
                                      setCurrentPage(1);
                                      saveFilterState();
                                    }}
                                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded transition-colors mt-0.5"
                                  />
                                  <div className="flex-1">
                                    <span className="text-sm font-medium text-gray-700">{option.name}</span>
                                  </div>
                                </label>
                              ))}
                            </div>
                          </div>
                        );
                      }
                      return null;
                    })()}

                    {/* Reset Button */}
                    <div className="pt-2 border-t border-gray-200">
                      <button
                        onClick={() => {
                          resetFilters();
                          setIsFiltersOpen(false);
                        }}
                        className="w-full px-3 py-2 text-gray-600 hover:text-gray-800 transition-colors font-medium text-sm"
                      >
                        Reset All Filters
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
          </>
        )}

        {/* Results Count */}
        {activeView === 'specialists' && (
        <div className="mb-3 text-sm text-gray-600">
          Showing {rankedProviders.length} of {providers.length} providers
          {searchTerm && ` matching "${searchTerm}"`}
          {selectedTreatmentOptions.length > 0 && (
            <span className="ml-2">
              with treatment options: {selectedTreatmentOptions.join(', ')}
            </span>
          )}
        </div>
        )}

        {/* Results */}
        {activeView === 'specialists' && (
        <div className="space-y-6">
          {currentProviders.map((provider, index) => {
            const rank = indexOfFirstProvider + index + 1;
            const grade = getLetterGrade(rank, rankedProviders.length);
            const isTopResult = rank === 1;
            
            return (
              <div key={provider.id} className="relative">
                {/* Top result indicator */}
                {isTopResult && (
                  <div className="absolute -right-2 -top-2 bg-gradient-to-r from-yellow-400 to-yellow-600 text-white px-3 py-1 rounded-full text-xs font-bold shadow-lg z-10 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                    BEST
                  </div>
                )}
                
                <NPIProviderCard
                  provider={provider}
                  onClick={handleProviderClick}
                  isHighlighted={isTopResult}
                  grade={grade}
                  pineconeLink={(() => {
                    const linkData = providerLinks[provider.name?.toUpperCase()];
                    console.log(`DEBUG: Looking for link for provider "${provider.name}" (uppercase: "${provider.name?.toUpperCase()}") - found:`, linkData);
                    console.log('DEBUG: Available provider links:', providerLinks);
                    return linkData;
                  })()}
                />
              </div>
            );
          })}
        </div>
        )}

        {/* Page Size Selector and Pagination */}
        {activeView === 'specialists' && (
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-between space-y-4 sm:space-y-0">
          {/* Page Size Selector */}
          <div className="flex items-center space-x-2">
            <label htmlFor="pageSize" className="text-sm font-medium text-gray-700">
              Show:
            </label>
            <select
              id="pageSize"
              value={providersPerPage}
              onChange={(e) => {
                setProvidersPerPage(Number(e.target.value));
                setCurrentPage(1); // Reset to first page when changing page size
                saveFilterState();
              }}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <span className="text-sm text-gray-600">per page</span>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <nav className="flex items-center space-x-2" aria-label="Pagination">
              {/* Previous Button */}
              <button
                onClick={goToPreviousPage}
                disabled={currentPage === 1}
                className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>

              {/* Page Numbers */}
              <div className="flex items-center space-x-1">
                {Array.from({ length: totalPages }, (_, index) => {
                  const pageNumber = index + 1;
                  // Show first page, last page, current page, and pages around current page
                  if (
                    pageNumber === 1 ||
                    pageNumber === totalPages ||
                    (pageNumber >= currentPage - 2 && pageNumber <= currentPage + 2)
                  ) {
                    return (
                      <button
                        key={pageNumber}
                        onClick={() => handlePageChange(pageNumber)}
                        className={`px-3 py-2 text-sm font-medium rounded-md ${
                          currentPage === pageNumber
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-500 bg-white border border-gray-300 hover:bg-gray-50'
                        }`}
                      >
                        {pageNumber}
                      </button>
                    );
                  } else if (
                    pageNumber === currentPage - 3 ||
                    pageNumber === currentPage + 3
                  ) {
                    return <span key={pageNumber} className="px-2 text-gray-500">...</span>;
                  }
                  return null;
                })}
              </div>

              {/* Next Button */}
              <button
                onClick={goToNextPage}
                disabled={currentPage === totalPages}
                className="px-3 py-2 text-sm font-medium text-gray-500 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </nav>
          )}
        </div>
        )}

        {/* Footer Info */}
        {activeView === 'specialists' && (
          <div className="mt-8 text-center text-gray-500">
            <p>Showing {indexOfFirstProvider + 1}-{Math.min(indexOfLastProvider, rankedProviders.length)} of {rankedProviders.length} providers</p>
          </div>
        )}

        {/* AI Recommendations Section */}
        {activeView === 'ai-recommendations' && (
          <>
            {/* AI Recommendations Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-purple-800 to-pink-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                AI-Powered Specialist Recommendations
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Based on your symptoms and diagnosis, our AI has analyzed medical content to recommend relevant specialists
              </p>
            </div>

            {/* Debug Info */}
            {!location.state?.aiRecommendations && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <h3 className="text-red-800 font-semibold">Debug: No AI Recommendations Data</h3>
                <p className="text-red-700">location.state: {JSON.stringify(location.state, null, 2)}</p>
              </div>
            )}

            {location.state?.aiRecommendations && !location.state.aiRecommendations.recommendations && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <h3 className="text-yellow-800 font-semibold">Debug: No Recommendations Array</h3>
                <p className="text-yellow-700">aiRecommendations: {JSON.stringify(location.state.aiRecommendations, null, 2)}</p>
              </div>
            )}

            {/* AI Recommendations Content */}
            {location.state?.aiRecommendations ? (
              <div className="space-y-6">
                {/* Patient Profile Summary */}
                <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-200">
                  <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    Patient Profile Analysis
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-medium text-gray-700 mb-2">Symptoms Identified:</h4>
                      <div className="flex flex-wrap gap-2">
                        {location.state.aiRecommendations.patient_profile.symptoms.map((symptom: string, index: number) => (
                          <span key={index} className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm">
                            {symptom}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-700 mb-2">Specialties Needed:</h4>
                      <div className="flex flex-wrap gap-2">
                        {location.state.aiRecommendations.patient_profile.specialties_needed.map((specialty: string, index: number) => (
                          <span key={index} className="bg-pink-100 text-pink-800 px-3 py-1 rounded-full text-sm">
                            {specialty}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-purple-600">{location.state.aiRecommendations.recommendations.length}</div>
                    <div className="text-sm text-gray-600">Specialists Recommended</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-pink-600">{location.state.aiRecommendations.total_candidates_found}</div>
                    <div className="text-sm text-gray-600">Medical Records Analyzed</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-indigo-600">{Math.round(location.state.aiRecommendations.processing_time_ms / 1000)}s</div>
                    <div className="text-sm text-gray-600">Processing Time</div>
                  </div>
                </div>

                {/* Specialist Recommendations */}
                <div className="space-y-4">
                  <h3 className="text-2xl font-semibold text-gray-800 mb-4">Recommended Specialists</h3>
                  
                  {location.state.aiRecommendations.recommendations && location.state.aiRecommendations.recommendations.length > 0 ? (
                    location.state.aiRecommendations.recommendations.map((recommendation: any, index: number) => (
                    <div key={index} className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h4 className="text-xl font-semibold text-gray-800 mb-2">{recommendation.name}</h4>
                          <p className="text-gray-600 mb-2">{recommendation.specialty}</p>
                          <p className="text-sm text-gray-500 mb-3">{recommendation.reasoning}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-purple-600">
                            {Math.round(recommendation.confidence_score * 100)}%
                          </div>
                          <div className="text-sm text-gray-500">Confidence</div>
                        </div>
                      </div>
                      
                      {/* Source Information */}
                      {recommendation.metadata && (
                        <div className="bg-gray-50 rounded-lg p-4">
                          <h5 className="font-medium text-gray-700 mb-2">Source Information:</h5>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div>
                              <span className="font-medium">Content:</span> {recommendation.metadata.title}
                            </div>
                            <div>
                              <span className="font-medium">Author:</span> {recommendation.metadata.author}
                            </div>
                            <div>
                              <span className="font-medium">Date:</span> {recommendation.metadata.date}
                            </div>
                            <div>
                              <span className="font-medium">Duration:</span> {recommendation.metadata.duration}
                            </div>
                          </div>
                          {recommendation.metadata.link && (
                            <div className="mt-3">
                              <a 
                                href={recommendation.metadata.link} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-purple-600 hover:text-purple-800 text-sm font-medium"
                              >
                                View Source Content →
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                  ) : (
                    <div className="text-center py-12">
                      <div className="text-gray-400 text-6xl mb-4">📋</div>
                      <h3 className="text-xl font-semibold text-gray-700 mb-2">No Specialist Recommendations Found</h3>
                      <p className="text-gray-500">The AI analysis did not find specific specialist recommendations for your condition.</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <div className="text-gray-400 text-6xl mb-4">🤖</div>
                <h3 className="text-xl font-semibold text-gray-700 mb-2">No AI Recommendations Available</h3>
                <p className="text-gray-500">AI recommendations were not generated for this search.</p>
              </div>
            )}
          </>
        )}
        
        {/* Bottom Button - Only show in assessment view */}
        {activeView === 'assessment' && (
          <div className="text-center mt-8 mb-6">
            <button
              onClick={handleShowSpecialists}
              disabled={isLoading}
              className="inline-flex items-center gap-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 rounded-lg font-semibold text-lg hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  Generating specialists...
                </>
              ) : (
                <>
                  Show me suggested specialists
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                </>
              )}
            </button>
          </div>
        )}
      </div>
      
      <style>{`
        /* Custom select styling */
        select {
          appearance: none;
          -webkit-appearance: none;
          -moz-appearance: none;
          background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6,9 12,15 18,9'%3e%3c/polyline%3e%3c/svg%3e");
          background-repeat: no-repeat;
          background-position: right 0.75rem center;
          background-size: 0.875em;
          padding-right: 2rem !important;
        }
      `}</style>
    </div>
  );
};

export default ResultsPage;
