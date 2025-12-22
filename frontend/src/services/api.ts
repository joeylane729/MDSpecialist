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
  isExcluded?: boolean;  // Flag for excluded providers
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
  predicted_icd10?: string;  // Predicted ICD-10 code
  icd10_description?: string;  // ICD-10 description
  diagnoses_prompt_text?: string;  // GPT prompt text used to generate diagnoses/treatment options
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
  custom_diagnoses_prompt?: string;
}

export interface MedicalAnalysisResponse {
  status: string;
  patient_profile: PatientProfile;
  message: string;
}

export interface CPTCodeGenerationRequest {
  search_query: string;
  treatment_options: Array<{
    name: string;
    outcomes: string;
    complications: string;
  }>;
  custom_prompt?: string; // Optional custom prompt to override default
}

export interface CPTCodeGenerationResponse {
  status: string;
  cpt_codes: Array<{ code: string; description: string }>;
  cpt_prompt_text: string;
  message: string;
}

export const generateCPTCodes = async (
  request: CPTCodeGenerationRequest
): Promise<CPTCodeGenerationResponse> => {
  try {
    console.log('🔍 [Frontend] Generating CPT codes:', {
      search_query: request.search_query?.substring(0, 100),
      treatment_options_count: request.treatment_options?.length
    });

    const formData = new FormData();
    formData.append('search_query', request.search_query);
    formData.append('treatment_options_json', JSON.stringify(request.treatment_options));
    if (request.custom_prompt) {
      formData.append('custom_prompt', request.custom_prompt);
    }
    
    console.log('🔍 [Frontend] Making API call to:', `${API_BASE_URL}/api/v1/medical-analysis/cpt-codes`);
    
    const response = await api.post('/api/v1/medical-analysis/cpt-codes', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    
    console.log('✅ [Frontend] CPT code generation response received:', response.data);
    return response.data;
  } catch (error) {
    console.error('❌ [Frontend] CPT code generation error:', error);
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to generate CPT codes');
    }
    throw error;
  }
};

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
    
    if (request.custom_diagnoses_prompt) {
      formData.append('custom_diagnoses_prompt', request.custom_diagnoses_prompt);
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
  cms_data?: any; // Optional CMS data for clinical volume bonus
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
  reviews?: HealthgradesReview[];  // Batch-fetched reviews from backend
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
      shared_specialist_information: request.shared_specialist_information,
      cms_data: request.cms_data // Include CMS data for clinical volume bonus
    };
    
    if (request.cms_data) {
      const cmsDataAny = request.cms_data as any;
      console.log('  - CMS data structure:', {
        hasTop25Npis: !!cmsDataAny.top_25_npis,
        top25NpisLength: cmsDataAny.top_25_npis?.length || 0,
        top25NpisType: Array.isArray(cmsDataAny.top_25_npis) ? 'array' : typeof cmsDataAny.top_25_npis,
        cmsDataKeys: Object.keys(request.cms_data)
      });
      if (cmsDataAny.top_25_npis && cmsDataAny.top_25_npis.length > 0) {
        console.log('  - Sample top_25_npis (first 5):', cmsDataAny.top_25_npis.slice(0, 5));
      }
    } else {
      console.warn('  ⚠️  NO CMS DATA IN RANKING REQUEST');
    }
    
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
    
    // Check if provider scores in response have clinical volume points
    if (response.data.treatment_rankings) {
      const firstTreatmentId = Object.keys(response.data.treatment_rankings)[0];
      if (firstTreatmentId) {
        const firstTreatment = response.data.treatment_rankings[firstTreatmentId];
        const providerScores = firstTreatment?.provider_scores || {};
        const scoresWithClinicalVolume = Object.values(providerScores).filter((scoreData: any) => 
          scoreData?.clinical_volume_points && scoreData.clinical_volume_points > 0
        );
        console.log(`🔍 [Frontend] Providers with clinical_volume_points in response (treatment ${firstTreatmentId}):`, scoresWithClinicalVolume.length);
        if (scoresWithClinicalVolume.length > 0) {
          console.log('  - Sample scores with clinical volume:', scoresWithClinicalVolume.slice(0, 3));
        } else {
          console.warn('  ⚠️  NO PROVIDER SCORES HAVE CLINICAL VOLUME POINTS IN RESPONSE');
        }
      }
    }
    
    return response.data;
  } catch (error) {
    console.error('❌ [Frontend] Error ranking NPI providers:', error);
    throw error;
  }
};

