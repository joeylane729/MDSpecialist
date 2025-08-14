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
  const [sortBy, setSortBy] = useState('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [filterAcceptingPatients, setFilterAcceptingPatients] = useState<boolean | null>(null);
  const [filterBoardCertified, setFilterBoardCertified] = useState<boolean | null>(null);
  const [isBackNavigation, setIsBackNavigation] = useState(false);

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
          sortBy,
          sortOrder,
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
            setSortBy(parsed.filters.sortBy || 'name');
            setSortOrder(parsed.filters.sortOrder || 'asc');
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
          setSortBy(parsed.filters.sortBy || 'name');
          setSortOrder(parsed.filters.sortOrder || 'asc');
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
            setSortBy(parsed.filters.sortBy || 'name');
            setSortOrder(parsed.filters.sortOrder || 'asc');
            setFilterAcceptingPatients(parsed.filters.filterAcceptingPatients || null);
            setFilterBoardCertified(parsed.filters.filterBoardCertified || null);
            setCurrentPage(parsed.filters.currentPage || 1);
            setProvidersPerPage(parsed.filters.providersPerPage || 20);
            
            // Log the state after setting
            setTimeout(() => {
              console.log('State after restoration:', {
                searchTerm,
                sortBy,
                sortOrder,
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
      sortBy,
      sortOrder,
      filterAcceptingPatients,
      filterBoardCertified,
      currentPage,
      providersPerPage
    });
  }, [searchTerm, sortBy, sortOrder, filterAcceptingPatients, filterBoardCertified, currentPage, providersPerPage]);

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

  // Filter and sort logic
  const filteredAndSortedProviders = providers
    .filter(provider => {
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
    })
    .sort((a, b) => {
      let aValue: any;
      let bValue: any;
      
      switch (sortBy) {
        case 'name':
          // Extract last name for sorting
          const aLastName = a.name.split(' ').pop()?.toLowerCase() || '';
          const bLastName = b.name.split(' ').pop()?.toLowerCase() || '';
          aValue = aLastName;
          bValue = bLastName;
          break;
        case 'specialty':
          aValue = a.specialty.toLowerCase();
          bValue = b.specialty.toLowerCase();
          break;
        case 'rating':
          aValue = a.rating;
          bValue = b.rating;
          break;
        case 'experience':
          aValue = a.yearsExperience;
          bValue = b.yearsExperience;
          break;
        case 'city':
          aValue = a.city.toLowerCase();
          bValue = b.city.toLowerCase();
          break;
        default:
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
      }
      
      if (sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

  // Pagination logic
  const indexOfLastProvider = currentPage * providersPerPage;
  const indexOfFirstProvider = indexOfLastProvider - providersPerPage;
  const currentProviders = filteredAndSortedProviders.slice(indexOfFirstProvider, indexOfLastProvider);
  const totalPages = Math.ceil(filteredAndSortedProviders.length / providersPerPage);

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
    setSortBy('name');
    setSortOrder('asc');
    setFilterAcceptingPatients(null);
    setFilterBoardCertified(null);
    setCurrentPage(1);
    saveFilterState();
  };

  const saveFilterState = () => {
    console.log('saveFilterState called with current state:', {
      searchTerm,
      sortBy,
      sortOrder,
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
            sortBy,
            sortOrder,
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

  const saveFilterStateWithValue = (newSortOrder?: 'asc' | 'desc') => {
    const sortOrderToSave = newSortOrder || sortOrder;
    console.log('saveFilterStateWithValue called with sortOrder:', sortOrderToSave);
    
    const savedData = localStorage.getItem('concierge_search_results');
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        const updatedData = {
          ...parsed,
          filters: {
            searchTerm,
            sortBy,
            sortOrder: sortOrderToSave,
            filterAcceptingPatients,
            filterBoardCertified,
            currentPage,
            providersPerPage
          }
        };
        localStorage.setItem('concierge_search_results', JSON.stringify(updatedData));
        console.log('Filter state saved successfully with new sortOrder:', sortOrderToSave);
      } catch (error) {
        console.error('Error saving filter state:', error);
      }
    } else {
      console.log('No existing search data to update with filters');
    }
  };

  const saveFilterStateWithSortBy = (newSortBy: string) => {
    console.log('saveFilterStateWithSortBy called with sortBy:', newSortBy);
    
    const savedData = localStorage.getItem('concierge_search_results');
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        const updatedData = {
          ...parsed,
          filters: {
            searchTerm,
            sortBy: newSortBy,
            sortOrder,
            filterAcceptingPatients,
            filterBoardCertified,
            currentPage,
            providersPerPage
          }
        };
        localStorage.setItem('concierge_search_results', JSON.stringify(updatedData));
        console.log('Filter state saved successfully with new sortBy:', newSortBy);
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
              Found {location.state?.totalProviders || providers.length} providers in {searchParams?.city}, {searchParams?.state}
            </p>
          </div>
        </div>

        {/* Search, Sort, and Filter Controls */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Search */}
            <div>
              <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-2">
                Search
              </label>
              <input
                type="text"
                id="search"
                placeholder="Search by name, specialty, or city..."
                value={searchTerm}
                onChange={(e) => {
                  setSearchTerm(e.target.value);
                  setCurrentPage(1);
                  // Save state immediately
                  saveFilterState();
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Sort By */}
            <div>
              <label htmlFor="sortBy" className="block text-sm font-medium text-gray-700 mb-2">
                Sort By
              </label>
              <select
                id="sortBy"
                value={sortBy}
                onChange={(e) => {
                  const newSortBy = e.target.value;
                  setSortBy(newSortBy);
                  setCurrentPage(1);
                  // Save with the new value immediately
                  saveFilterStateWithSortBy(newSortBy);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="name">Last Name</option>
                <option value="specialty">Specialty</option>
                <option value="rating">Rating</option>
                <option value="experience">Experience</option>
                <option value="city">City</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label htmlFor="sortOrder" className="block text-sm font-medium text-gray-700 mb-2">
                Order
              </label>
              <select
                id="sortOrder"
                value={sortOrder}
                onChange={(e) => {
                  const newSortOrder = e.target.value as 'asc' | 'desc';
                  console.log('Sort order changed to:', newSortOrder);
                  setSortOrder(newSortOrder);
                  setCurrentPage(1);
                  // Save with the new value immediately
                  saveFilterStateWithValue(newSortOrder);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="asc">A-Z / Low-High</option>
                <option value="desc">Z-A / High-Low</option>
              </select>
            </div>

            {/* Reset Button */}
            <div className="flex items-end">
              <button
                onClick={resetFilters}
                className="w-full px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
              >
                Reset Filters
              </button>
            </div>
          </div>

          {/* Additional Filters */}
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex flex-wrap gap-4">
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="acceptingPatients"
                  checked={filterAcceptingPatients === true}
                  onChange={(e) => {
                    setFilterAcceptingPatients(e.target.checked ? true : null);
                    setCurrentPage(1);
                    saveFilterState();
                  }}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="acceptingPatients" className="text-sm font-medium text-gray-700">
                  Accepting Patients
                </label>
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="boardCertified"
                  checked={filterBoardCertified === true}
                  onChange={(e) => {
                    setFilterBoardCertified(e.target.checked ? true : null);
                    setCurrentPage(1);
                    saveFilterState();
                  }}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="boardCertified" className="text-sm font-medium text-gray-700">
                  Board Certified
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Results Count */}
        <div className="mb-4 text-sm text-gray-600">
          Showing {filteredAndSortedProviders.length} of {providers.length} providers
          {searchTerm && ` matching "${searchTerm}"`}
        </div>

        {/* Results */}
        <div className="space-y-6">
          {currentProviders.map((provider) => (
            <NPIProviderCard
              key={provider.id}
              provider={provider}
              onClick={handleProviderClick}
            />
          ))}
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
          <p>Showing {indexOfFirstProvider + 1}-{Math.min(indexOfLastProvider, filteredAndSortedProviders.length)} of {filteredAndSortedProviders.length} providers</p>
          <p className="mt-2 text-sm">
            Results are based on your search criteria. Click on any provider to see more details.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage;
