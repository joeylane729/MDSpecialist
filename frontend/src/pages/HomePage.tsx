import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { searchNPIProviders, getSpecialistRecommendations, rankNPIProviders } from '../services/api';
import { 
  Stethoscope, 
  Users, 
  Zap,
  ArrowRight,
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

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [diagnosis, setDiagnosis] = useState<string>('');
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [states, setStates] = useState<State[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [patientType, setPatientType] = useState<string>('');
  const [proximity, setProximity] = useState<string>('');
  const [gender, setGender] = useState<string>('');
  const [medications, setMedications] = useState<string>('');
  const [medicalHistory, setMedicalHistory] = useState<string>('');
  const [surgicalHistory, setSurgicalHistory] = useState<string>('');
  const [symptoms, setSymptoms] = useState<string>('');

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
    
    if (!selectedState || !selectedCity || !symptoms.trim() || !diagnosis.trim() || !patientType || !proximity) {
      alert('Please fill in all required fields before searching');
      return;
    }

    setIsLoading(true);
    
    // Clear any previous search results
    localStorage.removeItem('concierge_search_results');
    
    try {
      // Step 1: Get NPI data and AI recommendations in parallel
      const [npiData, aiRecommendations] = await Promise.all([
        // NPI search
        searchNPIProviders({
          state: selectedState,
          city: selectedCity,
          diagnosis: diagnosis,
          symptoms: symptoms,
          uploadedFiles: uploadedFiles,
          limit: 10000  // Get 10000 providers for ranking
        }),
        // AI recommendations
        getSpecialistRecommendations({
          symptoms: symptoms,
          diagnosis: diagnosis,
          medical_history: medicalHistory,
          medications: medications,
          surgical_history: surgicalHistory,
          files: []
        })
      ]);
      
      // Step 2: Rank NPI providers based on shared Pinecone data
      let rankedNPIProviders = npiData.providers;
      let rankingExplanation = '';
      let providerLinks: { [doctorName: string]: string } = {};
      try {
        const rankingResponse = await rankNPIProviders({
          npi_providers: npiData.providers,
          patient_input: `Symptoms: ${symptoms}\nDiagnosis: ${diagnosis}`,
          shared_specialist_information: aiRecommendations.shared_specialist_information
        });
        
        // Reorder providers based on ranking
        const rankedNPIs = rankingResponse.ranked_npis;
        rankedNPIProviders = rankedNPIs.map(npi => 
          npiData.providers.find(provider => provider.npi === npi)
        ).filter(Boolean);
        
        // Capture the ranking explanation and provider links
        rankingExplanation = rankingResponse.explanation;
        providerLinks = rankingResponse.provider_links || {};
        
        console.log('NPI providers ranked successfully:', rankingResponse.message);
        console.log('Ranking explanation:', rankingExplanation);
        console.log('Provider links:', providerLinks);
        console.log('DEBUG: Full ranking response:', rankingResponse);
      } catch (rankingError) {
        console.warn('Failed to rank NPI providers, using original order:', rankingError);
        rankingExplanation = 'Ranking failed - showing providers in original order.';
        // Keep original order if ranking fails
      }
      
      // Save search results to localStorage for persistence
      localStorage.setItem('concierge_search_results', JSON.stringify({
        searchParams: {
          state: selectedState,
          city: selectedCity,
          symptoms: symptoms,
          diagnosis: diagnosis,
          gender: gender,
          medications: medications,
          medicalHistory: medicalHistory,
          surgicalHistory: surgicalHistory,
          determined_specialty: npiData.search_criteria?.determined_specialty,
          predicted_icd10: npiData.search_criteria?.predicted_icd10,
          icd10_description: npiData.search_criteria?.icd10_description
        },
        providers: rankedNPIProviders,
        totalProviders: npiData.total_providers,
        aiRecommendations: aiRecommendations,
        rankingExplanation: rankingExplanation
      }));

      // Navigate to results page with both datasets
      navigate('/results', {
        state: {
          state: selectedState,
          city: selectedCity,
          symptoms: symptoms,
          diagnosis: diagnosis,
          gender: gender,
          medications: medications,
          medicalHistory: medicalHistory,
          surgicalHistory: surgicalHistory,
          determined_specialty: npiData.search_criteria?.determined_specialty,
          predicted_icd10: npiData.search_criteria?.predicted_icd10,
          icd10_description: npiData.search_criteria?.icd10_description,
          differential_diagnoses: npiData.search_criteria?.differential_diagnoses,
          searchParams: {
            state: selectedState,
            city: selectedCity,
            symptoms: symptoms,
            diagnosis: diagnosis,
            gender: gender,
            medications: medications,
            medicalHistory: medicalHistory,
            surgicalHistory: surgicalHistory,
            determined_specialty: npiData.search_criteria?.determined_specialty,
            predicted_icd10: npiData.search_criteria?.predicted_icd10,
            icd10_description: npiData.search_criteria?.icd10_description,
            differential_diagnoses: npiData.search_criteria?.differential_diagnoses
          },
          providers: rankedNPIProviders,
          totalProviders: npiData.total_providers,
          aiRecommendations: aiRecommendations,
          rankingExplanation: rankingExplanation,
          providerLinks: providerLinks
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
          <div className="bg-white/80 backdrop-blur-xl rounded-3xl shadow-2xl p-8 border border-white/20 mb-16">
            <div className="text-center mb-8">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-2 leading-tight py-2">
                ConciergeMD.ai
              </h1>
              <p className="text-lg text-gray-700 max-w-2xl mx-auto leading-relaxed mb-2">
                Find the <span className="font-semibold text-blue-600">best subspecialist</span> for your specific diagnosis.
              </p>
            </div>
            
            <form onSubmit={handleSearch} className="space-y-8">
              {/* Section 1: Basic Information */}
              <div className="bg-gray-100/70 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Users className="w-5 h-5 mr-2 text-blue-600" />
                  Basic Information
                </h3>
                <div className="flex flex-wrap gap-6">
                  {/* Patient Type */}
                  <div className="group min-w-[200px]">
                    <label className="block text-sm font-semibold text-gray-700 mb-3">Patient Type *</label>
                    <div className="h-12 flex items-center space-x-6 px-4 py-3 border-2 border-gray-200 rounded-xl bg-white">
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="radio"
                          name="patientType"
                          value="adult"
                          checked={patientType === 'adult'}
                          onChange={() => setPatientType('adult')}
                          className="h-4 w-4 text-blue-600"
                          required
                        />
                        <span className="ml-3 text-gray-700">Adult</span>
                      </label>
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="radio"
                          name="patientType"
                          value="pediatric"
                          checked={patientType === 'pediatric'}
                          onChange={() => setPatientType('pediatric')}
                          className="h-4 w-4 text-blue-600"
                          required
                        />
                        <span className="ml-3 text-gray-700">Pediatric</span>
                      </label>
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
                </div>

                {/* Location and Search Radius - Second Row */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
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

                  {/* Search Radius */}
                  <div className="group">
                    <label htmlFor="proximity" className="block text-sm font-semibold text-gray-700 mb-3">Search Radius *</label>
                    <select
                      id="proximity"
                      value={proximity}
                      onChange={(e) => setProximity(e.target.value)}
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300"
                      required
                    >
                      <option value="">Select search radius</option>
                      <option value="50">Within 50 miles</option>
                      <option value="100">Within 100 miles</option>
                      <option value="state">State-wide</option>
                      <option value="us">US-wide</option>
                      <option value="world">Worldwide</option>
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
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Symptoms */}
                  <div className="group">
                    <label htmlFor="symptoms" className="block text-sm font-semibold text-gray-700 mb-3">Symptoms *</label>
                    <textarea
                      id="symptoms"
                      value={symptoms}
                      onChange={(e) => setSymptoms(e.target.value)}
                      placeholder="Describe your current symptoms in detail, including when they started, severity, and any triggers..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={5}
                      required
                    />
                  </div>

                  {/* Diagnosis Description */}
                  <div className="group">
                    <label htmlFor="diagnosis" className="block text-sm font-semibold text-gray-700 mb-3">Diagnosis Description *</label>
                    <textarea
                      id="diagnosis"
                      value={diagnosis}
                      onChange={(e) => setDiagnosis(e.target.value)}
                      placeholder="Provide details about your diagnosis, test results, or what your doctor has told you..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={5}
                      required
                    />
                  </div>
                </div>
              </div>

              {/* Section 3: Medical History */}
              <div className="bg-gray-100/70 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <FileText className="w-5 h-5 mr-2 text-blue-600" />
                  Medical History
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Current Medications */}
                  <div className="group">
                    <label htmlFor="medications" className="block text-sm font-semibold text-gray-700 mb-3">Current Medications</label>
                    <textarea
                      id="medications"
                      value={medications}
                      onChange={(e) => setMedications(e.target.value)}
                      placeholder="List any current medications, dosages, and how long you've been taking them..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={4}
                    />
                  </div>

                  {/* Medical History */}
                  <div className="group">
                    <label htmlFor="medicalHistory" className="block text-sm font-semibold text-gray-700 mb-3">Relevant Medical History</label>
                    <textarea
                      id="medicalHistory"
                      value={medicalHistory}
                      onChange={(e) => setMedicalHistory(e.target.value)}
                      placeholder="Include chronic conditions, previous diagnoses, family history, and any other relevant medical information..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={4}
                    />
                  </div>

                  {/* Surgical History */}
                  <div className="group md:col-span-2">
                    <label htmlFor="surgicalHistory" className="block text-sm font-semibold text-gray-700 mb-3">Surgical History</label>
                    <textarea
                      id="surgicalHistory"
                      value={surgicalHistory}
                      onChange={(e) => setSurgicalHistory(e.target.value)}
                      placeholder="List any previous surgeries, procedures, or hospitalizations with dates if possible..."
                      className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-4 focus:ring-blue-100 focus:border-blue-500 transition-all duration-300 bg-white hover:border-blue-300 resize-none"
                      rows={3}
                    />
                  </div>
                </div>
              </div>

              {/* Section 4: Medical Documents */}
              <div className="bg-gray-100/70 rounded-2xl p-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center">
                  <Upload className="w-5 h-5 mr-2 text-blue-600" />
                  Medical Documents
                </h3>
                <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors bg-white/50">
                  <input
                    type="file"
                    multiple
                    accept=".pdf"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer">
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-lg text-gray-700 mb-2 font-medium">Click to upload medical documents</p>
                    <p className="text-gray-600 mb-1">Upload relevant medical files to help specialists better understand your case</p>
                    <p className="text-sm text-gray-500">
                      Accepted: Imaging reports, doctor's notes, biopsy reports, blood tests, etc.
                    </p>
                  </label>
                </div>
                
                {/* Uploaded Files List */}
                {uploadedFiles.length > 0 && (
                  <div className="mt-6">
                    <p className="text-sm font-medium text-gray-700 mb-3">Uploaded Files:</p>
                    <div className="space-y-2">
                      {uploadedFiles.map((file, index) => (
                        <div key={index} className="flex items-center justify-between bg-white rounded-lg px-4 py-3 border border-gray-200">
                          <div className="flex items-center space-x-3">
                            <FileText className="w-5 h-5 text-blue-500" />
                            <span className="text-sm text-gray-700 font-medium">{file.name}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeFile(index)}
                            className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Search Button */}
              <div className="text-center">
                <button
                  type="submit"
                  disabled={isLoading || !selectedState || !selectedCity || !symptoms.trim() || !diagnosis.trim() || !patientType || !proximity}
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
