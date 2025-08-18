import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchNPIProviders } from '../services/api';
import { 
  MapPin, 
  Stethoscope, 
  Search, 
  Users, 
  Shield, 
  Clock, 
  Star,
  Building2,
  Heart,
  Zap,
  ArrowRight,
  CheckCircle,
  FileText,
  Upload,
  X
} from 'lucide-react';

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
  const [diagnosis, setDiagnosis] = useState<string>('');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [states, setStates] = useState<State[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [taxonomies, setTaxonomies] = useState<Taxonomy[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [patientType, setPatientType] = useState<string>('');
  const [proximity, setProximity] = useState<string>('');

  // Debug logging
  useEffect(() => {
    console.log('HomePage mounted - checking viewport width:', window.innerWidth);
    console.log('Document body width:', document.body.offsetWidth);
    console.log('Document body style:', document.body.style.cssText);
    console.log('Document html style:', document.documentElement.style.cssText);
    
    // Check for parent elements that might have margins/padding
    const root = document.getElementById('root');
    if (root) {
      console.log('Root element:', root);
      console.log('Root computed style:', window.getComputedStyle(root));
    }
    
    const app = document.querySelector('.App');
    if (app) {
      console.log('App element:', app);
      console.log('App computed style:', window.getComputedStyle(app));
    }
  }, []);

  // Mock data for now - will be replaced with API calls
  useEffect(() => {
    // All 50 US states in alphabetical order
    setStates([
      { name: 'Alabama', code: 'AL' },
      { name: 'Alaska', code: 'AK' },
      { name: 'Arizona', code: 'AZ' },
      { name: 'Arkansas', code: 'AR' },
      { name: 'California', code: 'CA' },
      { name: 'Colorado', code: 'CO' },
      { name: 'Connecticut', code: 'CT' },
      { name: 'Delaware', code: 'DE' },
      { name: 'Florida', code: 'FL' },
      { name: 'Georgia', code: 'GA' },
      { name: 'Hawaii', code: 'HI' },
      { name: 'Idaho', code: 'ID' },
      { name: 'Illinois', code: 'IL' },
      { name: 'Indiana', code: 'IN' },
      { name: 'Iowa', code: 'IA' },
      { name: 'Kansas', code: 'KS' },
      { name: 'Kentucky', code: 'KY' },
      { name: 'Louisiana', code: 'LA' },
      { name: 'Maine', code: 'ME' },
      { name: 'Maryland', code: 'MD' },
      { name: 'Massachusetts', code: 'MA' },
      { name: 'Michigan', code: 'MI' },
      { name: 'Minnesota', code: 'MN' },
      { name: 'Mississippi', code: 'MS' },
      { name: 'Missouri', code: 'MO' },
      { name: 'Montana', code: 'MT' },
      { name: 'Nebraska', code: 'NE' },
      { name: 'Nevada', code: 'NV' },
      { name: 'New Hampshire', code: 'NH' },
      { name: 'New Jersey', code: 'NJ' },
      { name: 'New Mexico', code: 'NM' },
      { name: 'New York', code: 'NY' },
      { name: 'North Carolina', code: 'NC' },
      { name: 'North Dakota', code: 'ND' },
      { name: 'Ohio', code: 'OH' },
      { name: 'Oklahoma', code: 'OK' },
      { name: 'Oregon', code: 'OR' },
      { name: 'Pennsylvania', code: 'PA' },
      { name: 'Rhode Island', code: 'RI' },
      { name: 'South Carolina', code: 'SC' },
      { name: 'South Dakota', code: 'SD' },
      { name: 'Tennessee', code: 'TN' },
      { name: 'Texas', code: 'TX' },
      { name: 'Utah', code: 'UT' },
      { name: 'Vermont', code: 'VT' },
      { name: 'Virginia', code: 'VA' },
      { name: 'Washington', code: 'WA' },
      { name: 'West Virginia', code: 'WV' },
      { name: 'Wisconsin', code: 'WI' },
      { name: 'Wyoming', code: 'WY' }
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
      // Major cities for all 50 states
      const mockCities: { [key: string]: City[] } = {
        'AL': [
          { name: 'Birmingham', state: 'AL' },
          { name: 'Montgomery', state: 'AL' },
          { name: 'Huntsville', state: 'AL' },
          { name: 'Mobile', state: 'AL' },
          { name: 'Tuscaloosa', state: 'AL' }
        ],
        'AK': [
          { name: 'Anchorage', state: 'AK' },
          { name: 'Fairbanks', state: 'AK' },
          { name: 'Juneau', state: 'AK' },
          { name: 'Sitka', state: 'AK' },
          { name: 'Ketchikan', state: 'AK' }
        ],
        'AZ': [
          { name: 'Phoenix', state: 'AZ' },
          { name: 'Tucson', state: 'AZ' },
          { name: 'Mesa', state: 'AZ' },
          { name: 'Scottsdale', state: 'AZ' },
          { name: 'Glendale', state: 'AZ' }
        ],
        'AR': [
          { name: 'Little Rock', state: 'AR' },
          { name: 'Fort Smith', state: 'AR' },
          { name: 'Fayetteville', state: 'AR' },
          { name: 'Springdale', state: 'AR' },
          { name: 'Jonesboro', state: 'AR' }
        ],
        'CA': [
          { name: 'Los Angeles', state: 'CA' },
          { name: 'San Francisco', state: 'CA' },
          { name: 'San Diego', state: 'CA' },
          { name: 'Sacramento', state: 'CA' },
          { name: 'San Jose', state: 'CA' },
          { name: 'Oakland', state: 'CA' },
          { name: 'Fresno', state: 'CA' },
          { name: 'Long Beach', state: 'CA' }
        ],
        'CO': [
          { name: 'Denver', state: 'CO' },
          { name: 'Colorado Springs', state: 'CO' },
          { name: 'Aurora', state: 'CO' },
          { name: 'Fort Collins', state: 'CO' },
          { name: 'Boulder', state: 'CO' }
        ],
        'CT': [
          { name: 'Bridgeport', state: 'CT' },
          { name: 'New Haven', state: 'CT' },
          { name: 'Hartford', state: 'CT' },
          { name: 'Stamford', state: 'CT' },
          { name: 'Waterbury', state: 'CT' }
        ],
        'DE': [
          { name: 'Wilmington', state: 'DE' },
          { name: 'Dover', state: 'DE' },
          { name: 'Newark', state: 'DE' },
          { name: 'Middletown', state: 'DE' },
          { name: 'Smyrna', state: 'DE' }
        ],
        'FL': [
          { name: 'Miami', state: 'FL' },
          { name: 'Orlando', state: 'FL' },
          { name: 'Tampa', state: 'FL' },
          { name: 'Jacksonville', state: 'FL' },
          { name: 'Fort Lauderdale', state: 'FL' },
          { name: 'Tallahassee', state: 'FL' }
        ],
        'GA': [
          { name: 'Atlanta', state: 'GA' },
          { name: 'Savannah', state: 'GA' },
          { name: 'Athens', state: 'GA' },
          { name: 'Augusta', state: 'GA' },
          { name: 'Columbus', state: 'GA' }
        ],
        'HI': [
          { name: 'Honolulu', state: 'HI' },
          { name: 'Hilo', state: 'HI' },
          { name: 'Kailua', state: 'HI' },
          { name: 'Kapolei', state: 'HI' },
          { name: 'Kaneohe', state: 'HI' }
        ],
        'ID': [
          { name: 'Boise', state: 'ID' },
          { name: 'Meridian', state: 'ID' },
          { name: 'Nampa', state: 'ID' },
          { name: 'Idaho Falls', state: 'ID' },
          { name: 'Pocatello', state: 'ID' }
        ],
        'IL': [
          { name: 'Chicago', state: 'IL' },
          { name: 'Springfield', state: 'IL' },
          { name: 'Peoria', state: 'IL' },
          { name: 'Rockford', state: 'IL' },
          { name: 'Naperville', state: 'IL' }
        ],
        'IN': [
          { name: 'Indianapolis', state: 'IN' },
          { name: 'Fort Wayne', state: 'IN' },
          { name: 'Evansville', state: 'IN' },
          { name: 'South Bend', state: 'IN' },
          { name: 'Carmel', state: 'IN' }
        ],
        'IA': [
          { name: 'Des Moines', state: 'IA' },
          { name: 'Cedar Rapids', state: 'IA' },
          { name: 'Davenport', state: 'IA' },
          { name: 'Sioux City', state: 'IA' },
          { name: 'Iowa City', state: 'IA' }
        ],
        'KS': [
          { name: 'Wichita', state: 'KS' },
          { name: 'Kansas City', state: 'KS' },
          { name: 'Overland Park', state: 'KS' },
          { name: 'Topeka', state: 'KS' },
          { name: 'Lawrence', state: 'KS' }
        ],
        'KY': [
          { name: 'Louisville', state: 'KY' },
          { name: 'Lexington', state: 'KY' },
          { name: 'Bowling Green', state: 'KY' },
          { name: 'Owensboro', state: 'KY' },
          { name: 'Covington', state: 'KY' }
        ],
        'LA': [
          { name: 'New Orleans', state: 'LA' },
          { name: 'Baton Rouge', state: 'LA' },
          { name: 'Shreveport', state: 'LA' },
          { name: 'Lafayette', state: 'LA' },
          { name: 'Lake Charles', state: 'LA' }
        ],
        'ME': [
          { name: 'Portland', state: 'ME' },
          { name: 'Lewiston', state: 'ME' },
          { name: 'Bangor', state: 'ME' },
          { name: 'Auburn', state: 'ME' },
          { name: 'Biddeford', state: 'ME' }
        ],
        'MD': [
          { name: 'Baltimore', state: 'MD' },
          { name: 'Annapolis', state: 'MD' },
          { name: 'Frederick', state: 'MD' },
          { name: 'Rockville', state: 'MD' },
          { name: 'Gaithersburg', state: 'MD' }
        ],
        'MA': [
          { name: 'Boston', state: 'MA' },
          { name: 'Worcester', state: 'MA' },
          { name: 'Springfield', state: 'MA' },
          { name: 'Cambridge', state: 'MA' },
          { name: 'Lowell', state: 'MA' }
        ],
        'MI': [
          { name: 'Detroit', state: 'MI' },
          { name: 'Grand Rapids', state: 'MI' },
          { name: 'Warren', state: 'MI' },
          { name: 'Sterling Heights', state: 'MI' },
          { name: 'Lansing', state: 'MI' }
        ],
        'MN': [
          { name: 'Minneapolis', state: 'MN' },
          { name: 'Saint Paul', state: 'MN' },
          { name: 'Rochester', state: 'MN' },
          { name: 'Duluth', state: 'MN' },
          { name: 'Bloomington', state: 'MN' }
        ],
        'MS': [
          { name: 'Jackson', state: 'MS' },
          { name: 'Gulfport', state: 'MS' },
          { name: 'Southaven', state: 'MS' },
          { name: 'Hattiesburg', state: 'MS' },
          { name: 'Biloxi', state: 'MS' }
        ],
        'MO': [
          { name: 'Kansas City', state: 'MO' },
          { name: 'St. Louis', state: 'MO' },
          { name: 'Springfield', state: 'MO' },
          { name: 'Columbia', state: 'MO' },
          { name: 'Independence', state: 'MO' }
        ],
        'MT': [
          { name: 'Billings', state: 'MT' },
          { name: 'Missoula', state: 'MT' },
          { name: 'Great Falls', state: 'MT' },
          { name: 'Bozeman', state: 'MT' },
          { name: 'Helena', state: 'MT' }
        ],
        'NE': [
          { name: 'Omaha', state: 'NE' },
          { name: 'Lincoln', state: 'NE' },
          { name: 'Bellevue', state: 'NE' },
          { name: 'Grand Island', state: 'NE' },
          { name: 'Kearney', state: 'NE' }
        ],
        'NV': [
          { name: 'Las Vegas', state: 'NV' },
          { name: 'Reno', state: 'NV' },
          { name: 'Henderson', state: 'NV' },
          { name: 'Carson City', state: 'NV' },
          { name: 'Sparks', state: 'NV' }
        ],
        'NH': [
          { name: 'Manchester', state: 'NH' },
          { name: 'Nashua', state: 'NH' },
          { name: 'Concord', state: 'NH' },
          { name: 'Dover', state: 'NH' },
          { name: 'Rochester', state: 'NH' }
        ],
        'NJ': [
          { name: 'Newark', state: 'NJ' },
          { name: 'Jersey City', state: 'NJ' },
          { name: 'Paterson', state: 'NJ' },
          { name: 'Elizabeth', state: 'NJ' },
          { name: 'Trenton', state: 'NJ' }
        ],
        'NM': [
          { name: 'Albuquerque', state: 'NM' },
          { name: 'Las Cruces', state: 'NM' },
          { name: 'Santa Fe', state: 'NM' },
          { name: 'Rio Rancho', state: 'NM' },
          { name: 'Roswell', state: 'NM' }
        ],
        'NY': [
          { name: 'New York', state: 'NY' },
          { name: 'Buffalo', state: 'NY' },
          { name: 'Rochester', state: 'NY' },
          { name: 'Albany', state: 'NY' },
          { name: 'Syracuse', state: 'NY' },
          { name: 'Yonkers', state: 'NY' }
        ],
        'NC': [
          { name: 'Charlotte', state: 'NC' },
          { name: 'Raleigh', state: 'NC' },
          { name: 'Greensboro', state: 'NC' },
          { name: 'Durham', state: 'NC' },
          { name: 'Winston-Salem', state: 'NC' }
        ],
        'ND': [
          { name: 'Fargo', state: 'ND' },
          { name: 'Bismarck', state: 'ND' },
          { name: 'Grand Forks', state: 'ND' },
          { name: 'Minot', state: 'ND' },
          { name: 'West Fargo', state: 'ND' }
        ],
        'OH': [
          { name: 'Columbus', state: 'OH' },
          { name: 'Cleveland', state: 'OH' },
          { name: 'Cincinnati', state: 'OH' },
          { name: 'Toledo', state: 'OH' },
          { name: 'Akron', state: 'OH' }
        ],
        'OK': [
          { name: 'Oklahoma City', state: 'OK' },
          { name: 'Tulsa', state: 'OK' },
          { name: 'Norman', state: 'OK' },
          { name: 'Broken Arrow', state: 'OK' },
          { name: 'Lawton', state: 'OK' }
        ],
        'OR': [
          { name: 'Portland', state: 'OR' },
          { name: 'Salem', state: 'OR' },
          { name: 'Eugene', state: 'OR' },
          { name: 'Gresham', state: 'OR' },
          { name: 'Hillsboro', state: 'OR' }
        ],
        'PA': [
          { name: 'Philadelphia', state: 'PA' },
          { name: 'Pittsburgh', state: 'PA' },
          { name: 'Allentown', state: 'PA' },
          { name: 'Erie', state: 'PA' },
          { name: 'Reading', state: 'PA' }
        ],
        'RI': [
          { name: 'Providence', state: 'RI' },
          { name: 'Warwick', state: 'RI' },
          { name: 'Cranston', state: 'RI' },
          { name: 'Pawtucket', state: 'RI' },
          { name: 'East Providence', state: 'RI' }
        ],
        'SC': [
          { name: 'Columbia', state: 'SC' },
          { name: 'Charleston', state: 'SC' },
          { name: 'Greenville', state: 'SC' },
          { name: 'Myrtle Beach', state: 'SC' },
          { name: 'Rock Hill', state: 'SC' }
        ],
        'SD': [
          { name: 'Sioux Falls', state: 'SD' },
          { name: 'Rapid City', state: 'SD' },
          { name: 'Aberdeen', state: 'SD' },
          { name: 'Brookings', state: 'SD' },
          { name: 'Watertown', state: 'SD' }
        ],
        'TN': [
          { name: 'Nashville', state: 'TN' },
          { name: 'Memphis', state: 'TN' },
          { name: 'Knoxville', state: 'TN' },
          { name: 'Chattanooga', state: 'TN' },
          { name: 'Clarksville', state: 'TN' }
        ],
        'TX': [
          { name: 'Houston', state: 'TX' },
          { name: 'Dallas', state: 'TX' },
          { name: 'Austin', state: 'TX' },
          { name: 'San Antonio', state: 'TX' },
          { name: 'Fort Worth', state: 'TX' },
          { name: 'El Paso', state: 'TX' }
        ],
        'UT': [
          { name: 'Salt Lake City', state: 'UT' },
          { name: 'West Valley City', state: 'UT' },
          { name: 'Provo', state: 'UT' },
          { name: 'West Jordan', state: 'UT' },
          { name: 'Orem', state: 'UT' }
        ],
        'VT': [
          { name: 'Burlington', state: 'VT' },
          { name: 'Montpelier', state: 'VT' },
          { name: 'Rutland', state: 'VT' },
          { name: 'Barre', state: 'VT' },
          { name: 'St. Albans', state: 'VT' }
        ],
        'VA': [
          { name: 'Virginia Beach', state: 'VA' },
          { name: 'Richmond', state: 'VA' },
          { name: 'Arlington', state: 'VA' },
          { name: 'Norfolk', state: 'VA' },
          { name: 'Alexandria', state: 'VA' }
        ],
        'WA': [
          { name: 'Seattle', state: 'WA' },
          { name: 'Spokane', state: 'WA' },
          { name: 'Tacoma', state: 'WA' },
          { name: 'Vancouver', state: 'WA' },
          { name: 'Bellevue', state: 'WA' }
        ],
        'WV': [
          { name: 'Charleston', state: 'WV' },
          { name: 'Huntington', state: 'WV' },
          { name: 'Morgantown', state: 'WV' },
          { name: 'Parkersburg', state: 'WV' },
          { name: 'Wheeling', state: 'WV' }
        ],
        'WI': [
          { name: 'Milwaukee', state: 'WI' },
          { name: 'Madison', state: 'WI' },
          { name: 'Green Bay', state: 'WI' },
          { name: 'Kenosha', state: 'WI' },
          { name: 'Racine', state: 'WI' }
        ],
        'WY': [
          { name: 'Cheyenne', state: 'WY' },
          { name: 'Casper', state: 'WY' },
          { name: 'Laramie', state: 'WY' },
          { name: 'Gillette', state: 'WY' },
          { name: 'Rock Springs', state: 'WY' }
        ]
      };
      
      setCities(mockCities[selectedState] || []);
      setSelectedCity(''); // Reset city when state changes
    } else {
      setCities([]);
      setSelectedCity('');
    }
  }, [selectedState]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setUploadedFiles(prev => [...prev, ...files]);
  };

  const removeFile = (index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!selectedState || !selectedCity || !selectedTaxonomy || !diagnosis.trim() || !patientType || !proximity) {
      alert('Please fill in all required fields before searching');
      return;
    }

    setIsLoading(true);
    
    // Clear any previous search results
    localStorage.removeItem('concierge_search_results');
    
    try {
      // Call the backend API to search for providers using the service
      const data = await searchNPIProviders({
        state: selectedState,
        city: selectedCity,
        taxonomy: selectedTaxonomy,
        limit: 500
      });
      
      // Save search results to localStorage for persistence
      localStorage.setItem('concierge_search_results', JSON.stringify({
        searchParams: {
          state: selectedState,
          city: selectedCity,
          taxonomy: selectedTaxonomy
        },
        providers: data.providers,
        totalProviders: data.total_providers
      }));

      // Navigate to results page with the real data
      navigate('/results', {
        state: {
          state: selectedState,
          city: selectedCity,
          taxonomy: selectedTaxonomy,
          searchParams: {
            state: selectedState,
            city: selectedCity,
            taxonomy: selectedTaxonomy
          },
          providers: data.providers,
          totalProviders: data.total_providers
        }
      });
    } catch (error) {
      console.error('Search error:', error);
      alert(`Search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 relative overflow-hidden w-full">
      {/* Background decorative elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-gradient-to-br from-blue-400/20 to-purple-400/20 rounded-full blur-3xl"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-gradient-to-tr from-indigo-400/20 to-blue-400/20 rounded-full blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-gradient-to-r from-purple-400/10 to-pink-400/10 rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10 w-full px-4 pt-8">
        <div className="max-w-6xl mx-auto">
          {/* Search Form */}
          <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-2 leading-tight py-2">
                ConciergeMD
              </h1>
              <p className="text-lg text-gray-700 max-w-2xl mx-auto leading-relaxed mb-2">
                Find the <span className="font-semibold text-blue-600">best subspecialist</span> for your specific diagnosis.
              </p>
            </div>
            
            <form onSubmit={handleSearch} className="space-y-6">
              {/* 2x2 Grid for Selectors */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Patient Type Selection */}
                <div className="group h-full flex flex-col justify-end">
                  <label className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    <Users className="w-4 h-4 mr-2 text-blue-600" />
                    Patient Type *
                  </label>
                  <div className="w-full h-full px-4 py-4 border-2 border-gray-200 rounded-xl focus-within:ring-4 focus-within:ring-blue-100 focus-within:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300 flex items-center gap-6">
                    <label className="inline-flex items-center cursor-pointer">
                      <input
                        type="radio"
                        name="patientType"
                        value="adult"
                        checked={patientType === 'adult'}
                        onChange={() => setPatientType('adult')}
                        className="form-radio h-5 w-5 text-blue-600"
                        required
                      />
                      <span className="ml-2 text-base text-gray-800">Adult</span>
                    </label>
                    <label className="inline-flex items-center cursor-pointer">
                      <input
                        type="radio"
                        name="patientType"
                        value="pediatric"
                        checked={patientType === 'pediatric'}
                        onChange={() => setPatientType('pediatric')}
                        className="form-radio h-5 w-5 text-blue-600"
                        required
                      />
                      <span className="ml-2 text-base text-gray-800">Pediatric</span>
                    </label>
                  </div>
                </div>
                {/* State Selection */}
                <div className="group">
                  <label htmlFor="state" className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    <MapPin className="w-4 h-4 mr-2 text-blue-600" />
                    State *
                  </label>
                  <select
                    id="state"
                    value={selectedState}
                    onChange={(e) => setSelectedState(e.target.value)}
                    className="w-full px-4 py-4 pr-8 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300"
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
                <div className="group">
                  <label htmlFor="city" className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    <MapPin className="w-4 h-4 mr-2 text-blue-600" />
                    City *
                  </label>
                  <select
                    id="city"
                    value={selectedCity}
                    onChange={(e) => setSelectedCity(e.target.value)}
                    className="w-full px-4 py-4 pr-8 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300 disabled:opacity-50"
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
                {/* Proximity Selection */}
                <div className="group">
                  <label htmlFor="proximity" className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    Proximity *
                  </label>
                  <select
                    id="proximity"
                    value={proximity}
                    onChange={(e) => setProximity(e.target.value)}
                    className="w-full px-4 py-4 pr-8 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300"
                    required
                  >
                    <option value="">Select proximity</option>
                    <option value="50">Within 50 miles</option>
                    <option value="100">Within 100 miles</option>
                    <option value="state">State-wide</option>
                    <option value="us">US-wide</option>
                    <option value="world">Worldwide</option>
                  </select>
                </div>
              </div>

              {/* Row 2: Diagnosis and Upload */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6 mt-2">
                {/* Diagnosis Input */}
                <div className="group md:col-span-2 flex flex-col pr-0 md:pr-2">
                  <label htmlFor="diagnosis" className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    <FileText className="w-4 h-4 mr-2 text-blue-600" />
                    Diagnosis Description *
                  </label>
                  <textarea
                    id="diagnosis"
                    value={diagnosis}
                    onChange={(e) => setDiagnosis(e.target.value)}
                    placeholder="Please provide a detailed description of your diagnosis, symptoms, and any relevant medical history..."
                    className="w-full px-4 py-4 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300 resize-none flex-1"
                    rows={4}
                    required
                  />
                </div>
                {/* File Upload */}
                <div className="group md:col-span-2 flex flex-col">
                  <label className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                    <Upload className="w-4 h-4 mr-2 text-blue-600" />
                    Upload Medical Documents
                  </label>
                  <div className="border-2 border-dashed border-gray-300 rounded-xl p-3 text-center hover:border-blue-400 transition-colors flex-1 flex flex-col justify-center">
                    <input
                      type="file"
                      multiple
                      accept=".pdf"
                      onChange={handleFileUpload}
                      className="hidden"
                      id="file-upload"
                    />
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-gray-600 mb-1">Click to upload PDF files</p>
                      <p className="text-sm text-gray-500">
                        Imaging reports, doctors notes, biopsy pathology reports, relevant blood tests...
                      </p>
                    </label>
                  </div>
                  
                  {/* Uploaded Files List */}
                  {uploadedFiles.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="text-sm font-medium text-gray-700">Uploaded Files:</p>
                      {uploadedFiles.map((file, index) => (
                        <div key={index} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                          <div className="flex items-center space-x-2">
                            <FileText className="w-4 h-4 text-gray-500" />
                            <span className="text-sm text-gray-700">{file.name}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Row 3: Medical Subspecialty */}
              <div className="group mb-6">
                <label htmlFor="taxonomy" className="block text-sm font-semibold text-gray-700 mb-3 flex items-center">
                  <Stethoscope className="w-4 h-4 mr-2 text-blue-600" />
                  Medical Subspecialty *
                </label>
                <select
                  id="taxonomy"
                  value={selectedTaxonomy}
                  onChange={(e) => setSelectedTaxonomy(e.target.value)}
                  className="w-full px-4 py-4 pr-8 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white/50 backdrop-blur-sm group-hover:border-blue-300"
                  required
                >
                  <option value="">Select a subspecialty</option>
                  {taxonomies.map((taxonomy) => (
                    <option key={taxonomy.code} value={taxonomy.code}>
                      {taxonomy.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Search Button */}
              <div className="text-center">
                <button
                  type="submit"
                  disabled={isLoading || !selectedState || !selectedCity || !selectedTaxonomy || !diagnosis.trim() || !patientType || !proximity}
                  className="group relative inline-flex items-center justify-center w-full max-w-md bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-1"
                >
                  {isLoading ? (
                    <div className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                      <span>Searching...</span>
                    </div>
                  ) : (
                    <>
                      <Zap className="w-6 h-6 mr-3" />
                      <span>Find Specialists</span>
                      <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
                    </>
                  )}
                </button>
              </div>
            </form>


          </div>


        </div>
      </div>

      {/* Animation styles */}
      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in {
          animation: fade-in 0.8s ease-out;
        }
        
        /* Custom select styling */
        select {
          appearance: none;
          -webkit-appearance: none;
          -moz-appearance: none;
          background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6,9 12,15 18,9'%3e%3c/polyline%3e%3c/svg%3e");
          background-repeat: no-repeat;
          background-position: right 1rem center;
          background-size: 1em;
          padding-right: 2.5rem !important;
        }
        

        

      `}</style>
    </div>
  );
};

export default HomePage;
