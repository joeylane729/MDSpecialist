import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getMedicalAnalysis } from '../services/api';
import { useTestingMode } from '../contexts/TestingModeContext';
import { 
  Stethoscope, 
  Users, 
  Zap,
  ArrowRight
} from 'lucide-react';

interface State {
  name: string;
  code: string;
}

interface City {
  name: string;
  state: string;
}

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const { testingMode } = useTestingMode();
  const [selectedState, setSelectedState] = useState<string>('NY');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [zipCode, setZipCode] = useState<string>('');
  const [diagnosis, setDiagnosis] = useState<string>('');
  const [anatomicalLocation, setAnatomicalLocation] = useState<string>('');
  const [states, setStates] = useState<State[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [patientAge, setPatientAge] = useState<{ month: string; year: string }>({ month: '1', year: '1980' });
  const [proximity, setProximity] = useState<string>('statewide');
  const [gender, setGender] = useState<string>('');
  const [specialty, setSpecialty] = useState<string>('Neurosurgery');
  const [selectedTreatmentCategories, setSelectedTreatmentCategories] = useState<string[]>([]);

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

  // When testing mode is off: no defaults (empty form). When testing mode is on: set testing defaults.
  useEffect(() => {
    if (!testingMode) {
      setSelectedState('');
      setSelectedCity('');
      setZipCode('');
      setDiagnosis('');
      setAnatomicalLocation('');
      setPatientAge({ month: '', year: '' });
      setProximity('');
      setGender('');
      setSpecialty('');
      setSelectedTreatmentCategories([]);
    } else {
      setSelectedState('NY');
      setSelectedCity('');
      setProximity('statewide');
      setSpecialty('Neurosurgery');
      setPatientAge({ month: '1', year: '1980' });
    }
  }, [testingMode]);

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
    // setTaxonomies([
    //   { code: '207Q00000X', description: 'Family Medicine' },
    //   { code: '207R00000X', description: 'Internal Medicine' },
    //   { code: '207T00000X', description: 'Neurological Surgery' },
    //   { code: '207U00000X', description: 'Nuclear Medicine' },
    //   { code: '207V00000X', description: 'Obstetrics & Gynecology' },
    //   { code: '207W00000X', description: 'Ophthalmology' },
    //   { code: '207X00000X', description: 'Orthopaedic Surgery' },
    //   { code: '207Y00000X', description: 'Otolaryngology' },
    //   { code: '207ZP0102X', description: 'Pediatric Otolaryngology' },
    //   { code: '208000000X', description: 'Pediatrics' }
    // ]);
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
      
      const stateCities = mockCities[selectedState] || [];
      setCities(stateCities);
      
      // Set default city for NY on initial load (only if city is empty)
      if (selectedState === 'NY' && stateCities.length > 0 && !selectedCity) {
        const nyCity = stateCities.find(city => city.name === 'New York');
        if (nyCity) {
          setSelectedCity('New York');
        }
      } else if (selectedState !== 'NY') {
        setSelectedCity(''); // Reset city when state changes to non-NY
      }
    } else {
      setCities([]);
      if (selectedState !== 'NY') {
        setSelectedCity('');
      }
    }
  }, [selectedState]);

  const handleSearch = async (provider: 'openai' | 'gemini' | 'gemini_no_thinking') => {
    if (!selectedState || !selectedCity || !diagnosis.trim() || !patientAge.month || !patientAge.year || !proximity) {
      alert('Please fill in all required fields before searching');
      return;
    }
    if (selectedTreatmentCategories.length === 0) {
      alert('Please select at least one treatment category');
      return;
    }

    // Clear any previous search results
    localStorage.removeItem('mdspecialist_search_results');

    // When testing mode is off: go straight to Results page; it will run medical analysis + full flow and show one loading screen
    if (!testingMode) {
      navigate('/results', {
        state: {
          autoRunFullFlow: true,
          state: selectedState,
          city: selectedCity,
          zipCode: zipCode,
          proximity: proximity,
          diagnosis: diagnosis,
          anatomical_location: anatomicalLocation,
          gender: gender,
          patientAge: patientAge,
          llm_provider: provider,
          selectedTreatmentCategories,
          providers: [],
          totalProviders: 0,
          providerLinks: {},
          treatmentRankings: null
        }
      });
      return;
    }

    setIsLoading(true);
    try {
      // Get medical analysis (diagnosis analysis only - providers are searched later on ResultsPage)
      const aiRecommendations = await getMedicalAnalysis({
        diagnosis: diagnosis,
        anatomical_location: anatomicalLocation,
        llm_provider: provider
      });
      
      // Debug logging for treatment options and ICD codes
      if (aiRecommendations) {
        console.log('🔍 [Frontend] HomePage - aiRecommendations received:', aiRecommendations);
        console.log('🔍 [Frontend] HomePage - aiRecommendations keys:', Object.keys(aiRecommendations));
        console.log('🔍 [Frontend] HomePage - patient_profile:', aiRecommendations.patient_profile);
        console.log('🔍 [Frontend] HomePage - ICD codes:', {
          predicted_icd10: aiRecommendations.patient_profile?.predicted_icd10,
          predicted_icd10_codes: aiRecommendations.patient_profile?.predicted_icd10_codes,
          predicted_icd10_codes_type: typeof aiRecommendations.patient_profile?.predicted_icd10_codes,
          predicted_icd10_codes_isArray: Array.isArray(aiRecommendations.patient_profile?.predicted_icd10_codes),
          predicted_icd10_codes_length: aiRecommendations.patient_profile?.predicted_icd10_codes?.length
        });
        if (aiRecommendations.patient_profile?.treatment_options) {
          console.log('🔍 DEBUG: Found treatment options:', aiRecommendations.patient_profile.treatment_options);
        }
      }
      
      // Save search results to localStorage for persistence
      localStorage.setItem('mdspecialist_search_results', JSON.stringify({
        searchParams: {
          state: selectedState,
          city: selectedCity,
          zipCode: zipCode,
          diagnosis: diagnosis,
          anatomical_location: anatomicalLocation,
          gender: gender,
          patientAge: patientAge,
          determined_specialty: aiRecommendations?.patient_profile?.determined_specialty || aiRecommendations?.patient_profile?.specialties_needed?.[0],
          predicted_icd10: aiRecommendations?.patient_profile?.predicted_icd10,
          predicted_icd10_codes: aiRecommendations?.patient_profile?.predicted_icd10_codes,
          icd10_relevancy_scores: aiRecommendations?.patient_profile?.icd10_relevancy_scores,
          icd10_llm_descriptions: aiRecommendations?.patient_profile?.icd10_llm_descriptions,
          icd10_description: aiRecommendations?.patient_profile?.icd10_description,
          icd10_descriptions: aiRecommendations?.patient_profile?.icd10_descriptions,
          treatment_options: aiRecommendations?.patient_profile?.treatment_options,
          cpt_codes: aiRecommendations?.patient_profile?.cpt_codes,
          cpt_prompt_text: aiRecommendations?.patient_profile?.cpt_prompt_text,
          cpt_categorization_prompt_text: aiRecommendations?.patient_profile?.cpt_categorization_prompt_text,
          diagnoses_prompt_text: aiRecommendations?.patient_profile?.diagnoses_prompt_text,
          search_query: aiRecommendations?.patient_profile?.search_query,
          llm_provider: aiRecommendations?.patient_profile?.llm_provider,
          timing_breakdown: aiRecommendations?.patient_profile?.timing_breakdown,
          selectedTreatmentCategories
        },
        providers: [], // Providers will be fetched later on ResultsPage
        totalProviders: 0,
        aiRecommendations: aiRecommendations,
        rankingExplanation: '',
        treatmentRankings: null
      }));

      console.log('🔍 [Frontend] HomePage - AI recommendations received:', {
        predicted_icd10: aiRecommendations?.patient_profile?.predicted_icd10,
        predicted_icd10_codes: aiRecommendations?.patient_profile?.predicted_icd10_codes,
        predicted_icd10_codes_type: typeof aiRecommendations?.patient_profile?.predicted_icd10_codes,
        predicted_icd10_codes_isArray: Array.isArray(aiRecommendations?.patient_profile?.predicted_icd10_codes),
        predicted_icd10_codes_length: aiRecommendations?.patient_profile?.predicted_icd10_codes?.length,
        full_patient_profile: aiRecommendations?.patient_profile
      });

      // Navigate to results page (test mode on: we have aiRecommendations; no autoRunFullFlow)
      navigate('/results', {
        state: {
          autoRunFullFlow: false,
          state: selectedState,
          city: selectedCity,
          zipCode: zipCode,
          proximity: proximity,
          diagnosis: diagnosis,
          anatomical_location: anatomicalLocation,
          gender: gender,
          patientAge: patientAge,
          determined_specialty: aiRecommendations?.patient_profile?.determined_specialty || aiRecommendations?.patient_profile?.specialties_needed?.[0],
          predicted_icd10: aiRecommendations?.patient_profile?.predicted_icd10,
          predicted_icd10_codes: aiRecommendations?.patient_profile?.predicted_icd10_codes,
          icd10_description: aiRecommendations?.patient_profile?.icd10_description,
          icd10_descriptions: aiRecommendations?.patient_profile?.icd10_descriptions,
          searchParams: {
            state: selectedState,
            city: selectedCity,
            zipCode: zipCode,
            diagnosis: diagnosis,
            anatomical_location: anatomicalLocation,
            gender: gender,
            patientAge: patientAge,
            determined_specialty: aiRecommendations?.patient_profile?.determined_specialty || aiRecommendations?.patient_profile?.specialties_needed?.[0],
            predicted_icd10: aiRecommendations?.patient_profile?.predicted_icd10,
            predicted_icd10_codes: aiRecommendations?.patient_profile?.predicted_icd10_codes,
            icd10_relevancy_scores: aiRecommendations?.patient_profile?.icd10_relevancy_scores,
            icd10_llm_descriptions: aiRecommendations?.patient_profile?.icd10_llm_descriptions,
            icd10_description: aiRecommendations?.patient_profile?.icd10_description,
            icd10_descriptions: aiRecommendations?.patient_profile?.icd10_descriptions,
            treatment_options: aiRecommendations?.patient_profile?.treatment_options,
            cpt_codes: aiRecommendations?.patient_profile?.cpt_codes,
            cpt_prompt_text: aiRecommendations?.patient_profile?.cpt_prompt_text,
            cpt_categorization_prompt_text: aiRecommendations?.patient_profile?.cpt_categorization_prompt_text,
            diagnoses_prompt_text: aiRecommendations?.patient_profile?.diagnoses_prompt_text,
            search_query: aiRecommendations?.patient_profile?.search_query,
            llm_provider: aiRecommendations?.patient_profile?.llm_provider,
            timing_breakdown: aiRecommendations?.patient_profile?.timing_breakdown,
            selectedTreatmentCategories
          },
          selectedTreatmentCategories,
          providers: [], // Providers will be fetched later on ResultsPage
          totalProviders: 0,
          aiRecommendations: aiRecommendations,
          rankingExplanation: '',
          providerLinks: {},
          treatmentRankings: null
        }
      });
    } catch (error) {
      console.error('Search error:', error);
      alert(`Search failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
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
            Analyzing your medical information...
          </h2>
        </div>
      </div>
    );
  }

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
          <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20 mb-16">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-2 leading-tight py-2">
                MDSpecialist.ai
              </h1>
              <p className="text-lg text-gray-700 max-w-2xl mx-auto leading-relaxed mb-2">
                Find the <span className="font-semibold text-blue-600">best subspecialist</span> for your specific diagnosis.
              </p>
            </div>
            
            <form onSubmit={(e) => e.preventDefault()} className="space-y-8">
              {/* Section 1: Basic Information */}
              <div className="bg-gray-100/70 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Users className="w-5 h-5 mr-2 text-blue-600" />
                  Basic Information
                </h3>
                <div className="flex flex-wrap gap-6">
                  {/* Patient Age */}
                  <div className="group min-w-[200px]">
                    <label className="block text-sm font-semibold text-gray-700 mb-3">Patient Age *</label>
                    <div className="flex space-x-3">
                      <div className="flex-1">
                        <select
                          value={patientAge.month}
                          onChange={(e) => setPatientAge(prev => ({ ...prev, month: e.target.value }))}
                          className="w-full px-3 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                          required
                        >
                          <option value="">Month</option>
                          <option value="1">January</option>
                          <option value="2">February</option>
                          <option value="3">March</option>
                          <option value="4">April</option>
                          <option value="5">May</option>
                          <option value="6">June</option>
                          <option value="7">July</option>
                          <option value="8">August</option>
                          <option value="9">September</option>
                          <option value="10">October</option>
                          <option value="11">November</option>
                          <option value="12">December</option>
                        </select>
                      </div>
                      <div className="flex-1">
                        <select
                          value={patientAge.year}
                          onChange={(e) => setPatientAge(prev => ({ ...prev, year: e.target.value }))}
                          className="w-full px-3 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                          required
                        >
                          <option value="">Year</option>
                          {Array.from({ length: 100 }, (_, i) => {
                            const year = new Date().getFullYear() - i;
                            return (
                              <option key={year} value={year}>
                                {year}
                              </option>
                            );
                          })}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Gender */}
                  <div className="group min-w-[200px]">
                    <label htmlFor="gender" className="block text-sm font-semibold text-gray-700 mb-3">Gender</label>
                    <select
                      id="gender"
                      value={gender}
                      onChange={(e) => setGender(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                    >
                      <option value="">Select gender</option>
                      <option value="male">Male</option>
                      <option value="female">Female</option>
                      <option value="other">Other</option>
                      <option value="prefer-not-to-say">Prefer not to say</option>
                    </select>
                  </div>

                  {/* Specialty */}
                  <div className="group min-w-[200px]">
                    <label htmlFor="specialty" className="block text-sm font-semibold text-gray-700 mb-3">Specialty</label>
                    <select
                      id="specialty"
                      value={specialty}
                      onChange={(e) => setSpecialty(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                    >
                      {!testingMode && <option value="">Select specialty</option>}
                      <option value="Neurosurgery">Neurosurgery</option>
                      <option value="Cardiology" disabled>Cardiology</option>
                      <option value="Dermatology" disabled>Dermatology</option>
                      <option value="Endocrinology" disabled>Endocrinology</option>
                      <option value="Gastroenterology" disabled>Gastroenterology</option>
                      <option value="Neurology" disabled>Neurology</option>
                      <option value="Orthopedics" disabled>Orthopedics</option>
                      <option value="Psychiatry" disabled>Psychiatry</option>
                      <option value="Pulmonology" disabled>Pulmonology</option>
                      <option value="Urology" disabled>Urology</option>
                      <option value="Oncology" disabled>Oncology</option>
                      <option value="Pediatrics" disabled>Pediatrics</option>
                      <option value="Gynecology" disabled>Gynecology</option>
                      <option value="Ophthalmology" disabled>Ophthalmology</option>
                      <option value="Otolaryngology" disabled>Otolaryngology</option>
                      <option value="Radiology" disabled>Radiology</option>
                      <option value="Pathology" disabled>Pathology</option>
                    </select>
                  </div>

                  {/* Treatment categories: when testing mode off, only show after specialty is selected */}
                  {(testingMode || specialty) && (
                    <div className="group min-w-[280px] w-full">
                      <div className="flex items-center justify-between mb-3">
                        <label className="block text-sm font-semibold text-gray-700">Select preferred treatment categories</label>
                        <button
                          type="button"
                          onClick={() => {
                            const all = ['surgery', 'radiation', 'endovascular', 'medical', 'diagnostic testing'];
                            setSelectedTreatmentCategories(
                              selectedTreatmentCategories.length === all.length ? [] : all
                            );
                          }}
                          className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                        >
                          {selectedTreatmentCategories.length === 5 ? 'Deselect all' : 'Select all'}
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-x-6 gap-y-2">
                        {[
                          { value: 'surgery', label: 'Surgery' },
                          { value: 'radiation', label: 'Radiation' },
                          { value: 'endovascular', label: 'Endovascular' },
                          { value: 'medical', label: 'Medical' },
                          { value: 'diagnostic testing', label: 'Diagnostic testing' }
                        ].map(({ value, label }) => (
                          <label
                            key={value}
                            className="flex items-center gap-2 cursor-pointer text-sm text-gray-700 hover:text-gray-900"
                          >
                            <input
                              type="checkbox"
                              checked={selectedTreatmentCategories.includes(value)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedTreatmentCategories(prev => [...prev, value]);
                                } else {
                                  setSelectedTreatmentCategories(prev => prev.filter(c => c !== value));
                                }
                              }}
                              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                            <span>{label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Location and Search Radius - Second Row */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-6">
                  {/* State */}
                  <div className="group">
                    <label htmlFor="state" className="block text-sm font-semibold text-gray-700 mb-3">State *</label>
                    <select
                      id="state"
                      value={selectedState}
                      onChange={(e) => setSelectedState(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
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

                  {/* City */}
                  <div className="group">
                    <label htmlFor="city" className="block text-sm font-semibold text-gray-700 mb-3">City *</label>
                    <select
                      id="city"
                      value={selectedCity}
                      onChange={(e) => setSelectedCity(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 disabled:opacity-50"
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

                  {/* Zip Code */}
                  <div className="group">
                    <label htmlFor="zipCode" className="block text-sm font-semibold text-gray-700 mb-3">Zip Code</label>
                    <input
                      type="text"
                      id="zipCode"
                      value={zipCode}
                      onChange={(e) => setZipCode(e.target.value)}
                      placeholder="Enter zip code"
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                      maxLength={10}
                    />
                  </div>

                  {/* Search Radius */}
                  <div className="group">
                    <label htmlFor="proximity" className="block text-sm font-semibold text-gray-700 mb-3">Search Area *</label>
                    <select
                      id="proximity"
                      value={proximity}
                      onChange={(e) => setProximity(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                      required
                    >
                      <option value="">Select search area</option>
                      <option value="statewide">Statewide</option>
                      <option value="us-wide">US-wide</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Section 2: Current Condition */}
              <div className="bg-gray-100/70 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Stethoscope className="w-5 h-5 mr-2 text-blue-600" />
                  Current Condition
                </h3>
                <div className="grid grid-cols-1 gap-6">
                  {/* Presumed Diagnosis */}
                  <div className="group">
                    <label htmlFor="diagnosis" className="block text-sm font-semibold text-gray-700 mb-3">Presumed Diagnosis *</label>
                    <textarea
                      id="diagnosis"
                      value={diagnosis}
                      onChange={(e) => setDiagnosis(e.target.value)}
                      placeholder="Provide details about your presumed diagnosis, test results, or what your doctor has told you..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={5}
                      required
                    />
                  </div>

                  {/* Anatomical Location (below diagnosis) */}
                  <div className="group">
                    <label htmlFor="anatomicalLocation" className="block text-sm font-semibold text-gray-700 mb-3">Anatomical Location</label>
                    <input
                      type="text"
                      id="anatomicalLocation"
                      value={anatomicalLocation}
                      onChange={(e) => setAnatomicalLocation(e.target.value)}
                      placeholder="e.g., brain, arm, spine, leg..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                    />
                  </div>
                </div>
              </div>

              {/* Search Buttons */}
              <div className="text-center">
                <div className="flex flex-col sm:flex-row flex-wrap gap-4 justify-center items-center max-w-4xl mx-auto">
                  {!testingMode ? (
                    /* Single Search button when testing mode is off (uses Gemini no thinking) */
                    <button
                      type="button"
                      onClick={() => handleSearch('gemini_no_thinking')}
                      disabled={isLoading || !selectedState || !selectedCity || !diagnosis.trim() || !patientAge.month || !patientAge.year || !proximity}
                      className="group relative inline-flex items-center justify-center w-full sm:w-auto bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-1"
                    >
                      {isLoading ? (
                        <div className="flex items-center justify-center">
                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                          <span>Searching...</span>
                        </div>
                      ) : (
                        <>
                          <Zap className="w-6 h-6 mr-3" />
                          <span>Find Top Specialists</span>
                          <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
                        </>
                      )}
                    </button>
                  ) : (
                    <>
                      {/* OpenAI Search Button */}
                      <button
                        type="button"
                        onClick={() => handleSearch('openai')}
                        disabled={isLoading || !selectedState || !selectedCity || !diagnosis.trim() || !patientAge.month || !patientAge.year || !proximity}
                        className="group relative inline-flex items-center justify-center w-full sm:w-auto bg-gradient-to-r from-green-600 to-emerald-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:from-green-700 hover:to-emerald-700 focus:ring-4 focus:ring-green-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-1"
                      >
                        {isLoading ? (
                          <div className="flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                            <span>Searching...</span>
                          </div>
                        ) : (
                          <>
                            <Zap className="w-6 h-6 mr-3" />
                            <span>Search with OpenAI</span>
                            <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
                          </>
                        )}
                      </button>

                      {/* Gemini (default thinking) Search Button */}
                      <button
                        type="button"
                        onClick={() => handleSearch('gemini')}
                        disabled={isLoading || !selectedState || !selectedCity || !diagnosis.trim() || !patientAge.month || !patientAge.year || !proximity}
                        className="group relative inline-flex items-center justify-center w-full sm:w-auto bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-1"
                      >
                        {isLoading ? (
                          <div className="flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                            <span>Searching...</span>
                          </div>
                        ) : (
                          <>
                            <Zap className="w-6 h-6 mr-3" />
                            <span>Search with Gemini (default thinking)</span>
                            <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
                          </>
                        )}
                      </button>

                      {/* Gemini (no thinking) Search Button */}
                      <button
                        type="button"
                        onClick={() => handleSearch('gemini_no_thinking')}
                        disabled={isLoading || !selectedState || !selectedCity || !diagnosis.trim() || !patientAge.month || !patientAge.year || !proximity}
                        className="group relative inline-flex items-center justify-center w-full sm:w-auto bg-gradient-to-r from-violet-600 to-purple-600 text-white py-5 px-8 rounded-2xl font-bold text-xl hover:from-violet-700 hover:to-purple-700 focus:ring-4 focus:ring-violet-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-1"
                      >
                        {isLoading ? (
                          <div className="flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                            <span>Searching...</span>
                          </div>
                        ) : (
                          <>
                            <Zap className="w-6 h-6 mr-3" />
                            <span>Search with Gemini (no thinking)</span>
                            <ArrowRight className="w-5 h-5 ml-3 group-hover:translate-x-1 transition-transform" />
                          </>
                        )}
                      </button>
                    </>
                  )}
                </div>
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
