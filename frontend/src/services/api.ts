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
  yearsExperience?: number | null;
  rating?: number;
  languages?: string[];
  insurance?: string[];
  acceptingPatients: boolean;
  education?: {
    medicalSchool?: string | null;
    residency?: string | null;
    fellowship?: string | null;
    certifications?: string | null;
  };
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
  search_query?: string;  // Pre-generated search query for Pinecone
}

export interface SpecialistRecommendationResponse {
  patient_profile: PatientProfile;
  recommendations: SpecialistRecommendation[];
  total_candidates_found: number;
  processing_time_ms: number;
  retrieval_strategies_used: string[];
  timestamp: string;
  shared_specialist_information?: any[];
  search_query?: string;
  cms_data?: {
    url: string | null;
    results: any[];
    total_results: number;
    cpt_codes_searched?: string[];
    error: string | null;
  };
}

export interface SpecialistRecommendationRequest {
  symptoms: string;
  diagnosis: string;
  medical_history?: string;
  medications?: string;
  surgical_history?: string;
  state?: string;
  files?: File[];
  cpt_codes?: Array<{ code: string; description: string }>;  // Optional CPT codes to reuse (avoids duplicate generation)
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
    if (request.state) {
      formData.append('state', request.state);
    }
    
    // Add CPT codes if provided (to reuse from previous medical analysis)
    if (request.cpt_codes && request.cpt_codes.length > 0) {
      formData.append('cpt_codes_json', JSON.stringify(request.cpt_codes));
      console.log('♻️ [Frontend] Passing', request.cpt_codes.length, 'pre-generated CPT codes to reuse');
    }

    
    // Add files if provided
    if (request.files) {
      request.files.forEach((file) => {
        formData.append('files', file);
      });
    }
    
    console.log('🔍 [Frontend] Calling /api/v1/specialist-recommendations endpoint');
    const response = await api.post('/api/v1/specialist-recommendations', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    console.log('✅ [Frontend] /api/v1/specialist-recommendations response received:', {
      status: response.status,
      hasSharedSpecialistInfo: !!response.data?.shared_specialist_information,
      sharedInfoKeys: response.data?.shared_specialist_information ? Object.keys(response.data.shared_specialist_information) : []
    });
    
    // Debug: Check all top-level keys in response
    console.log('🔍 [Frontend] Response data keys:', Object.keys(response.data || {}));
    console.log('🔍 [Frontend] cms_data present?', 'cms_data' in (response.data || {}));
    if (response.data?.cms_data) {
      console.log('🔍 [Frontend] cms_data value:', response.data.cms_data);
      console.log('🔍 [Frontend] cms_data.total_results:', response.data.cms_data.total_results);
    } else {
      console.warn('⚠️ [Frontend] cms_data is MISSING from response!');
    }

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
    console.log('🔍 [Frontend] Starting medical analysis request:', {
      symptoms: request.symptoms,
      diagnosis: request.diagnosis,
      apiBaseUrl: API_BASE_URL,
      fullUrl: `${API_BASE_URL}/api/v1/medical-analysis`
    });

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
    
    console.log('🔍 [Frontend] Making API call to:', `${API_BASE_URL}/api/v1/medical-analysis`);
    
    const response = await api.post('/api/v1/medical-analysis', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    console.log('✅ [Frontend] Medical analysis response received:', response.data);
    return response.data;
  } catch (error) {
    console.error('❌ [Frontend] Medical analysis error:', error);
    if (axios.isAxiosError(error)) {
      console.error('❌ [Frontend] Axios error details:', {
        status: error.response?.status,
        statusText: error.response?.statusText,
        data: error.response?.data,
        url: error.config?.url,
        baseURL: error.config?.baseURL
      });
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

export interface ProviderScore {
  score: number;
  content_score: number;
  vumedi_count: number;
  pubmed_count: number;
  pubmed_first_author_count?: number;
  pubmed_middle_author_count?: number;
  pubmed_last_author_count?: number;
  pubmed_base_points?: number;
  pubmed_weighted_points?: number;
  pubmed_quartile_q1_count?: number;
  pubmed_quartile_q2_count?: number;
  pubmed_quartile_q3_count?: number;
  pubmed_quartile_q4_count?: number;
  pubmed_quartile_no_data_count?: number;
  med_school_score: number;
  residency_score?: number;
  experience_points?: number;
  years_experience?: number | null;
}

export interface TreatmentRanking {
  name: string;
  ranked_providers: string[];
  explanation: string;
  provider_links: { [npi: string]: ProviderContent };
  provider_scores: { [npi: string]: ProviderScore };
}

export interface NPIRankingResponse {
  status: string;
  treatment_rankings: { [treatmentId: string]: TreatmentRanking };
  total_treatments: number;
  message: string;
}

export const rankNPIProviders = async (request: NPIRankingRequest): Promise<NPIRankingResponse> => {
  try {
    console.log('🔍 [Frontend] rankNPIProviders called with:', {
      npi_count: request.npi_providers?.length,
      patient_input_length: request.patient_input?.length,
      has_shared_info: !!request.shared_specialist_information,
      shared_info_type: typeof request.shared_specialist_information,
      shared_info_keys: request.shared_specialist_information ? Object.keys(request.shared_specialist_information) : null
    });
    
    // Send as JSON instead of FormData to avoid size limits
    const payload = {
      npi_providers: request.npi_providers,
      patient_input: request.patient_input,
      shared_specialist_information: request.shared_specialist_information
    };
    
    const payloadSize = JSON.stringify(payload).length;
    console.log(`🔍 [Frontend] Calling /api/v1/rank-npi-providers with payload size: ${(payloadSize / 1024).toFixed(2)} KB`);
    console.log(`🔍 [Frontend] Payload contains:`, {
      npiProvidersCount: payload.npi_providers?.length || 0,
      hasPatientInput: !!payload.patient_input,
      hasSharedSpecialistInfo: !!payload.shared_specialist_information
    });
    
    const response = await api.post(`/api/v1/rank-npi-providers`, payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log('✅ [Frontend] /api/v1/rank-npi-providers response received:', {
      status: response.status,
      hasTreatmentRankings: !!response.data?.treatment_rankings,
      totalTreatments: response.data?.total_treatments || 0
    });
    
    console.log('✅ [Frontend] Ranking successful:', response.data.message);
    return response.data;
  } catch (error) {
    console.error('❌ [Frontend] Error ranking NPI providers:', error);
    throw error;
  }
};

export default api
