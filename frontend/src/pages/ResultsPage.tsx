import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { MapPin, Phone, Mail, Globe, Star, Award, Calendar, Building } from 'lucide-react';
import { NPIProvider } from '../services/api';
import NPIProviderCard from '../components/NPIProviderCard';

interface Provider extends NPIProvider {
  email?: string;
  website?: string;
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
  const [currentPage, setCurrentPage] = useState(1);
  const [providersPerPage, setProvidersPerPage] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterAcceptingPatients, setFilterAcceptingPatients] = useState<boolean | null>(null);
  const [filterBoardCertified, setFilterBoardCertified] = useState<boolean | null>(null);
  const [isBackNavigation, setIsBackNavigation] = useState(false);
  const [isFiltersOpen, setIsFiltersOpen] = useState(false);
  const [rankedProviders, setRankedProviders] = useState<Provider[]>([]);

  // Fisher-Yates shuffle algorithm for random ranking
  const shuffleArray = (array: Provider[]): Provider[] => {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
  };

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
    // Try to get data from location.state first (direct navigation)
    if (location.state?.searchParams && location.state.providers) {
      setSearchParams(location.state.searchParams);
      setProviders(location.state.providers);
      setIsLoading(false);
      setCurrentPage(1);
      
      // Save to localStorage for back navigation
      localStorage.setItem('concierge_search_results', JSON.stringify({
        searchParams: location.state.searchParams,
        providers: location.state.providers,
        filters: {
          searchTerm,
          filterAcceptingPatients,
          filterBoardCertified,
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
        if (parsed.searchParams && parsed.providers && parsed.providers.length > 0) {
          setSearchParams(parsed.searchParams);
          setProviders(parsed.providers);
          
          // Restore filter state if available
          if (parsed.filters) {
            console.log('Restoring filters from localStorage:', parsed.filters);
            setSearchTerm(parsed.filters.searchTerm || '');
            setFilterAcceptingPatients(parsed.filters.filterAcceptingPatients || null);
            setFilterBoardCertified(parsed.filters.filterBoardCertified || null);
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
        taxonomy: '207Q00000X'
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
          setFilterAcceptingPatients(parsed.filters.filterAcceptingPatients || null);
          setFilterBoardCertified(parsed.filters.filterBoardCertified || null);
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
            setFilterAcceptingPatients(parsed.filters.filterAcceptingPatients || null);
            setFilterBoardCertified(parsed.filters.filterBoardCertified || null);
            setCurrentPage(parsed.filters.currentPage || 1);
            setProvidersPerPage(parsed.filters.providersPerPage || 20);
            
            // Log the state after setting
            setTimeout(() => {
              console.log('State after restoration:', {
                searchTerm,
                filterAcceptingPatients,
                filterBoardCertified,
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
      filterAcceptingPatients,
      filterBoardCertified,
      currentPage,
      providersPerPage
    });
  }, [searchTerm, filterAcceptingPatients, filterBoardCertified, currentPage, providersPerPage]);

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
        
        // Accepting patients filter
        if (filterAcceptingPatients !== null && provider.acceptingPatients !== filterAcceptingPatients) {
          return false;
        }
        
        // Board certified filter
        if (filterBoardCertified !== null && provider.boardCertified !== filterBoardCertified) {
          return false;
        }
        
        return true;
      });
      
      // Apply ranking with Theodore priority
      let ranked = filtered;
      
      // Check if any provider is named Theodore
      const theodoreProvider = filtered.find(provider => 
        provider.name.toLowerCase().includes('theodore')
      );
      
      if (theodoreProvider) {
        // Put Theodore first, then shuffle the rest
        const otherProviders = filtered.filter(provider => 
          !provider.name.toLowerCase().includes('theodore')
        );
        const shuffledOthers = shuffleArray(otherProviders);
        ranked = [theodoreProvider, ...shuffledOthers];
      } else {
        // No Theodore found, use random ranking
        ranked = shuffleArray(filtered);
      }
      
      setRankedProviders(ranked);
      setCurrentPage(1); // Reset to first page when filters change
    }
  }, [providers, searchTerm, filterAcceptingPatients, filterBoardCertified]);

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
    setFilterAcceptingPatients(null);
    setFilterBoardCertified(null);
    setCurrentPage(1);
    saveFilterState();
  };

  const saveFilterState = () => {
    console.log('saveFilterState called with current state:', {
      searchTerm,
      filterAcceptingPatients,
      filterBoardCertified,
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
            filterAcceptingPatients,
            filterBoardCertified,
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
        <div className="mb-4">
          <button
            onClick={() => navigate('/')}
            className="text-gray-900 hover:text-gray-700 mb-2 flex items-center"
          >
            ← Back to Search
          </button>
          
          <div className="text-center mb-4">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
              {getSpecialtyName(searchParams?.taxonomy || '')} Specialists
            </h1>
            <p className="text-xl text-gray-600 font-medium">
              Found {location.state?.totalProviders || providers.length} providers in {searchParams?.city}, {searchParams?.state}
            </p>

          </div>
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
                  placeholder="Search providers..."
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

            {/* Filters Dropdown */}
            <div className="relative filters-dropdown">
              <button
                onClick={() => setIsFiltersOpen(!isFiltersOpen)}
                className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors bg-white/50"
              >
                <svg className="h-4 w-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.414A1 1 0 013 6.707V4z" />
                </svg>
                <span className="text-sm font-medium text-gray-700">Filters</span>
                <svg className={`h-4 w-4 text-gray-600 transition-transform ${isFiltersOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Filters Dropdown Content */}
              {isFiltersOpen && (
                <div className="absolute right-0 top-full mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-10 p-4">
                  <div className="space-y-4">
                    {/* Filter Toggles */}
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900 mb-2">Filters</h3>
                      <div className="space-y-2">
                        <label className="flex items-center space-x-2 cursor-pointer">
                          <input
                            type="checkbox"
                            id="acceptingPatients"
                            checked={filterAcceptingPatients === true}
                            onChange={(e) => {
                              setFilterAcceptingPatients(e.target.checked ? true : null);
                              setCurrentPage(1);
                              saveFilterState();
                            }}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded transition-colors"
                          />
                          <span className="text-sm font-medium text-gray-700">Accepting Patients</span>
                        </label>

                        <label className="flex items-center space-x-2 cursor-pointer">
                          <input
                            type="checkbox"
                            id="boardCertified"
                            checked={filterBoardCertified === true}
                            onChange={(e) => {
                              setFilterBoardCertified(e.target.checked ? true : null);
                              setCurrentPage(1);
                              saveFilterState();
                            }}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded transition-colors"
                          />
                          <span className="text-sm font-medium text-gray-700">Board Certified</span>
                        </label>
                      </div>
                    </div>

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

        {/* Results Count */}
        <div className="mb-3 text-sm text-gray-600">
          Showing {rankedProviders.length} of {providers.length} providers
          {searchTerm && ` matching "${searchTerm}"`}
        </div>

        {/* Results */}
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
                />
              </div>
            );
          })}
        </div>

        {/* Page Size Selector and Pagination */}
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

        {/* Footer Info */}
        <div className="mt-8 text-center text-gray-500">
          <p>Showing {indexOfFirstProvider + 1}-{Math.min(indexOfLastProvider, rankedProviders.length)} of {rankedProviders.length} providers</p>

        </div>
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
