import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url, config.data)
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for logging
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url, response.data)
    return response
  },
  (error) => {
    console.error('API Error:', error.response?.status, error.config?.url, error.response?.data)
    return Promise.reject(error)
  }
)

export interface MatchRequest {
  diagnosis: string
  metro_area: string
  location_radius?: number
  specialty?: string
  subspecialty?: string
  max_results?: number
}

export interface Doctor {
  id: number
  first_name: string
  last_name: string
  middle_name?: string
  title?: string
  specialty: string
  subspecialty?: string
  email?: string
  phone?: string
  website?: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  zip_code?: string
  metro_area?: string
  latitude?: number
  longitude?: number
  medical_school?: string
  medical_school_tier?: string
  graduation_year?: number
  residency_program?: string
  residency_tier?: string
  fellowship_programs?: any[]
  board_certifications?: string[]
  years_experience?: number
  clinical_years?: number
  research_years?: number
  teaching_years?: number
  leadership_roles?: string[]
  awards?: string[]
  website_mentions?: number
  patient_reviews?: any[]
  social_media?: any
  directory_listings?: string[]
  full_name: string
  display_name: string
  location_summary: string
  overall_grade?: string
  rank?: number
  created_at: string
  updated_at?: string
}

export interface MatchResponse {
  diagnosis: string
  metro_area: string
  location_radius?: number
  total_doctors_found: number
  doctors: Doctor[]
  search_summary: string
  search_duration_ms?: number
}

export const matchDoctors = async (request: MatchRequest): Promise<MatchResponse> => {
  try {
    const response = await api.post('/api/v1/match', request)
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to match doctors')
    }
    throw error
  }
}

export const getDoctor = async (id: number): Promise<Doctor> => {
  try {
    const response = await api.get(`/api/v1/doctors/${id}`)
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to get doctor')
    }
    throw error
  }
}

export const getDoctors = async (params?: {
  skip?: number
  limit?: number
  specialty?: string
  metro_area?: string
}): Promise<{
  doctors: Doctor[]
  total_count: number
  page: number
  page_size: number
  total_pages: number
}> => {
  try {
    const response = await api.get('/api/v1/doctors', { params })
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to get doctors')
    }
    throw error
  }
}

export const getDiagnosisSuggestions = async (query: string): Promise<string[]> => {
  try {
    const response = await api.get('/api/v1/suggestions/diagnosis', {
      params: { query }
    })
    return response.data.suggestions
  } catch (error) {
    console.error('Failed to get diagnosis suggestions:', error)
    return []
  }
}

export const getMetroSuggestions = async (query: string): Promise<string[]> => {
  try {
    const response = await api.get('/api/v1/suggestions/metro', {
      params: { query }
    })
    return response.data.suggestions
  } catch (error) {
    console.error('Failed to get metro suggestions:', error)
    return []
  }
}

export interface NPIProvider {
  id: string;
  npi: string;
  name: string;
  specialty: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
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
  // Additional professional information
  publications?: string[];
  books?: string[];
  lectures?: string[];
  specializations?: string[];
  fellowships?: string[];
  patientReviews?: Array<{
    rating: number;
    comment: string;
    date: string;
  }>;
  websites?: string[];
}

export interface NPISearchRequest {
  state: string;
  city: string;
  diagnosis: string;
  symptoms: string;
  uploadedFiles?: File[];
  limit?: number;
}

export interface NPISearchResponse {
  total_providers: number;
  providers: NPIProvider[];
  search_criteria: {
    state: string;
    city: string;
    diagnosis: string;
    determined_specialty: string;
    predicted_icd10?: string;
    icd10_description?: string;
    differential_diagnoses?: Array<{
      code: string;
      description: string;
    }>;
  };
}

export const searchNPIProviders = async (request: NPISearchRequest): Promise<NPISearchResponse> => {
  try {
    // Create FormData for file uploads
    const formData = new FormData();
    formData.append('state', request.state);
    formData.append('city', request.city);
    formData.append('diagnosis', request.diagnosis);
    formData.append('symptoms', request.symptoms);
    
    if (request.limit) {
      formData.append('limit', request.limit.toString());
    }
    
    // Add uploaded files
    if (request.uploadedFiles) {
      request.uploadedFiles.forEach((file) => {
        formData.append('files', file);
      });
    }
    
    const response = await api.post(`/api/v1/npi/search-providers`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.error || 'Failed to search NPI providers')
    }
    throw error
  }
}

export default api