// Pre-authorization Letter API
export interface PreAuthLetterRequest {
  provider_info: {
    name: string;
    npi: string;
    specialty: string;
    publications?: Array<{ title: string; pmid?: string }>;
    clinical_volume?: {
      raw?: number;
      tot_srvcs?: number;
    };
    education?: {
      medicalSchool?: string;
      residency?: string;
      fellowship?: string;
    };
    years_experience?: number;
    yearsExperience?: number;
  };
  patient_diagnosis: string;
  patient_symptoms?: string;
  specificity_relevance?: {
    score?: number;
    [key: string]: any;
  };
  user_first_name?: string;
  user_last_name?: string;
  insurance_company_name?: string;
  insurance_company_email?: string;
  custom_prompt?: string;  // Custom prompt text if user wants to edit and re-run
}

export interface PreAuthLetterResponse {
  status: string;
  letter: string;
  prompt_text: string;  // The actual GPT prompt that was used
  message: string;
}

export const generatePreAuthLetter = async (
  request: PreAuthLetterRequest
): Promise<PreAuthLetterResponse> => {
  try {
    console.log('🔍 [Frontend] Generating pre-authorization letter for provider:', request.provider_info.npi);
    console.log('🔍 [Frontend] Request payload:', {
      provider_info: request.provider_info,
      patient_diagnosis: request.patient_diagnosis,
      user_first_name: request.user_first_name,
      user_last_name: request.user_last_name,
      insurance_company_name: request.insurance_company_name,
      insurance_company_email: request.insurance_company_email,
      has_custom_prompt: !!request.custom_prompt
    });
    
    const response = await api.post('/api/v1/preauth-letter', request, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    console.log('✅ [Frontend] Pre-authorization letter generated successfully');
    return response.data;
  } catch (error) {
    console.error('❌ [Frontend] Error generating pre-authorization letter:', error);
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to generate pre-authorization letter');
    }
    throw error;
  }
};

// ==================== REVIEWS API ====================

export interface HealthgradesReview {
  id: number;
  npi: number;
  first_name: string | null;
  last_name: string | null;
  review_index: number | null;
  review_text: string | null;
  review_author: string | null;
  review_date: string | null;
  is_relevant?: boolean;  // Boolean flag indicating if review is relevant to search query
}

export interface ReviewCountResponse {
  npi: number;
  review_count: number;
}

export const getReviewsByNPI = async (npi: string | number, limit: number = 100): Promise<HealthgradesReview[]> => {
  try {
    console.log(`🌐 [API] GET /api/v1/reviews/${npi}?limit=${limit}`);
    const response = await api.get<HealthgradesReview[]>(`/api/v1/reviews/${npi}`, {
      params: { limit }
    });
    console.log(`✅ [API] Received ${response.data.length} reviews for NPI ${npi}`);
    return response.data;
  } catch (error) {
    console.error(`❌ [API] Error fetching reviews for NPI ${npi}:`, error);
    return [];
  }
};

export const getReviewCount = async (npi: string | number): Promise<number> => {
  try {
    console.log(`🌐 [API] GET /api/v1/reviews/${npi}/count`);
    const response = await api.get<ReviewCountResponse>(`/api/v1/reviews/${npi}/count`);
    console.log(`✅ [API] Review count for NPI ${npi}: ${response.data.review_count}`);
    return response.data.review_count;
  } catch (error) {
    console.error(`❌ [API] Error fetching review count for NPI ${npi}:`, error);
    return 0;
  }
};

export interface SearchReviewCountResponse {
  npi: number;
  keywords: string | null;
  matching_review_count: number;
}

export const searchReviewsByKeywords = async (
  npi: string | number,
  keywords?: string,
  limit: number = 100
): Promise<HealthgradesReview[]> => {
  try {
    const params: any = { limit };
    if (keywords) {
      params.keywords = keywords;
    }
    
    console.log(`🔍 [API] GET /api/v1/reviews/${npi}/search?keywords=${keywords || 'none'}&limit=${limit}`);
    const response = await api.get<HealthgradesReview[]>(
      `/api/v1/reviews/${npi}/search`,
      { params }
    );
    console.log(`✅ [API] Found ${response.data.length} reviews for NPI ${npi} with keywords`);
    return response.data;
  } catch (error) {
    console.error(`❌ [API] Error searching reviews for NPI ${npi}:`, error);
    return [];
  }
};

export const getSearchReviewCount = async (
  npi: string | number,
  keywords?: string
): Promise<number> => {
  try {
    const params: any = {};
    if (keywords) {
      params.keywords = keywords;
    }
    
    console.log(`📊 [API] GET /api/v1/reviews/${npi}/search/count?keywords=${keywords || 'none'}`);
    const response = await api.get<SearchReviewCountResponse>(
      `/api/v1/reviews/${npi}/search/count`,
      { params }
    );
    console.log(`✅ [API] Found ${response.data.matching_review_count} matching reviews for NPI ${npi}`);
    return response.data.matching_review_count;
  } catch (error) {
    console.error(`❌ [API] Error fetching search review count for NPI ${npi}:`, error);
    return 0;
  }
};

export default api
