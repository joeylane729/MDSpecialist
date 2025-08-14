import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

interface State {
  name: string;
  code: string;
}

interface City {
  name: string;
  state: string;
}

interface Taxonomy {
  code: string;
  description: string;
}

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [selectedTaxonomy, setSelectedTaxonomy] = useState<string>('');
  const [states, setStates] = useState<State[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [taxonomies, setTaxonomies] = useState<Taxonomy[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Mock data for now - will be replaced with API calls
  useEffect(() => {
    // Mock states
    setStates([
      { name: 'California', code: 'CA' },
      { name: 'New York', code: 'NY' },
      { name: 'Texas', code: 'TX' },
      { name: 'Florida', code: 'FL' },
      { name: 'Illinois', code: 'IL' },
      { name: 'Pennsylvania', code: 'PA' },
      { name: 'Ohio', code: 'OH' },
      { name: 'Georgia', code: 'GA' },
      { name: 'North Carolina', code: 'NC' },
      { name: 'Michigan', code: 'MI' }
    ]);

    // Mock taxonomies
    setTaxonomies([
      { code: '207Q00000X', description: 'Family Medicine' },
      { code: '207R00000X', description: 'Internal Medicine' },
      { code: '207T00000X', description: 'Neurological Surgery' },
      { code: '207U00000X', description: 'Nuclear Medicine' },
      { code: '207V00000X', description: 'Obstetrics & Gynecology' },
      { code: '207W00000X', description: 'Ophthalmology' },
      { code: '207X00000X', description: 'Orthopaedic Surgery' },
      { code: '207Y00000X', description: 'Otolaryngology' },
      { code: '207ZP0102X', description: 'Pediatric Otolaryngology' },
      { code: '208000000X', description: 'Pediatrics' }
    ]);
  }, []);

  // Update cities when state changes
  useEffect(() => {
    if (selectedState) {
      // Mock cities based on state
      const mockCities: { [key: string]: City[] } = {
        'CA': [
          { name: 'Los Angeles', state: 'CA' },
          { name: 'San Francisco', state: 'CA' },
          { name: 'San Diego', state: 'CA' },
          { name: 'Sacramento', state: 'CA' },
          { name: 'San Jose', state: 'CA' }
        ],
        'NY': [
          { name: 'New York City', state: 'NY' },
          { name: 'Buffalo', state: 'NY' },
          { name: 'Rochester', state: 'NY' },
          { name: 'Albany', state: 'NY' },
          { name: 'Syracuse', state: 'NY' }
        ],
        'TX': [
          { name: 'Houston', state: 'TX' },
          { name: 'Dallas', state: 'TX' },
          { name: 'Austin', state: 'TX' },
          { name: 'San Antonio', state: 'TX' },
          { name: 'Fort Worth', state: 'TX' }
        ]
      };
      
      setCities(mockCities[selectedState] || []);
      setSelectedCity(''); // Reset city when state changes
    } else {
      setCities([]);
      setSelectedCity('');
    }
  }, [selectedState]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedState || !selectedCity || !selectedTaxonomy) {
      alert('Please select all fields before searching');
      return;
    }

    setIsLoading(true);
    
    try {
      // For now, navigate to results with mock data
      // Later this will make an API call to search providers
      navigate('/results', {
        state: {
          state: selectedState,
          city: selectedCity,
          taxonomy: selectedTaxonomy,
          searchParams: {
            state: selectedState,
            city: selectedCity,
            taxonomy: selectedTaxonomy
          }
        }
      });
    } catch (error) {
      console.error('Search error:', error);
      alert('An error occurred during search');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-12">
            <h1 className="text-5xl font-bold text-gray-900 mb-4">
              ConciergeMD
            </h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Find the perfect medical specialist for your needs. Search by location and specialty to discover qualified healthcare providers in your area.
            </p>
          </div>

          {/* Search Form */}
          <div className="bg-white rounded-2xl shadow-xl p-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-6 text-center">
              Find Your Specialist
            </h2>
            
            <form onSubmit={handleSearch} className="space-y-6">
              {/* State Selection */}
              <div>
                <label htmlFor="state" className="block text-sm font-medium text-gray-700 mb-2">
                  State *
                </label>
                <select
                  id="state"
                  value={selectedState}
                  onChange={(e) => setSelectedState(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  required
                >
                  <option value="">Select a state</option>
                  {states.map((state) => (
                    <option key={state.code} value={state.code}>
                      {state.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* City Selection */}
              <div>
                <label htmlFor="city" className="block text-sm font-medium text-gray-700 mb-2">
                  City *
                </label>
                <select
                  id="city"
                  value={selectedCity}
                  onChange={(e) => setSelectedCity(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  required
                  disabled={!selectedState}
                >
                  <option value="">Select a city</option>
                  {cities.map((city) => (
                    <option key={`${city.state}-${city.name}`} value={city.name}>
                      {city.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Taxonomy/Specialty Selection */}
              <div>
                <label htmlFor="taxonomy" className="block text-sm font-medium text-gray-700 mb-2">
                  Medical Specialty *
                </label>
                <select
                  id="taxonomy"
                  value={selectedTaxonomy}
                  onChange={(e) => setSelectedTaxonomy(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  required
                >
                  <option value="">Select a specialty</option>
                  {taxonomies.map((taxonomy) => (
                    <option key={taxonomy.code} value={taxonomy.code}>
                      {taxonomy.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search Button */}
              <button
                type="submit"
                disabled={isLoading || !selectedState || !selectedCity || !selectedTaxonomy}
                className="w-full bg-blue-600 text-white py-4 px-6 rounded-lg font-semibold text-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                    Searching...
                  </div>
                ) : (
                  'Search Specialists'
                )}
              </button>
            </form>

            {/* Info Text */}
            <div className="mt-6 text-center text-sm text-gray-500">
              <p>Search through our database of over 9 million healthcare providers</p>
              <p className="mt-1">Find specialists based on location and medical expertise</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;
