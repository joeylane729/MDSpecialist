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
  boardCertified: boolean;
  acceptingPatients: boolean;
}

export interface NPISearchRequest {
  state: string;
  city: string;
  zipCode: string;
  proximity: string;
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
    formData.append('zipCode', request.zipCode);
    formData.append('proximity', request.proximity);
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

// LangChain Specialist Recommendation Types
export interface SpecialistRecommendation {
  specialist_id: string;
  name: string;
  specialty: string;
  relevance_score: number;
  confidence_score: number;
  reasoning: string;
  metadata: any;
}

export interface PatientProfile {
  symptoms: string[];
  conditions: string[];
  specialties_needed: string[];
  location_preference?: string;
  additional_notes?: string;
  treatment_options?: Array<{
    name: string;
    outcomes: string;
    complications: string;
  }>;
}

export interface SpecialistRecommendationResponse {
  patient_profile: PatientProfile;
  recommendations: SpecialistRecommendation[];
  total_candidates_found: number;
  processing_time_ms: number;
  retrieval_strategies_used: string[];
  timestamp: string;
  shared_specialist_information?: any[];
}

export interface SpecialistRecommendationRequest {
  symptoms: string;
  diagnosis: string;
  medical_history?: string;
  medications?: string;
  surgical_history?: string;
  files?: File[];
}

export const getSpecialistRecommendations = async (
  request: SpecialistRecommendationRequest
): Promise<SpecialistRecommendationResponse> => {
  try {
    // Create FormData for the request
    const formData = new FormData();
    formData.append('symptoms', request.symptoms);
    formData.append('diagnosis', request.diagnosis);
    
    if (request.medical_history) {
      formData.append('medical_history', request.medical_history);
    }
    if (request.medications) {
      formData.append('medications', request.medications);
    }
    if (request.surgical_history) {
      formData.append('surgical_history', request.surgical_history);
    }

    
    // Add files if provided
    if (request.files) {
      request.files.forEach((file) => {
        formData.append('files', file);
      });
    }
    
    const response = await api.post('/api/v1/specialist-recommendations', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to get specialist recommendations');
    }
    throw error;
  }
};

// Medical Analysis API (without specialist retrieval)
export interface MedicalAnalysisRequest {
  symptoms: string;
  diagnosis: string;
  medical_history?: string;
  medications?: string;
  surgical_history?: string;
  files?: File[];
}

export interface MedicalAnalysisResponse {
  status: string;
  patient_profile: PatientProfile;
  message: string;
}

export const getMedicalAnalysis = async (
  request: MedicalAnalysisRequest
): Promise<MedicalAnalysisResponse> => {
  try {
    // Create FormData for the request
    const formData = new FormData();
    formData.append('symptoms', request.symptoms);
    formData.append('diagnosis', request.diagnosis);
    
    if (request.medical_history) {
      formData.append('medical_history', request.medical_history);
    }
    if (request.medications) {
      formData.append('medications', request.medications);
    }
    if (request.surgical_history) {
      formData.append('surgical_history', request.surgical_history);
    }
    
    // Add files if provided
    if (request.files) {
      request.files.forEach((file) => {
        formData.append('files', file);
      });
    }
    
    const response = await api.post('/api/v1/medical-analysis', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to get medical analysis');
    }
    throw error;
  }
};

export interface NPIRankingRequest {
  npi_providers: any[];
  patient_input: string;
  shared_specialist_information?: any[];
}

export interface VumediContent {
  link: string;
  title: string;
}

export interface PubMedArticle {
  pmid: string;
  title: string;
}

export interface ProviderContent {
  vumedi_content: VumediContent[];
  pubmed_articles: PubMedArticle[];
}

export interface NPIRankingResponse {
  status: string;
  ranked_npis: string[];
  explanation: string;
  provider_links: { [doctorName: string]: ProviderContent };
  total_providers: number;
  message: string;
}

export const rankNPIProviders = async (request: NPIRankingRequest): Promise<NPIRankingResponse> => {
  try {
    const formData = new FormData();
    formData.append('npi_providers', JSON.stringify(request.npi_providers));
    formData.append('patient_input', request.patient_input);
    
    // Add shared Pinecone data if provided
    if (request.shared_specialist_information) {
      formData.append('shared_specialist_information', JSON.stringify(request.shared_specialist_information));
    }
    
    const response = await api.post(`/api/v1/rank-npi-providers`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    return response.data;
  } catch (error) {
    console.error('Error ranking NPI providers:', error);
    throw error;
  }
};

export default api
