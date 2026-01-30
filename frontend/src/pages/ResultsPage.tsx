import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { NPIProvider, getSpecialistRecommendations, SpecialistRecommendationRequest, searchNPIProviders, rankNPIProviders, NPISearchRequest, NPIRankingRequest, ProviderContent, generateCPTCodes, generateSearchQuery, getMedicalAnalysis, regenerateICD10Code, categorizeCPTCodes } from '../services/api';
import api from '../services/api';
import NPIProviderCard from '../components/NPIProviderCard';
import { SCORING_WEIGHTS } from '../constants/scoringWeights';

interface Provider extends NPIProvider {
  email?: string;
  website?: string;
  languages?: string[];
  insurance?: string[];
}

interface SearchParams {
  state: string;
  city: string;
  diagnosis: string;
  anatomical_location?: string;
  determined_specialty?: string;
  predicted_icd10?: string;  // Primary code for backward compatibility
  predicted_icd10_codes?: string[];  // All ICD-10 codes
  icd10_relevancy_scores?: { [code: string]: number };  // Code -> relevancy score mapping (0-100)
  icd10_llm_descriptions?: { [code: string]: string };  // Code -> LLM description mappings
  icd10_descriptions?: { [code: string]: string | null };  // All code -> database description mappings
  icd10_description?: string;
  treatment_options?: Array<{
    name: string;
    category?: string;
  }>;
  cpt_codes?: Array<{
    code: string;
    description: string;
  }>;
  cpt_prompt_text?: string;  // Step 1: GPT prompt used to generate CPT codes + descriptions
  cpt_categorization_prompt_text?: string;  // Step 2: GPT prompt used to categorize and score codes
  diagnoses_prompt_text?: string;  // GPT prompt text used to generate diagnoses/treatment options
  icd10_prompt_text?: string;  // Step 1: GPT prompt used to generate ICD-10 codes + descriptions
  icd10_scoring_prompt_text?: string;  // Step 2: GPT prompt used to assign relevancy (DB descriptions)
  search_query?: string;  // Pre-generated search query
  search_query_diagnostic_terms?: string[];  // Parsed diagnostic terms (first OR group)
  search_query_anatomic_terms?: string[];  // Parsed anatomic terms (second OR group)
  llm_provider?: string;  // LLM provider used ("openai" or "gemini")
  search_query_prompt_text?: string;  // GPT prompt text used to generate search query
  patientAge?: { month: string; year: string };  // Patient age (month and year of birth)
  patient_age_category?: 'adult' | 'child';  // Patient age category
}

// Treatment options removed - no longer generated

// Helper function to map CPT codes to categories
const getCptCodeToCategoryMap = (cptCodesByCategory: { [category: string]: Array<{ code: string; description: string }> }): { [cptCode: string]: string } => {
  const map: { [cptCode: string]: string } = {};
  Object.entries(cptCodesByCategory).forEach(([category, codes]) => {
    codes.forEach(cpt => {
      map[cpt.code] = category;
    });
  });
  return map;
};

// Helper function to get categories from CPT codes
const getCategoriesFromCptCodes = (cptCodesByCategory: { [category: string]: Array<any> }): string[] => {
  const categories = Object.keys(cptCodesByCategory);
  
  // Define the preferred order for categories (case-insensitive matching)
  const categoryOrder = ['surgery', 'radiation', 'endovascular', 'medical', 'diagnostic testing'];
  
  // Sort categories: first by preferred order, then alphabetically for any others
  return categories.sort((a, b) => {
    const aLower = a.toLowerCase();
    const bLower = b.toLowerCase();
    const aIndex = categoryOrder.indexOf(aLower);
    const bIndex = categoryOrder.indexOf(bLower);
    
    // If both are in the preferred order, sort by their index
    if (aIndex !== -1 && bIndex !== -1) {
      return aIndex - bIndex;
    }
    // If only a is in the preferred order, it comes first
    if (aIndex !== -1) {
      return -1;
    }
    // If only b is in the preferred order, it comes first
    if (bIndex !== -1) {
      return 1;
    }
    // If neither is in the preferred order, sort alphabetically
    return a.localeCompare(b);
  });
};

// Helper function to calculate patient age category from birth month and year
const calculateAgeCategory = (month: string, year: string): 'adult' | 'child' | null => {
  if (!month || !year) return null;
  
  const birthMonth = parseInt(month, 10);
  const birthYear = parseInt(year, 10);
  
  if (isNaN(birthMonth) || isNaN(birthYear)) return null;
  
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1; // getMonth() returns 0-11
  
  let age = currentYear - birthYear;
  
  // Adjust age if birthday hasn't occurred this year
  if (currentMonth < birthMonth || (currentMonth === birthMonth && today.getDate() < 1)) {
    age--;
  }
  
  return age >= 18 ? 'adult' : 'child';
};

// Parse search query into diagnostic and anatomic term lists (matches backend format)
function parseSearchQuery(raw: string | undefined): { diagnostic: string[]; anatomic: string[] } {
  if (!raw?.trim()) return { diagnostic: [], anatomic: [] };
  const r = raw.trim();
  const match = r.match(/\(\s*([^)]+)\s*\)\s+AND\s+\(\s*([^)]+)\s*\)/i);
  if (match) {
    const first = match[1].split(/\s+OR\s+/).map((t) => t.trim()).filter(Boolean);
    const second = match[2].split(/\s+OR\s+/).map((t) => t.trim()).filter(Boolean);
    return { diagnostic: first, anatomic: second };
  }
  const terms = r.split(/\s+OR\s+/).map((t) => t.trim()).filter(Boolean);
  return { diagnostic: terms, anatomic: [] };
}

// Treatment options removed - categories now come from CPT codes

const ResultsPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchParams, setSearchParams] = useState<SearchParams | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [providersPerPage, setProvidersPerPage] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [isSearchExpanded, setIsSearchExpanded] = useState(false);
  // Treatment options removed - no longer needed
  const [isBackNavigation, setIsBackNavigation] = useState(false);
  const [rankedProviders, setRankedProviders] = useState<Provider[]>([]);
  const [filteredProviders, setFilteredProviders] = useState<Provider[]>([]);
  const [providerLinks, setProviderLinks] = useState<{ [npi: string]: ProviderContent }>({});
  const [providerScores, setProviderScores] = useState<{ [npi: string]: any }>({});
  const [treatmentRankings, setTreatmentRankings] = useState<{ [treatmentId: string]: any }>({});
  const [selectedCategory, setSelectedCategory] = useState<string>(''); // For specialists page filtering
  const [selectedDebugCategory, setSelectedDebugCategory] = useState<string>(''); // For debug page CMS results
  const [activeView, setActiveView] = useState<'assessment' | 'specialists' | 'debug'>('assessment');
  const [specialistRecommendationData, setSpecialistRecommendationData] = useState<any>(null);
  const [cptCodes, setCptCodes] = useState<Array<{ code: string; description: string }> | null>(null);
  const [cptCodesByCategory, setCptCodesByCategory] = useState<{ [category: string]: Array<{ code: string; description: string }> }>({});
  const [dbCptCodes, setDbCptCodes] = useState<Array<{ code: string; description: string; relevancy_score?: number }> | null>(null); // Database-mapped CPT codes
  const [dbCptCodesByCategory, setDbCptCodesByCategory] = useState<{ [category: string]: Array<{ code: string; description: string; relevancy_score?: number }> }>({}); // Database CPT codes by category
  const [activeCptSourceTab, setActiveCptSourceTab] = useState<'gpt' | 'database' | 'comparison'>('gpt'); // Tab for CPT code source (GPT vs Database vs Comparison)
  const [categorizationPromptText, setCategorizationPromptText] = useState<string | null>(null); // Prompt text used for categorizing database CPT codes
  const [editableCategorizationPromptText, setEditableCategorizationPromptText] = useState<string | null>(null); // Editable version of categorization prompt
  const [isRecategorizingCPTCodes, setIsRecategorizingCPTCodes] = useState(false); // Loading state for recategorization
  const [cptPromptTextByCategory, setCptPromptTextByCategory] = useState<{ [category: string]: string }>({});
  const [editablePromptTextByCategory, setEditablePromptTextByCategory] = useState<{ [category: string]: string }>({});
  const [selectedCptCategory, setSelectedCptCategory] = useState<string | null>(null);
  const [cptPromptText, setCptPromptText] = useState<string | null>(null);
  const [cptCategorizationPromptText, setCptCategorizationPromptText] = useState<string | null>(null);
  const [cptDbDescriptions, setCptDbDescriptions] = useState<{ [code: string]: string }>({}); // code -> long_desc from cpt_consolidated for GPT codes
  const [editablePromptText, setEditablePromptText] = useState<string | null>(null);
  const [diagnosesPromptText, setDiagnosesPromptText] = useState<string | null>(null);
  const [editableDiagnosesPromptText, setEditableDiagnosesPromptText] = useState<string | null>(null);
  const [searchQueryPromptText, setSearchQueryPromptText] = useState<string | null>(null);
  const [editableSearchQueryPromptText, setEditableSearchQueryPromptText] = useState<string | null>(null);
  const [icd10PromptText, setIcd10PromptText] = useState<string | null>(null);
  const [editableIcd10PromptText, setEditableIcd10PromptText] = useState<string | null>(null);
  const [isRegeneratingSearchQuery, setIsRegeneratingSearchQuery] = useState(false);
  const [isRegeneratingICD10, setIsRegeneratingICD10] = useState(false);
  const [isGeneratingCPTCodes, setIsGeneratingCPTCodes] = useState(false);
  const [isGeneratingCPTCodesForCategory, setIsGeneratingCPTCodesForCategory] = useState<string | null>(null);
  // Treatment options/diagnoses regeneration removed
  const [isGeneratingSpecialists, setIsGeneratingSpecialists] = useState(false);
  // Treatment options removed - no longer needed
  const hasInitializedCategoryFilter = useRef(false);
  
  // Helper function to get existing CPT codes from all possible sources (reusable logic)
  const getExistingCptCodes = useCallback((): Array<{code: string; description: string}> | null => {
    // Check all possible sources for CPT codes
    let existingCptCodes = cptCodes || searchParams?.cpt_codes || 
                          location.state?.aiRecommendations?.patient_profile?.cpt_codes;
    
    // If we have category-based codes, combine them all (takes precedence)
    if (Object.keys(cptCodesByCategory).length > 0) {
      const allCategoryCodes = Object.values(cptCodesByCategory).flat();
      if (allCategoryCodes.length > 0) {
        existingCptCodes = allCategoryCodes;
      }
    }
    
    return existingCptCodes && existingCptCodes.length > 0 ? existingCptCodes : null;
  }, [cptCodes, cptCodesByCategory, searchParams?.cpt_codes, location.state?.aiRecommendations?.patient_profile?.cpt_codes]);
  
  // Helper to check if CPT codes exist (boolean) - used for conditional rendering
  const hasCptCodes = useMemo(() => {
    return getExistingCptCodes() !== null;
  }, [getExistingCptCodes]);
  
  // Initial view is always 'assessment' (default state)
  
  // Debug logging
  useEffect(() => {
    console.log('ResultsPage - location.state:', location.state);
    console.log('ResultsPage - aiRecommendations:', location.state?.aiRecommendations);
    if (location.state?.aiRecommendations) {
      console.log('ResultsPage - aiRecommendations keys:', Object.keys(location.state.aiRecommendations));
      console.log('ResultsPage - cms_data present?', 'cms_data' in location.state.aiRecommendations);
      if (location.state.aiRecommendations.cms_data) {
        console.log('✅ ResultsPage - cms_data FOUND!', location.state.aiRecommendations.cms_data);
      } else {
        console.warn('⚠️ ResultsPage - cms_data MISSING!');
      }
      console.log('ResultsPage - patient_profile:', location.state.aiRecommendations.patient_profile);
      console.log('🔍 [Frontend] ResultsPage - ICD codes in aiRecommendations.patient_profile:', {
        predicted_icd10: location.state.aiRecommendations.patient_profile?.predicted_icd10,
        predicted_icd10_codes: location.state.aiRecommendations.patient_profile?.predicted_icd10_codes,
        predicted_icd10_codes_type: typeof location.state.aiRecommendations.patient_profile?.predicted_icd10_codes,
        predicted_icd10_codes_isArray: Array.isArray(location.state.aiRecommendations.patient_profile?.predicted_icd10_codes),
        predicted_icd10_codes_length: location.state.aiRecommendations.patient_profile?.predicted_icd10_codes?.length
      });
      console.log('ResultsPage - recommendations:', location.state.aiRecommendations.recommendations);
      
      // Debug search_query specifically
      if (location.state.aiRecommendations.patient_profile?.search_query) {
        console.log('🔍 DEBUG: ResultsPage found search_query in aiRecommendations patient_profile:', location.state.aiRecommendations.patient_profile.search_query);
      } else {
        console.log('🔍 DEBUG: ResultsPage - No search_query in aiRecommendations patient_profile');
      }
    }
    if (location.state?.providers) {
      console.log('ResultsPage - providers received:', location.state.providers.length);
      console.log('ResultsPage - first 5 provider NPIs:', location.state.providers.slice(0, 5).map((p: Provider) => p.npi));
    }
    
    // Treatment options removed - no longer generated
    
    // Debug search_query specifically
    if (searchParams?.search_query) {
      console.log('🔍 DEBUG: ResultsPage found search_query in searchParams:', searchParams.search_query);
    } else {
      console.log('🔍 DEBUG: ResultsPage - No search_query in searchParams');
      console.log('🔍 DEBUG: searchParams search_query:', searchParams?.search_query);
    }
  }, [location.state, searchParams]);
  
  // Initialize CPT codes from searchParams if available
  useEffect(() => {
    if (searchParams?.cpt_codes && !cptCodes) {
      setCptCodes(searchParams.cpt_codes);
      if (searchParams.cpt_prompt_text) {
        setCptPromptText(searchParams.cpt_prompt_text);
        setEditablePromptText(searchParams.cpt_prompt_text);
      }
      if (searchParams.cpt_categorization_prompt_text) {
        setCptCategorizationPromptText(searchParams.cpt_categorization_prompt_text);
      }
    }
  }, [searchParams, cptCodes]);

  // Initialize cptCodesByCategory from location.state if available (when navigating from HomePage)
  useEffect(() => {
    // Check if we have cptCodesByCategory in location.state (if it was stored there)
    if (location.state?.cptCodesByCategory && Object.keys(cptCodesByCategory).length === 0) {
      console.log('🔍 Initializing cptCodesByCategory from location.state');
      setCptCodesByCategory(location.state.cptCodesByCategory);
    }
  }, [location.state, cptCodesByCategory]);

  // Treatment options removed - cptCodesByCategory is now set directly from GPT response

  // Initialize selected category when treatmentRankings are available
  useEffect(() => {
    if (Object.keys(treatmentRankings).length > 0 && !selectedCategory) {
      // Default to "All" instead of first category
      setSelectedCategory('All');
      console.log('🔍 Auto-selecting "All" category');
    }
  }, [treatmentRankings, selectedCategory, searchParams, location.state?.aiRecommendations]);

  // Apply category filter when selectedCategory is set for the first time
  useEffect(() => {
    if (selectedCategory && Object.keys(treatmentRankings).length > 0 && !hasInitializedCategoryFilter.current) {
      // Get categories from CPT codes (combine GPT and AAPC categories)
      const allCategories = new Set<string>();
      Object.keys(cptCodesByCategory).forEach(cat => allCategories.add(cat));
      Object.keys(dbCptCodesByCategory).forEach(cat => allCategories.add(cat));
      const categories = Array.from(allCategories);
      
      // Handle both "All" and specific categories
      if (selectedCategory === 'All' || categories.includes(selectedCategory)) {
        // Group treatments by category for the filter change handler
        const treatmentsByCategory: { [category: string]: Array<{ id: string; treatment: any }> } = {};
        Object.entries(treatmentRankings).forEach(([treatmentId, treatment]) => {
          const category = (treatment as any).category || 'Medical';
          if (!treatmentsByCategory[category]) {
            treatmentsByCategory[category] = [];
          }
          treatmentsByCategory[category].push({ id: treatmentId, treatment });
        });
        
        // Apply the category filter once
        handleCategoryFilterChange(selectedCategory, treatmentsByCategory);
        hasInitializedCategoryFilter.current = true;
      }
    }
  }, [selectedCategory, treatmentRankings, searchParams, location.state?.aiRecommendations]);

  // Original useEffect for CPT codes (keeping for backward compatibility)
  useEffect(() => {
    if (searchParams?.cpt_codes && !cptCodes) {
      setCptCodes(searchParams.cpt_codes);
      if (searchParams.cpt_prompt_text) {
        setCptPromptText(searchParams.cpt_prompt_text);
        setEditablePromptText(searchParams.cpt_prompt_text);
      }
      if (searchParams.cpt_categorization_prompt_text) {
        setCptCategorizationPromptText(searchParams.cpt_categorization_prompt_text);
      }
    }
  }, [searchParams, cptCodes]);
  
  // Initialize diagnoses prompt text from searchParams if available
  useEffect(() => {
    if (searchParams?.diagnoses_prompt_text && !diagnosesPromptText) {
      setDiagnosesPromptText(searchParams.diagnoses_prompt_text);
      setEditableDiagnosesPromptText(searchParams.diagnoses_prompt_text);
    }
  }, [searchParams, diagnosesPromptText]);
  
  // Initialize ICD-10 prompt text from searchParams or location.state if available
  useEffect(() => {
    if (searchParams?.icd10_prompt_text && !icd10PromptText) {
      setIcd10PromptText(searchParams.icd10_prompt_text);
      setEditableIcd10PromptText(searchParams.icd10_prompt_text);
    } else if (location.state?.aiRecommendations?.patient_profile?.icd10_prompt_text && !icd10PromptText) {
      setIcd10PromptText(location.state.aiRecommendations.patient_profile.icd10_prompt_text);
      setEditableIcd10PromptText(location.state.aiRecommendations.patient_profile.icd10_prompt_text);
    }
    // icd10_scoring_prompt_text is read from searchParams / patient_profile for display only (no separate state)
  }, [searchParams, icd10PromptText, location.state]);

  // Initialize search query prompt text from searchParams or location.state if available
  useEffect(() => {
    if (searchParams?.search_query_prompt_text && !searchQueryPromptText) {
      setSearchQueryPromptText(searchParams.search_query_prompt_text);
      setEditableSearchQueryPromptText(searchParams.search_query_prompt_text);
    } else if (location.state?.aiRecommendations?.patient_profile?.search_query_prompt_text && !searchQueryPromptText) {
      setSearchQueryPromptText(location.state.aiRecommendations.patient_profile.search_query_prompt_text);
      setEditableSearchQueryPromptText(location.state.aiRecommendations.patient_profile.search_query_prompt_text);
    }
  }, [searchParams, searchQueryPromptText, location.state]);
  
  // Initialize selected treatment indices - all checked by default (only once)
  useEffect(() => {
    // Treatment options removed - no longer needed
    
    // Treatment options removed - no longer needed
  }, [searchParams, location.state?.aiRecommendations]);

  // CPT codes now come pre-categorized from GPT, so no reconstruction needed

  // Get provider score and breakdown
  const getProviderScore = (provider: any): { score: number; breakdown: string } => {
    const npi = provider.npi;
    const scoreData = providerScores[npi];
    
    if (!scoreData) {
      return { score: 0, breakdown: 'No score data available' };
    }
    
    const { 
      score, 
      weighted_breakdown,
      vumedi_count, 
      pubmed_count, 
      pubmed_first_author_count = 0,
      pubmed_middle_author_count = 0,
      pubmed_last_author_count = 0,
      pubmed_base_points = 0,
      pubmed_weighted_points = 0,
      pubmed_quartile_q1_count = 0,
      pubmed_quartile_q2_count = 0,
      pubmed_quartile_q3_count = 0,
      pubmed_quartile_q4_count = 0,
      pubmed_quartile_no_data_count = 0,
      med_school_score,
      residency_score = 0,
      experience_points = 0,
      certification_points = 0,
      clinical_volume_points = 0,
      abns_points = 0,
      aoa_points = 0,
      years_experience
    } = scoreData;
    
    // Log clinical volume points for debugging (only for first few providers to avoid spam)
    if (typeof window !== 'undefined' && !(window as any).__clinicalVolumeLogged) {
      (window as any).__clinicalVolumeLogged = new Set();
    }
    const loggedSet = (window as any).__clinicalVolumeLogged as Set<string>;
    if (!loggedSet.has(npi) && clinical_volume_points > 0) {
      console.log(`✅ [Frontend] Provider ${npi} (${provider.first_name} ${provider.last_name}) has clinical_volume_points: ${clinical_volume_points}`);
      loggedSet.add(npi);
      // Only log first 10
      if (loggedSet.size <= 10) {
        console.log(`  - Full scoreData for ${npi}:`, JSON.stringify(scoreData, null, 2));
      }
    }
    
    // Create weighted breakdown display if available
    if (weighted_breakdown) {
      const breakdownParts = [];
      
      // Add header explaining the weighting system
      breakdownParts.push('Score Breakdown (Weighted System):\n');
      breakdownParts.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');
      
      // Clinical Volume (40%)
      const cv = weighted_breakdown.clinical_volume;
      breakdownParts.push(`1. Clinical Volume (${cv.weight}% weight)`);
      breakdownParts.push(`   Percentage: ${cv.percentage.toFixed(1)}%`);
      breakdownParts.push(`   Weighted Points: ${cv.weighted_points.toFixed(2)} / ${cv.weight}`);
      breakdownParts.push(`   Status: ${cv.percentage > 0 ? '✓ Top 25 CMS provider' : 'Not in top 25'}\n`);
      
      // PubMed (40%)
      const pubmed = weighted_breakdown.pubmed;
      breakdownParts.push(`2. PubMed Articles (${pubmed.weight}% weight)`);
      breakdownParts.push(`   Percentage: ${pubmed.percentage.toFixed(1)}%`);
      breakdownParts.push(`   Weighted Points: ${pubmed.weighted_points.toFixed(2)} / ${pubmed.weight}`);
      if (pubmed_count > 0) {
        breakdownParts.push(`   Details: ${pubmed_count} article${pubmed_count !== 1 ? 's' : ''} (weighted by author position & journal quartile)`);
        if (pubmed_first_author_count > 0 || pubmed_middle_author_count > 0 || pubmed_last_author_count > 0) {
          const authorParts = [];
          if (pubmed_first_author_count > 0) authorParts.push(`${pubmed_first_author_count} first author${pubmed_first_author_count !== 1 ? 's' : ''}`);
          if (pubmed_middle_author_count > 0) authorParts.push(`${pubmed_middle_author_count} middle author${pubmed_middle_author_count !== 1 ? 's' : ''}`);
          if (pubmed_last_author_count > 0) authorParts.push(`${pubmed_last_author_count} last author${pubmed_last_author_count !== 1 ? 's' : ''}`);
          breakdownParts.push(`     - ${authorParts.join(', ')}`);
        }
      } else {
        breakdownParts.push(`   Details: No PubMed articles found`);
      }
      breakdownParts.push('');
      
      // Training (10%) - Med school + Residency + Certification
      const training = weighted_breakdown.training;
      breakdownParts.push(`3. Training (${training.weight}% weight - Med School + Residency + Board Certifications)`);
      breakdownParts.push(`   Percentage: ${training.percentage.toFixed(1)}%`);
      breakdownParts.push(`   Weighted Points: ${training.weighted_points.toFixed(2)} / ${training.weight}`);
      const trainingDetails = [];
      if (med_school_score > 0) trainingDetails.push(`Med school: ${med_school_score} pts`);
      if (residency_score > 0) trainingDetails.push(`Residency: ${residency_score} pts`);
      if (certification_points > 0) {
        const certDetails = [];
        if (abns_points > 0) certDetails.push(`ABNS: ${abns_points}`);
        if (aoa_points > 0) certDetails.push(`AOA: ${aoa_points}`);
        trainingDetails.push(`Certifications: ${certDetails.join(', ')}`);
      }
      breakdownParts.push(`   Details: ${trainingDetails.length > 0 ? trainingDetails.join(' | ') : 'No training data'}\n`);
      
      // Experience (6%)
      const exp = weighted_breakdown.experience;
      breakdownParts.push(`4. Years of Experience (${exp.weight}% weight)`);
      breakdownParts.push(`   Percentage: ${exp.percentage.toFixed(1)}%`);
      breakdownParts.push(`   Weighted Points: ${exp.weighted_points.toFixed(2)} / ${exp.weight}`);
      if (years_experience) {
        breakdownParts.push(`   Details: ${years_experience} year${years_experience !== 1 ? 's' : ''} of experience`);
      } else {
        breakdownParts.push(`   Details: Experience data not available`);
      }
      breakdownParts.push('');
      
      // Vumedi (4%)
      const vumedi = weighted_breakdown.vumedi;
      breakdownParts.push(`5. Medical Lectures - Vumedi (${vumedi.weight}% weight)`);
      breakdownParts.push(`   Percentage: ${vumedi.percentage.toFixed(1)}%`);
      breakdownParts.push(`   Weighted Points: ${vumedi.weighted_points.toFixed(2)} / ${vumedi.weight}`);
      if (vumedi_count > 0) {
        breakdownParts.push(`   Details: ${vumedi_count} video${vumedi_count !== 1 ? 's' : ''}`);
      } else {
        breakdownParts.push(`   Details: No Vumedi videos found`);
      }
      breakdownParts.push('');
      
      // Total
      breakdownParts.push('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
      breakdownParts.push(`Total Weighted Score: ${score.toFixed(2)} / 100`);
      breakdownParts.push('');
      breakdownParts.push(`Weight Distribution:`);
      breakdownParts.push(`  • Clinical Volume: ${SCORING_WEIGHTS.CLINICAL_VOLUME}%`);
      breakdownParts.push(`  • PubMed: ${SCORING_WEIGHTS.PUBMED}%`);
      breakdownParts.push(`  • Training: ${SCORING_WEIGHTS.TRAINING}%`);
      breakdownParts.push(`  • Experience: ${SCORING_WEIGHTS.EXPERIENCE}%`);
      breakdownParts.push(`  • Vumedi: ${SCORING_WEIGHTS.VUMEDI}%`);
      
      const breakdown = breakdownParts.join('\n');
      return { score, breakdown };
    }
    
    // Fallback to old breakdown format if weighted_breakdown is not available
    const breakdownParts = [];
    if (vumedi_count > 0) {
      breakdownParts.push(`${vumedi_count} Vumedi video${vumedi_count > 1 ? 's' : ''} = ${vumedi_count * 4} point${vumedi_count * 4 !== 1 ? 's' : ''} (${vumedi_count} × 4)`);
    }
    
    // Show weighted PubMed breakdown with quartile multipliers
    if (pubmed_count > 0) {
      const pubmedBreakdownParts = [];
      
      // Show author position breakdown with base points
      if (pubmed_first_author_count > 0) {
        pubmedBreakdownParts.push(`First author: ${pubmed_first_author_count} appearance${pubmed_first_author_count !== 1 ? 's' : ''} = ${pubmed_first_author_count * 2} base point${pubmed_first_author_count * 2 !== 1 ? 's' : ''} (${pubmed_first_author_count} × 2)`);
      }
      
      if (pubmed_middle_author_count > 0) {
        pubmedBreakdownParts.push(`Middle author: ${pubmed_middle_author_count} appearance${pubmed_middle_author_count !== 1 ? 's' : ''} = ${pubmed_middle_author_count} base point${pubmed_middle_author_count !== 1 ? 's' : ''} (${pubmed_middle_author_count} × 1)`);
      }
      
      if (pubmed_last_author_count > 0) {
        pubmedBreakdownParts.push(`Last author: ${pubmed_last_author_count} appearance${pubmed_last_author_count !== 1 ? 's' : ''} = ${pubmed_last_author_count * 3} base point${pubmed_last_author_count * 3 !== 1 ? 's' : ''} (${pubmed_last_author_count} × 3)`);
      }
      
      // Show quartile breakdown
      const quartileBreakdownParts = [];
      if (pubmed_quartile_q1_count > 0) {
        quartileBreakdownParts.push(`Q1: ${pubmed_quartile_q1_count} article${pubmed_quartile_q1_count !== 1 ? 's' : ''} (×1.0 multiplier)`);
      }
      if (pubmed_quartile_q2_count > 0) {
        quartileBreakdownParts.push(`Q2: ${pubmed_quartile_q2_count} article${pubmed_quartile_q2_count !== 1 ? 's' : ''} (×0.75 multiplier)`);
      }
      if (pubmed_quartile_q3_count > 0) {
        quartileBreakdownParts.push(`Q3: ${pubmed_quartile_q3_count} article${pubmed_quartile_q3_count !== 1 ? 's' : ''} (×0.5 multiplier)`);
      }
      if (pubmed_quartile_q4_count > 0) {
        quartileBreakdownParts.push(`Q4: ${pubmed_quartile_q4_count} article${pubmed_quartile_q4_count !== 1 ? 's' : ''} (×0.25 multiplier)`);
      }
      if (pubmed_quartile_no_data_count > 0) {
        quartileBreakdownParts.push(`No quartile data: ${pubmed_quartile_no_data_count} article${pubmed_quartile_no_data_count !== 1 ? 's' : ''} (×1.0 multiplier)`);
      }
      
      // Build the full PubMed breakdown
      let pubmedBreakdown = `PubMed articles (${pubmed_count} total):`;
      
      if (pubmedBreakdownParts.length > 0) {
        pubmedBreakdown += `\n  Author positions:\n    ${pubmedBreakdownParts.join('\n    ')}`;
        pubmedBreakdown += `\n  Base points: ${pubmed_base_points || 0} point${(pubmed_base_points || 0) !== 1 ? 's' : ''}`;
      }
      
      if (quartileBreakdownParts.length > 0) {
        pubmedBreakdown += `\n  Journal quartiles:\n    ${quartileBreakdownParts.join('\n    ')}`;
      }
      
      pubmedBreakdown += `\n  Weighted total: ${pubmed_weighted_points || 0} point${(pubmed_weighted_points || 0) !== 1 ? 's' : ''} (after quartile multipliers)`;
      
      breakdownParts.push(pubmedBreakdown);
    }
    
    if (med_school_score > 0) {
      breakdownParts.push(`Medical school ranking = ${med_school_score} point${med_school_score > 1 ? 's' : ''}`);
    }
    
    if (residency_score > 0) {
      breakdownParts.push(`Residency ranking = ${residency_score} point${residency_score > 1 ? 's' : ''}`);
    }
    
    if (typeof years_experience === 'number' && !Number.isNaN(years_experience)) {
      const experienceSuffix = years_experience === 1 ? '' : 's';
      if (experience_points > 0) {
        breakdownParts.push(`Experience: ${years_experience} year${experienceSuffix} = ${experience_points} point${experience_points !== 1 ? 's' : ''} (bonus)`);
      } else {
        breakdownParts.push(`Experience: ${years_experience} year${experienceSuffix} = 0 points`);
      }
    }
    
    if (certification_points > 0) {
      const certParts = [];
      if (abns_points > 0) {
        certParts.push(`ABNS certified = ${abns_points} point${abns_points !== 1 ? 's' : ''}`);
      }
      if (aoa_points > 0) {
        certParts.push(`AOA certified = ${aoa_points} point${aoa_points !== 1 ? 's' : ''}`);
      }
      if (certParts.length > 0) {
        breakdownParts.push(certParts.join(', '));
      }
    }
    
    if (clinical_volume_points > 0) {
      breakdownParts.push(`Clinical volume: Top 25 CMS provider = ${clinical_volume_points} point${clinical_volume_points !== 1 ? 's' : ''}`);
    }
    
    const breakdown = breakdownParts.length > 0 
      ? breakdownParts.join('\n') + `\n\nTotal: ${score} points`
      : 'No score data available';
    
    return { score, breakdown };
  };




  useEffect(() => {
    // Scroll to top when component mounts or location.state changes
    window.scrollTo(0, 0);
    
    // Try to get data from location.state first (direct navigation)
    // Note: providers can be an empty array initially (providers are fetched later on ResultsPage)
    if (location.state?.searchParams && location.state.providers !== undefined) {
      console.log('🔍 [Frontend] ResultsPage - location.state.searchParams:', location.state.searchParams);
      console.log('🔍 [Frontend] ResultsPage - ICD codes in searchParams:', {
        predicted_icd10: location.state.searchParams.predicted_icd10,
        predicted_icd10_codes: location.state.searchParams.predicted_icd10_codes,
        predicted_icd10_codes_type: typeof location.state.searchParams.predicted_icd10_codes,
        predicted_icd10_codes_isArray: Array.isArray(location.state.searchParams.predicted_icd10_codes),
        predicted_icd10_codes_length: location.state.searchParams.predicted_icd10_codes?.length
      });
      console.log('🔍 DEBUG: ResultsPage - search_query in searchParams:', location.state.searchParams.search_query);
      
      // Calculate age category if patientAge is available
      const patientAge = location.state.searchParams.patientAge || location.state.patientAge;
      let ageCategory: 'adult' | 'child' | undefined = undefined;
      if (patientAge && patientAge.month && patientAge.year) {
        ageCategory = calculateAgeCategory(patientAge.month, patientAge.year) || undefined;
      }
      
      const searchParamsWithAge = {
        ...location.state.searchParams,
        patientAge: patientAge,
        patient_age_category: ageCategory
      };
      
      console.log('🔍 [Frontend] ResultsPage - Setting searchParams with ICD codes:', {
        predicted_icd10: searchParamsWithAge.predicted_icd10,
        predicted_icd10_codes: searchParamsWithAge.predicted_icd10_codes,
        predicted_icd10_codes_length: searchParamsWithAge.predicted_icd10_codes?.length
      });
      
      setSearchParams(searchParamsWithAge);
      setProviders(location.state.providers);
      
      // Check if we have treatment rankings data to use for initial display
      if (location.state.treatmentRankings && Object.keys(location.state.treatmentRankings).length > 0) {
        console.log('🔍 Initializing with treatment rankings from location.state');
        setTreatmentRankings(location.state.treatmentRankings);
        
        // Initialize selected category to "All"
        const allCategories = new Set<string>();
        Object.keys(cptCodesByCategory).forEach(cat => allCategories.add(cat));
        Object.keys(dbCptCodesByCategory).forEach(cat => allCategories.add(cat));
        if (allCategories.size > 0 && !selectedCategory) {
          // Default to "All"
          setSelectedCategory('All');
          console.log('🔍 Initializing selected category to: All');
        }
        
        // Combine all providers and links from all treatments (same logic as category filter)
        const allRankedNPIs = new Set<string>();
        const allProviderLinks: { [npi: string]: ProviderContent } = {};
        
        Object.values(location.state.treatmentRankings).forEach((treatment: any) => {
          if (treatment.ranked_providers) {
            treatment.ranked_providers.forEach((npi: string) => allRankedNPIs.add(npi));
          }
          if (treatment.provider_links) {
            Object.assign(allProviderLinks, treatment.provider_links);
          }
        });
        
        const rankedNPIProviders = Array.from(allRankedNPIs).map((npi: string) => 
          location.state.providers.find((provider: Provider) => provider.npi === npi)
        ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
        
        setRankedProviders(rankedNPIProviders);
        setProviderLinks(allProviderLinks);
        console.log('🔍 Initial ranked providers from all treatments:', rankedNPIProviders.length);
      } else {
        // Fallback to all providers if no treatment rankings available
        setRankedProviders(location.state.providers);
        console.log('🔍 No treatment rankings, using all providers:', location.state.providers.length);
      }
      
      const links = location.state.providerLinks || {};
      console.log('DEBUG: Setting provider links:', links);
      console.log('DEBUG: Provider names:', location.state.providers.slice(0, 5).map((p: Provider) => p.name));
      setIsLoading(false);
      setCurrentPage(1);
      
      // Save to localStorage for back navigation
      localStorage.setItem('mdspecialist_search_results', JSON.stringify({
        searchParams: location.state.searchParams,
        providers: location.state.providers,
        filters: {
          searchTerm,
          currentPage,
          providersPerPage
        }
      }));
      return;
    }
    
    // Try to get data from localStorage (back navigation)
    const savedSearchData = localStorage.getItem('mdspecialist_search_results');
    if (savedSearchData) {
      try {
        const parsed = JSON.parse(savedSearchData);
        console.log('🔍 DEBUG: Loading from localStorage - parsed data:', parsed);
        console.log('🔍 DEBUG: Loading from localStorage - searchParams:', parsed.searchParams);
        console.log('🔍 DEBUG: Loading from localStorage - treatment_options:', parsed.searchParams?.treatment_options);
        if (parsed.searchParams && parsed.providers && parsed.providers.length > 0) {
          // Calculate age category if patientAge is available
          const patientAge = parsed.searchParams.patientAge;
          let ageCategory: 'adult' | 'child' | undefined = undefined;
          if (patientAge && patientAge.month && patientAge.year) {
            ageCategory = calculateAgeCategory(patientAge.month, patientAge.year) || undefined;
          }
          
          const searchParamsWithAge = {
            ...parsed.searchParams,
            patient_age_category: ageCategory
          };
          setSearchParams(searchParamsWithAge);
          setProviders(parsed.providers);
          
          // Restore filter state if available
          if (parsed.filters) {
            console.log('Restoring filters from localStorage:', parsed.filters);
            setSearchTerm(parsed.filters.searchTerm || '');
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
      // Calculate age category if patientAge is available
      const patientAge = location.state.searchParams.patientAge || location.state.patientAge;
      let ageCategory: 'adult' | 'child' | undefined = undefined;
      if (patientAge && patientAge.month && patientAge.year) {
        ageCategory = calculateAgeCategory(patientAge.month, patientAge.year) || undefined;
      }
      
      const searchParamsWithAge = {
        ...location.state.searchParams,
        patientAge: patientAge,
        patient_age_category: ageCategory
      };
      setSearchParams(searchParamsWithAge);
      setCurrentPage(1);
    } else {
      // No location.state data - should not happen in normal flow
      console.warn('ResultsPage: No location.state data available');
      setCurrentPage(1);
    }
  }, [location.state]);

  // Separate useEffect to restore filter state from localStorage on component mount
  useEffect(() => {
    console.log('Component mount useEffect running...');
    const savedSearchData = localStorage.getItem('mdspecialist_search_results');
    if (savedSearchData) {
      try {
        const parsed = JSON.parse(savedSearchData);
        console.log('Found saved data on mount:', parsed);
        if (parsed.filters && !location.state?.providers) {
          console.log('Restoring filters on mount:', parsed.filters);
          // Only restore filters if we don't have fresh data from navigation
          setSearchTerm(parsed.filters.searchTerm || '');
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
      const savedSearchData = localStorage.getItem('mdspecialist_search_results');
      if (savedSearchData) {
        try {
          const parsed = JSON.parse(savedSearchData);
          if (parsed.filters) {
            console.log('Restoring filters on back navigation:', parsed.filters);
            setSearchTerm(parsed.filters.searchTerm || '');
            setCurrentPage(parsed.filters.currentPage || 1);
            setProvidersPerPage(parsed.filters.providersPerPage || 20);
            
            // Log the state after setting
            setTimeout(() => {
              console.log('State after restoration:', {
                searchTerm,
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
      currentPage,
      providersPerPage
    });
  }, [searchTerm, currentPage, providersPerPage]);

  // Effect to update filtered providers when ranked providers or search term changes
  useEffect(() => {
    if (rankedProviders.length > 0) {
      const filtered = rankedProviders.filter(provider => {
        // Search filter
        if (searchTerm && !provider.name.toLowerCase().includes(searchTerm.toLowerCase()) &&
            !provider.specialty.toLowerCase().includes(searchTerm.toLowerCase()) &&
            !provider.city.toLowerCase().includes(searchTerm.toLowerCase())) {
          return false;
        }
        
        
        return true;
      });
      
      // Update filtered providers without affecting the original ranked providers
      setFilteredProviders(filtered);
      setCurrentPage(1); // Reset to first page when filters change
    } else {
      // If no ranked providers, clear filtered providers
      setFilteredProviders([]);
    }
  }, [rankedProviders, searchTerm]);

  // Initialize filtered providers when ranked providers change
  useEffect(() => {
    if (rankedProviders.length > 0) {
      setFilteredProviders(rankedProviders);
    } else {
      setFilteredProviders([]);
    }
  }, [rankedProviders]);

  const handleProviderClick = (provider: Provider) => {
    navigate(`/doctor/${provider.id}`, { state: { provider } });
  };

  // Pagination logic
  const indexOfLastProvider = currentPage * providersPerPage;
  const indexOfFirstProvider = indexOfLastProvider - providersPerPage;
  const currentProviders = filteredProviders.slice(indexOfFirstProvider, indexOfLastProvider);
  const totalPages = Math.ceil(filteredProviders.length / providersPerPage);

  const handlePageChange = (pageNumber: number) => {
    setCurrentPage(pageNumber);
    // Scroll to top when page changes
    window.scrollTo({ top: 0, behavior: 'smooth' });
    saveFilterState();
  };

  const handleRegenerateDiagnoses = async (useCustomPrompt: boolean = false) => {
    try {
      // Note: This function regenerates ICD codes and search query (treatment options removed)
      
      // Get original request data from searchParams or location.state
      if (!searchParams) {
        alert('Unable to regenerate: Search parameters not found');
        return;
      }
      
      // Use custom prompt if rerunning with edited prompt, otherwise use default (undefined)
      const customPrompt = useCustomPrompt && editableDiagnosesPromptText ? editableDiagnosesPromptText : undefined;
      
      // Call medical analysis API with custom prompt
      // Get data from searchParams or fallback to location.state
      const response = await getMedicalAnalysis({
        diagnosis: searchParams.diagnosis || location.state?.diagnosis || '',
        anatomical_location: searchParams?.anatomical_location || location.state?.anatomical_location || '',
        files: [], // Files are not persisted, so we can't include them in rerun
        custom_diagnoses_prompt: customPrompt
      });
      
      // Update searchParams with new results
      if (response.patient_profile) {
        console.log('🔍 [Frontend] Medical analysis response received:', {
          predicted_icd10: response.patient_profile.predicted_icd10,
          predicted_icd10_codes: response.patient_profile.predicted_icd10_codes,
          predicted_icd10_codes_type: typeof response.patient_profile.predicted_icd10_codes,
          predicted_icd10_codes_isArray: Array.isArray(response.patient_profile.predicted_icd10_codes),
          predicted_icd10_codes_length: response.patient_profile.predicted_icd10_codes?.length,
          icd10_relevancy_scores: response.patient_profile.icd10_relevancy_scores,
          full_patient_profile: response.patient_profile
        });
        
        const newSearchParams: SearchParams = {
          ...searchParams!,
          predicted_icd10: response.patient_profile.predicted_icd10,
          predicted_icd10_codes: response.patient_profile.predicted_icd10_codes,
          icd10_relevancy_scores: response.patient_profile.icd10_relevancy_scores,
          icd10_llm_descriptions: response.patient_profile.icd10_llm_descriptions,
          icd10_description: response.patient_profile.icd10_description,
          icd10_descriptions: response.patient_profile.icd10_descriptions,
          icd10_prompt_text: response.patient_profile.icd10_prompt_text,
          icd10_scoring_prompt_text: response.patient_profile.icd10_scoring_prompt_text,
          treatment_options: response.patient_profile.treatment_options,
          search_query: response.patient_profile.search_query,
          search_query_diagnostic_terms: response.patient_profile.search_query_diagnostic_terms,
          search_query_anatomic_terms: response.patient_profile.search_query_anatomic_terms,
          diagnoses_prompt_text: response.patient_profile.diagnoses_prompt_text,
          search_query_prompt_text: response.patient_profile.search_query_prompt_text,
          llm_provider: response.patient_profile.llm_provider
        };
        
        console.log('🔍 [Frontend] Setting searchParams with:', {
          predicted_icd10: newSearchParams.predicted_icd10,
          predicted_icd10_codes: newSearchParams.predicted_icd10_codes,
          predicted_icd10_codes_type: typeof newSearchParams.predicted_icd10_codes,
          predicted_icd10_codes_isArray: Array.isArray(newSearchParams.predicted_icd10_codes),
          predicted_icd10_codes_length: newSearchParams.predicted_icd10_codes?.length,
          icd10_relevancy_scores: newSearchParams.icd10_relevancy_scores
        });
        
        setSearchParams(newSearchParams);
        
        // Update prompt text state
        if (response.patient_profile.diagnoses_prompt_text) {
          setDiagnosesPromptText(response.patient_profile.diagnoses_prompt_text);
          // Only update editable prompt if we used the default (not custom), otherwise keep the edited version
          if (!useCustomPrompt) {
            setEditableDiagnosesPromptText(response.patient_profile.diagnoses_prompt_text);
          }
        }
        
        // Update ICD-10 prompt text state
        if (response.patient_profile.icd10_prompt_text) {
          setIcd10PromptText(response.patient_profile.icd10_prompt_text);
          setEditableIcd10PromptText(response.patient_profile.icd10_prompt_text);
        }
        
        // Update search query prompt text state
        if (response.patient_profile.search_query_prompt_text) {
          setSearchQueryPromptText(response.patient_profile.search_query_prompt_text);
          // Only update editable prompt if we used the default (not custom), otherwise keep the edited version
          if (!useCustomPrompt) {
            setEditableSearchQueryPromptText(response.patient_profile.search_query_prompt_text);
          }
        }
        
        console.log('✅ Regenerated medical analysis');
      }
    } catch (error) {
      console.error('Error regenerating diagnoses:', error);
      alert('Failed to regenerate medical analysis. Please try again.');
    }
  };

  const handleRegenerateICD10 = async (useCustomPrompt: boolean = false) => {
    try {
      setIsRegeneratingICD10(true);
      
      // Get required data from searchParams
      if (!searchParams) {
        alert('Unable to regenerate: Search parameters not found');
        return;
      }
      
      if (!searchParams.diagnosis) {
        alert('Diagnosis is required to regenerate ICD-10 code');
        return;
      }
      
      // Show warning if search query or CPT codes exist
      if (searchParams.search_query || (cptCodes && cptCodes.length > 0)) {
        const confirmed = window.confirm(
          'Warning: Regenerating the ICD-10 code may affect search query and CPT code generation. ' +
          'You may need to regenerate those after this. Continue?'
        );
        if (!confirmed) {
          return;
        }
      }
      
      // Use custom prompt if rerunning with edited prompt, otherwise use default (undefined)
      const customPrompt = useCustomPrompt && editableIcd10PromptText ? editableIcd10PromptText : undefined;
      
      // Call ICD-10 code generation API
      const response = await regenerateICD10Code({
        diagnosis: searchParams.diagnosis,
        anatomical_location: searchParams.anatomical_location,
        llm_provider: searchParams.llm_provider,
        custom_prompt: customPrompt
      });
      
      // Update searchParams with new ICD-10 code and both prompts
      const newSearchParams: SearchParams = {
        ...searchParams,
        predicted_icd10: response.predicted_icd10 || undefined,
        predicted_icd10_codes: response.predicted_icd10_codes || undefined,
        icd10_relevancy_scores: response.icd10_relevancy_scores || undefined,
        icd10_llm_descriptions: response.icd10_llm_descriptions || undefined,
        icd10_description: response.icd10_description || undefined,
        icd10_descriptions: response.icd10_descriptions || undefined,
        icd10_prompt_text: response.icd10_prompt_text,
        icd10_scoring_prompt_text: response.icd10_scoring_prompt_text
      };
      setSearchParams(newSearchParams);
      
      // Update prompt text state (step 1 only; step 2 is display-only)
      if (response.icd10_prompt_text) {
        setIcd10PromptText(response.icd10_prompt_text);
        if (!useCustomPrompt) {
          setEditableIcd10PromptText(response.icd10_prompt_text);
        }
      }
      
      console.log('✅ Regenerated ICD-10 code');
    } catch (error) {
      console.error('Error regenerating ICD-10 code:', error);
      alert('Failed to regenerate ICD-10 code. Please try again.');
    } finally {
      setIsRegeneratingICD10(false);
    }
  };

  const handleRegenerateSearchQuery = async (useCustomPrompt: boolean = false) => {
    try {
      setIsRegeneratingSearchQuery(true);
      
      // Get required data from searchParams
      if (!searchParams) {
        alert('Unable to regenerate: Search parameters not found');
        return;
      }
      
      if (!searchParams.diagnosis) {
        alert('Diagnosis is required to regenerate search query');
        return;
      }
      
      // Show warning if CPT codes exist
      const existingCptCodes = getExistingCptCodes();
      if (existingCptCodes && existingCptCodes.length > 0) {
        const confirmed = window.confirm(
          'Warning: Regenerating the search query may affect CPT code generation. ' +
          'You may need to regenerate CPT codes after this. Continue?'
        );
        if (!confirmed) {
          return;
        }
      }
      
      // Use custom prompt if rerunning with edited prompt, otherwise use default (undefined)
      const customPrompt = useCustomPrompt && editableSearchQueryPromptText ? editableSearchQueryPromptText : undefined;
      
      // Call search query generation API
      const response = await generateSearchQuery({
        user_diagnosis: searchParams.diagnosis,
        anatomical_location: searchParams.anatomical_location,
        llm_provider: searchParams.llm_provider,
        custom_prompt: customPrompt
      });
      
      // Update searchParams with new search query and parsed terms (API doesn't return parsed terms)
      const parsed = parseSearchQuery(response.search_query);
      const newSearchParams: SearchParams = {
        ...searchParams,
        search_query: response.search_query,
        search_query_diagnostic_terms: parsed.diagnostic,
        search_query_anatomic_terms: parsed.anatomic,
        search_query_prompt_text: response.search_query_prompt_text
      };
      setSearchParams(newSearchParams);
      
      // Update prompt text state
      if (response.search_query_prompt_text) {
        setSearchQueryPromptText(response.search_query_prompt_text);
        // Only update editable prompt if we used the default (not custom), otherwise keep the edited version
        if (!useCustomPrompt) {
          setEditableSearchQueryPromptText(response.search_query_prompt_text);
        }
      }
      
      console.log('✅ Regenerated search query');
    } catch (error) {
      console.error('Error regenerating search query:', error);
      alert('Failed to regenerate search query. Please try again.');
    } finally {
      setIsRegeneratingSearchQuery(false);
    }
  };

  const handleGenerateCPTCodes = async (useCustomPrompt: boolean = false) => {
    try {
      setIsGeneratingCPTCodes(true);
      
      console.log(`🚀 [Frontend] ===== Starting CPT Code Generation =====`);
      console.log(`   - Mode: GPT generation + categorization in single call (treatment options removed)`);
      console.log(`   - Use custom prompt: ${useCustomPrompt}`);
      
      // Get search query from current data
      const searchQuery = searchParams?.search_query || location.state?.aiRecommendations?.patient_profile?.search_query;
      
      if (!searchQuery) {
        console.error(`❌ [Frontend] Missing search query - cannot generate CPT codes`);
        alert('Search query is required to generate CPT codes');
        return;
      }
      
      console.log(`   - Search query available: Yes`);
      
      // Get ICD-10 code(s) if available - handle both single code (string) and multiple codes (array)
      const icd10CodeOrCodes = searchParams?.predicted_icd10 || location.state?.aiRecommendations?.patient_profile?.predicted_icd10;
      const icd10CodesList = searchParams?.predicted_icd10_codes || location.state?.aiRecommendations?.patient_profile?.predicted_icd10_codes;
      
      // Use list if available, otherwise use single code (for backward compatibility)
      const icd10Codes = icd10CodesList && Array.isArray(icd10CodesList) && icd10CodesList.length > 0
        ? icd10CodesList
        : (icd10CodeOrCodes ? [icd10CodeOrCodes] : []);
      
      // Query database CPT codes once (same for all categories since they're based on ICD-10)
      let dbCptCodesResult: Array<{ code: string; description: string }> = [];
      if (icd10Codes.length > 0) {
        try {
          // Join multiple codes with comma for API call
          const icd10CodesStr = icd10Codes.join(',');
          console.log(`🔍 Querying database for CPT codes from ICD-10 codes: ${icd10CodesStr} (once for all categories)...`);
          const dbResponse = await api.get(`/api/v1/medical-analysis/cpt-codes-by-icd10/${encodeURIComponent(icd10CodesStr)}`);
          dbCptCodesResult = dbResponse.data.cpt_codes || [];
          console.log(`✅ Found ${dbCptCodesResult.length} database CPT codes from ${icd10Codes.length} ICD-10 code(s)`);
          
          // Categorize database CPT codes using GPT
          if (dbCptCodesResult.length > 0) {
            try {
              console.log(`🔍 Categorizing ${dbCptCodesResult.length} database CPT codes using GPT...`);
              const categorizeResponse = await categorizeCPTCodes({
                cpt_codes: dbCptCodesResult,
                treatment_options: [],  // Empty array - not used but required for API
                search_query: searchQuery
              });
              
              // Update dbCptCodesResult with categorized codes
              dbCptCodesResult = categorizeResponse.categorized_cpt_codes || dbCptCodesResult;
              
              // Store the prompt text
              if (categorizeResponse.categorization_prompt_text) {
                setCategorizationPromptText(categorizeResponse.categorization_prompt_text);
                setEditableCategorizationPromptText(categorizeResponse.categorization_prompt_text);
              }
              
              console.log(`✅ Categorized ${categorizeResponse.count} database CPT codes`);
            } catch (error) {
              console.error(`❌ Error categorizing database CPT codes:`, error);
              // Continue with uncategorized codes if categorization fails
            }
          }
        } catch (error) {
          console.error(`❌ Error querying database CPT codes:`, error);
          // Continue with GPT generation even if DB query fails
        }
      }
      
      // Generate and categorize CPT codes in a single GPT call (no treatment options needed)
      const customPrompt = useCustomPrompt && editablePromptText ? editablePromptText : undefined;
      
      console.log(`🚀 [Frontend] Starting GPT CPT code generation and categorization`);
      console.log(`   - Search query: ${searchQuery?.substring(0, 100)}...`);
      console.log(`   - Anatomical location: ${searchParams?.anatomical_location || 'Not specified'}`);
      console.log(`   - Using custom prompt: ${customPrompt ? 'Yes' : 'No'}`);
      console.log(`   - Treatment options: REMOVED (not needed for GPT CPT generation)`);
      
      try {
        const startTime = Date.now();
        const response = await generateCPTCodes({
          search_query: searchQuery,
          anatomical_location: searchParams?.anatomical_location,
          llm_provider: searchParams?.llm_provider,
          custom_prompt: customPrompt
        });
        const elapsed = Date.now() - startTime;
        
        console.log(`✅ [Frontend] GPT CPT code generation completed in ${elapsed}ms`);
        console.log(`   - Received ${response.cpt_codes?.length || 0} CPT codes`);
        console.log(`   - All codes come pre-categorized from GPT`);
        
        if (response.cpt_codes && response.cpt_codes.length > 0) {
          // Group GPT codes by category (they come pre-categorized)
          const newCptCodesByCategory: { [category: string]: Array<{ code: string; description: string; category?: string; relevancy_score?: number }> } = {};
          const newCptPromptTextByCategory: { [category: string]: string } = {};
          const categoryStats: { [category: string]: { count: number; avgRelevancy: number; relevancySum: number } } = {};
          
          response.cpt_codes.forEach((cpt: any) => {
            const category = cpt.category || 'Medical';
            if (!newCptCodesByCategory[category]) {
              newCptCodesByCategory[category] = [];
              categoryStats[category] = { count: 0, avgRelevancy: 0, relevancySum: 0 };
            }
            newCptCodesByCategory[category].push(cpt);
            categoryStats[category].count++;
            if (cpt.relevancy_score !== undefined) {
              categoryStats[category].relevancySum += cpt.relevancy_score || 0;
            }
          });
          
          // Calculate averages
          Object.keys(categoryStats).forEach(cat => {
            const stats = categoryStats[cat];
            stats.avgRelevancy = stats.relevancySum / stats.count;
          });
          
          // Store prompt text for all categories (same generation prompt used for all)
          Object.keys(newCptCodesByCategory).forEach(category => {
            newCptPromptTextByCategory[category] = response.cpt_prompt_text || '';
            setEditablePromptTextByCategory(prev => ({
              ...prev,
              [category]: response.cpt_prompt_text || ''
            }));
          });
          setCptPromptText(response.cpt_prompt_text || null);
          setEditablePromptText(response.cpt_prompt_text || null);
          setCptCategorizationPromptText(response.cpt_categorization_prompt_text || null);
          
          // Store database descriptions from cpt_consolidated for GPT codes
          if (response.cpt_db_descriptions && Object.keys(response.cpt_db_descriptions).length > 0) {
            setCptDbDescriptions(response.cpt_db_descriptions);
          } else {
            setCptDbDescriptions({});
          }
          
          // Update state with all categories
          setCptCodesByCategory(newCptCodesByCategory);
          setCptPromptTextByCategory(newCptPromptTextByCategory);
          
          console.log(`✅ [Frontend] Successfully processed GPT CPT codes`);
          console.log(`   - Total codes: ${response.cpt_codes.length}`);
          console.log(`   - Categories: ${Object.keys(newCptCodesByCategory).join(', ')}`);
          console.log(`   - Category distribution:`, Object.entries(categoryStats).map(([cat, stats]) => 
            `${cat}: ${stats.count} codes (avg relevancy: ${stats.avgRelevancy.toFixed(1)}%)`
          ).join(', '));
          console.log(`   - All codes have category and relevancy_score from GPT`);
          
          // Store database CPT codes grouped by category (now that they're categorized)
          if (dbCptCodesResult.length > 0) {
            // Group categorized codes by category
            const newDbCptCodesByCategory: { [category: string]: Array<{ code: string; description: string; relevancy_score?: number }> } = {};
            
            dbCptCodesResult.forEach(cpt => {
              const category = (cpt as any).category || 'Medical'; // Default to Medical if no category
              if (!newDbCptCodesByCategory[category]) {
                newDbCptCodesByCategory[category] = [];
              }
              newDbCptCodesByCategory[category].push({
                code: cpt.code,
                description: cpt.description,
                relevancy_score: (cpt as any).relevancy_score
              });
            });
            
            setDbCptCodesByCategory(prev => ({ ...prev, ...newDbCptCodesByCategory }));
            
            // Set the combined database CPT codes
            setDbCptCodes(dbCptCodesResult);
            console.log(`✅ Stored ${dbCptCodesResult.length} categorized database CPT codes across ${Object.keys(newDbCptCodesByCategory).length} categories`);
            
            // Set first database category as selected if none selected yet and we're on database tab
            if (!selectedCptCategory && Object.keys(newDbCptCodesByCategory).length > 0) {
              setSelectedCptCategory(Object.keys(newDbCptCodesByCategory)[0]);
            }
          }
          
          // Set first GPT category as selected if none selected yet (only if we have GPT codes)
          if (!selectedCptCategory && Object.keys(newCptCodesByCategory).length > 0) {
            setSelectedCptCategory(Object.keys(newCptCodesByCategory)[0]);
          }
          
          // Combine all CPT codes for backward compatibility and CMS API call
          const allCptCodes = Object.values(newCptCodesByCategory).flat() as Array<{ code: string; description: string }>;
          
          // If we have database codes but no GPT codes, switch to database tab
          if (allCptCodes.length === 0 && dbCptCodesResult.length > 0) {
            setActiveCptSourceTab('database');
          }
          if (allCptCodes.length > 0) {
            setCptCodes(allCptCodes);
            
            // Update searchParams to include combined CPT codes and both prompts
            if (searchParams) {
              setSearchParams({
                ...searchParams,
                cpt_codes: allCptCodes,
                cpt_prompt_text: response.cpt_prompt_text,
                cpt_categorization_prompt_text: response.cpt_categorization_prompt_text
              });
            }
            
            console.log(`✅ [Frontend] Generated total ${allCptCodes.length} CPT codes across ${Object.keys(newCptCodesByCategory).length} categories`);
            console.log(`✅ [Frontend] ===== CPT Code Generation Complete =====`);
          }
        } else {
          console.warn(`⚠️  [Frontend] Received 0 GPT CPT codes from API`);
        }
      } catch (error) {
        console.error(`❌ [Frontend] Error in GPT CPT code generation:`, error);
        throw error;
      }
      
    } catch (error) {
      console.error('❌ [Frontend] Fatal error in handleGenerateCPTCodes:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to generate CPT codes: ' + errorMessage);
    } finally {
      setIsGeneratingCPTCodes(false);
      setIsGeneratingCPTCodesForCategory(null);
      console.log(`🏁 [Frontend] CPT code generation process finished`);
    }
  };

  const handleRecategorizeCPTCodes = async (useCustomPrompt: boolean = false) => {
    if (!dbCptCodes || dbCptCodes.length === 0) {
      alert('No database CPT codes available to recategorize');
      return;
    }

    // Get search query for diagnosis terms
    const searchQuery = searchParams?.search_query || location.state?.aiRecommendations?.patient_profile?.search_query;

    try {
      setIsRecategorizingCPTCodes(true);

      // Use custom prompt if rerunning with edited prompt, otherwise use default (undefined)
      const customPrompt = useCustomPrompt && editableCategorizationPromptText ? editableCategorizationPromptText : undefined;

      console.log(`🔍 Recategorizing ${dbCptCodes.length} database CPT codes using GPT...`);
      const categorizeResponse = await categorizeCPTCodes({
        cpt_codes: dbCptCodes,
        treatment_options: [],  // Not used but required for API
        custom_prompt: customPrompt,
        search_query: searchQuery
      });

      // Update categorized codes
      const categorizedCodes = categorizeResponse.categorized_cpt_codes || dbCptCodes;

      // Store the prompt text
      if (categorizeResponse.categorization_prompt_text) {
        setCategorizationPromptText(categorizeResponse.categorization_prompt_text);
        if (!useCustomPrompt) {
          // Only update editable prompt if not using custom (to preserve user edits)
          setEditableCategorizationPromptText(categorizeResponse.categorization_prompt_text);
        }
      }

      // Group categorized codes by category
      const newDbCptCodesByCategory: { [category: string]: Array<{ code: string; description: string; relevancy_score?: number }> } = {};
      categorizedCodes.forEach(cpt => {
        const category = (cpt as any).category || 'Medical';
        if (!newDbCptCodesByCategory[category]) {
          newDbCptCodesByCategory[category] = [];
        }
        newDbCptCodesByCategory[category].push({
          code: cpt.code,
          description: cpt.description,
          relevancy_score: (cpt as any).relevancy_score
        });
      });

      setDbCptCodesByCategory(newDbCptCodesByCategory);
      setDbCptCodes(categorizedCodes);

      console.log(`✅ Recategorized ${categorizeResponse.count} database CPT codes across ${Object.keys(newDbCptCodesByCategory).length} categories`);
    } catch (error) {
      console.error('❌ Error recategorizing CPT codes:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to recategorize CPT codes: ' + errorMessage);
    } finally {
      setIsRecategorizingCPTCodes(false);
    }
  };

  const handleShowSpecialists = async () => {
    // If specialists are already available, just switch to the view
    if (filteredProviders.length > 0) {
      setActiveView('specialists');
      return;
    }

    // Check if CPT codes are available using helper function
    const existingCptCodes = getExistingCptCodes();
    
    if (!existingCptCodes) {
      alert('Please generate CPT codes first before getting specialist recommendations');
      return;
    }

    // If specialists haven't been generated yet, call the APIs
    try {
      setIsGeneratingSpecialists(true);
      
      // Step 1: Get specialist recommendations
      // Reuse medical analysis results from first step to avoid duplicate GPT calls
      const patientProfile = location.state?.aiRecommendations?.patient_profile;
      const specialistRequest: SpecialistRecommendationRequest = {
        diagnosis: searchParams?.diagnosis || '',
        state: searchParams?.state || location.state?.state || '',
        files: [],
        cpt_codes: existingCptCodes,  // Pass existing CPT codes to reuse them
        // Pass medical analysis results to reuse (avoids duplicate GPT calls)
        treatment_options: [],  // Treatment options no longer generated - pass empty array
        predicted_icd10: patientProfile?.predicted_icd10,
        icd10_description: patientProfile?.icd10_description,
        search_query: patientProfile?.search_query,
        determined_specialty: searchParams?.determined_specialty || patientProfile?.determined_specialty
      };

      if (existingCptCodes && existingCptCodes.length > 0) {
        console.log('♻️ [Frontend] Reusing', existingCptCodes.length, 'CPT codes for specialist recommendations');
      }
      if (specialistRequest.treatment_options && specialistRequest.treatment_options.length > 0) {
        console.log('♻️ [Frontend] Reusing', specialistRequest.treatment_options.length, 'treatment options from medical analysis');
      }
      if (specialistRequest.search_query) {
        console.log('♻️ [Frontend] Reusing search_query from medical analysis');
      }
      if (specialistRequest.determined_specialty) {
        console.log('♻️ [Frontend] Reusing determined_specialty from medical analysis:', specialistRequest.determined_specialty);
      }

      const specialistResponse = await getSpecialistRecommendations(specialistRequest);
      
      // Store the specialist response for debug display
      setSpecialistRecommendationData(specialistResponse);
      
      // Step 2: Search for NPI providers
      // Must pass pre-determined values from medical analysis (required - no fallback)
      const determinedSpecialty = searchParams?.determined_specialty || location.state?.aiRecommendations?.patient_profile?.determined_specialty;
      if (!determinedSpecialty) {
        alert('Error: Missing specialty information from medical analysis. Please start a new search.');
        setIsGeneratingSpecialists(false);
        return;
      }
      
      const npiSearchRequest: NPISearchRequest = {
        state: searchParams?.state || '',
        city: searchParams?.city || '',
        zipCode: location.state?.zipCode || '',
        proximity: location.state?.proximity || 'statewide',
        diagnosis: searchParams?.diagnosis || '',
        uploadedFiles: [],
        // Required: Pass pre-determined values from medical analysis
        determined_specialty: determinedSpecialty,
        predicted_icd10: searchParams?.predicted_icd10 || location.state?.aiRecommendations?.patient_profile?.predicted_icd10,
        icd10_description: searchParams?.icd10_description || location.state?.aiRecommendations?.patient_profile?.icd10_description
      };

      const npiData = await searchNPIProviders(npiSearchRequest);
      
      // Step 3: Rank NPI providers using specialist information
      console.log('🔍 [Frontend] CMS Data Check Before Ranking:');
      console.log('  - specialistResponse.cms_data exists?', !!specialistResponse.cms_data);
      if (specialistResponse.cms_data) {
        console.log('  - cms_data keys:', Object.keys(specialistResponse.cms_data));
        const cmsDataAny = specialistResponse.cms_data as any;
        console.log('  - cms_data.top_25_npis?', cmsDataAny.top_25_npis);
        console.log('  - cms_data.top_25_npis length:', cmsDataAny.top_25_npis?.length || 0);
        if (cmsDataAny.top_25_npis && cmsDataAny.top_25_npis.length > 0) {
          console.log('  - First 5 top_25_npis:', cmsDataAny.top_25_npis.slice(0, 5));
        }
      } else {
        console.warn('  ⚠️  NO CMS DATA AVAILABLE FOR RANKING');
      }
      
      // Extract search_query from specialistResponse (it should be in patient_profile.search_query)
      const searchQueryFromPatientProfile = specialistResponse?.patient_profile?.search_query;
      const searchQueryFromTopLevel = specialistResponse?.search_query;
      const searchQueryFromParams = searchParams?.search_query;
      const searchQueryFromState = location.state?.aiRecommendations?.patient_profile?.search_query;
      
      const searchQuery = searchQueryFromPatientProfile 
        || searchQueryFromTopLevel 
        || searchQueryFromParams 
        || searchQueryFromState;
      
      console.log('🔍 [Frontend] Extracting search_query for ranking:');
      console.log('  - specialistResponse.patient_profile.search_query:', searchQueryFromPatientProfile?.substring(0, 150) || 'NOT FOUND');
      console.log('  - specialistResponse.search_query:', searchQueryFromTopLevel?.substring(0, 150) || 'NOT FOUND');
      console.log('  - searchParams.search_query:', searchQueryFromParams?.substring(0, 150) || 'NOT FOUND');
      console.log('  - location.state.aiRecommendations.patient_profile.search_query:', searchQueryFromState?.substring(0, 150) || 'NOT FOUND');
      console.log('  - FINAL search_query being sent:', searchQuery?.substring(0, 150) || 'NOT FOUND');
      console.log('  - specialistResponse keys:', Object.keys(specialistResponse || {}));
      console.log('  - patient_profile keys:', Object.keys(specialistResponse?.patient_profile || {}));
      
      // If search_query is not found, log the full patient_profile to debug
      if (!searchQuery && specialistResponse?.patient_profile) {
        console.warn('⚠️ [Frontend] search_query NOT FOUND - logging full patient_profile:');
        console.warn('  - patient_profile:', JSON.stringify(specialistResponse.patient_profile, null, 2).substring(0, 500));
      }
      
      const rankingRequest: NPIRankingRequest = {
        npi_providers: npiData.providers,
        patient_input: `Diagnosis: ${searchParams?.diagnosis}`,
        shared_specialist_information: specialistResponse.shared_specialist_information || [],
        cms_data: specialistResponse.cms_data, // Pass CMS data for clinical volume bonus
        search_query: searchQuery // Pass search_query from first analysis (same as used for PubMed)
      };

      console.log('🔍 [Frontend] Ranking request cms_data:', rankingRequest.cms_data ? 'PRESENT' : 'MISSING');
      
      const rankingResponse = await rankNPIProviders(rankingRequest);
      
      // Handle new treatment-specific ranking structure
      const treatmentRankingsData = rankingResponse.treatment_rankings;
      let rankedNPIProviders: NPIProvider[] = [];
      let providerLinks: { [npi: string]: ProviderContent } = {};
      const providerLookup = new Map(npiData.providers.map((provider: Provider) => [provider.npi, provider]));
      
      if (treatmentRankingsData && Object.keys(treatmentRankingsData).length > 0) {
        console.log('🔍 Treatment rankings data received:', treatmentRankingsData);
        
        // Store treatment rankings for filtering
        setTreatmentRankings(treatmentRankingsData);
        
        // Combine all providers and links from all treatments (same logic as category filter)
        const allRankedNPIs = new Set<string>();
        const allProviderLinks: { [npi: string]: ProviderContent } = {};
        const allProviderScores: { [npi: string]: any } = {};
        
        Object.values(treatmentRankingsData).forEach((treatment: any) => {
          if (treatment.ranked_providers) {
            treatment.ranked_providers.forEach((npi: string) => allRankedNPIs.add(npi));
          }
          if (treatment.provider_links) {
            Object.assign(allProviderLinks, treatment.provider_links);
          }
          if (treatment.provider_scores) {
            Object.entries(treatment.provider_scores).forEach(([npi, scoreData]: [string, any]) => {
              if (!allProviderScores[npi]) {
                // Deep copy the score data so we can modify it without affecting the original
                allProviderScores[npi] = JSON.parse(JSON.stringify(scoreData));
              }
            });
          }
        });
        
        rankedNPIProviders = Array.from(allRankedNPIs).map((npi: string) => 
          providerLookup.get(npi)
        ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
        
        setRankedProviders(rankedNPIProviders);
        console.log('🔍 Ranked providers from all treatments:', rankedNPIProviders.length);
        
        // Capture the provider links and scores
        providerLinks = allProviderLinks;
        const providerScores = allProviderScores;
        
        console.log('🔍 [Frontend] Provider Scores Received:');
        console.log('  - Total providers with scores:', Object.keys(providerScores).length);
        
        // Check for clinical volume points in scores
        let providersWithClinicalVolume = 0;
        const sampleProvidersWithClinicalVolume: string[] = [];
        Object.entries(providerScores).forEach(([npi, scoreData]: [string, any]) => {
          const scoreDataAny = scoreData as any;
          const clinicalVol = scoreDataAny?.clinical_volume_points || 0;
          if (clinicalVol > 0) {
            providersWithClinicalVolume++;
            if (sampleProvidersWithClinicalVolume.length < 5) {
              sampleProvidersWithClinicalVolume.push(`${npi}: ${clinicalVol} points`);
            }
          }
        });
        
        console.log('  - Providers with clinical_volume_points > 0:', providersWithClinicalVolume);
        if (sampleProvidersWithClinicalVolume.length > 0) {
          console.log('  - Sample providers with clinical volume:', sampleProvidersWithClinicalVolume);
        } else {
          console.warn('  ⚠️  NO PROVIDERS FOUND WITH CLINICAL VOLUME POINTS');
          
          // Log first 5 providers' scores for debugging
          const first5Npis = Object.keys(providerScores).slice(0, 5);
          console.log('  - First 5 providers score data:');
          first5Npis.forEach(npi => {
            const scoreData = providerScores[npi] as any;
            console.log(`    ${npi}:`, {
              score: scoreData?.score,
              clinical_volume_points: scoreData?.clinical_volume_points,
              hasClinicalVolume: !!(scoreData?.clinical_volume_points && scoreData.clinical_volume_points > 0)
            });
          });
        }
        
        setProviderScores(providerScores);
      }
      
      // Update state with ranked providers and original NPI data
      setProviders(npiData.providers); // Store original NPI providers for filtering
      setRankedProviders(rankedNPIProviders);
      setProviderLinks(providerLinks);
      
      // Switch to specialists view after loading providers
      setActiveView('specialists');
      
    } catch (error) {
      console.error('Error fetching specialist recommendations:', error);
      // You might want to show an error message to the user here
    } finally {
      setIsGeneratingSpecialists(false);
    }
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

  const handleCategoryFilterChange = (category: string, _treatmentsByCategory?: { [category: string]: Array<{ id: string; treatment: any }> }) => {
    console.log('🔍 Category filter changed to:', category);
    
    // Always show ALL providers from all treatments (combine all ranked providers)
    const allRankedNPIs = new Set<string>();
    const allProviderLinks: { [npi: string]: ProviderContent } = {};
    
    // Collect all providers and links from all treatments
    Object.values(treatmentRankings).forEach((treatment: any) => {
      if (treatment.ranked_providers) {
        treatment.ranked_providers.forEach((npi: string) => allRankedNPIs.add(npi));
      }
      if (treatment.provider_links) {
        Object.assign(allProviderLinks, treatment.provider_links);
      }
    });
    
    const originalProviders = providers || [];
    const allProviders = Array.from(allRankedNPIs).map((npi: string) => 
      originalProviders.find((provider: Provider) => provider.npi === npi)
    ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
    
    // Now filter scores based on category
    // First, merge ALL scores from ALL treatments (scores should be same across treatments except clinical volume)
    let filteredProviderScores: { [npi: string]: any } = {};
    
    // Merge all scores from all treatments - use first complete score we find for each provider
    Object.values(treatmentRankings).forEach((treatment: any) => {
      if (treatment.provider_scores) {
        Object.entries(treatment.provider_scores).forEach(([npi, scoreData]: [string, any]) => {
          if (!filteredProviderScores[npi]) {
            // Deep copy the score data so we can modify it without affecting the original
            filteredProviderScores[npi] = JSON.parse(JSON.stringify(scoreData));
          }
          // If we already have scores for this provider, keep the existing ones
          // (scores should be same across treatments except clinical volume, so first wins)
        });
      }
    });
    
    // Handle category filtering - modify ONLY clinical volume based on category-specific CPT codes
    if (category && category !== 'All') {
      // Modify ONLY clinical volume based on category-specific CPT codes
      const categoryCptCodes = cptCodesByCategory[category] || [];
      const categoryCptCodeSet = new Set(categoryCptCodes.map(cpt => cpt.code));
      
      // Get CMS data to filter clinical volume by category
      const cmsData = specialistRecommendationData?.cms_data || location.state?.aiRecommendations?.cms_data;
      
      // Get user's neurosurgeon NPIs to filter out entities/facilities
      const userProviderNPIs = new Set(
        (providers || location.state?.providers || []).map((p: Provider) => String(p.npi))
      );
      
      const cmsProvidersByNpi: { [npi: string]: any } = {};
      if (cmsData?.results) {
        cmsData.results.forEach((provider: any) => {
          const npi = String(provider.Rndrng_NPI || '');
          // ONLY include providers that are in the user's search (neurosurgeons)
          // This prevents entities/facilities like "Yorkville Endoscopy, Llc" from being included
          if (npi && userProviderNPIs.has(npi)) {
            if (!cmsProvidersByNpi[npi]) {
              cmsProvidersByNpi[npi] = [];
            }
            cmsProvidersByNpi[npi].push(provider);
          }
        });
      }
      
      // First, calculate the max Tot_Srvcs for this category across all providers
      // This ensures all providers are compared against the same max value
      // NOTE: Now filtered to only neurosurgeons from user's search (entities excluded)
      const providerCategoryTotSrvcs: { [npi: string]: number } = {};
      
      // Calculate Tot_Srvcs per provider for this category
      // CMS data has one row per provider-CPT code combination, so we need to sum Tot_Srvcs
      // for each provider where the CPT code matches the selected category
      Object.keys(cmsProvidersByNpi).forEach(providerNpi => {
        // Double-check: only process neurosurgeons (should already be filtered above, but safety check)
        if (!userProviderNPIs.has(providerNpi)) {
          return; // Skip entities/facilities
        }
        
        const providerData = cmsProvidersByNpi[providerNpi];
        let providerCategoryTotal = 0;
        
        // Sum Tot_Srvcs for this provider's CPT codes that match the selected category
        providerData.forEach((p: any) => {
          const codes = Array.isArray(p.HCPCS_Codes) ? p.HCPCS_Codes : [];
          // Check if any of this row's CPT codes are in the selected category
          if (codes.some((code: string) => categoryCptCodeSet.has(code))) {
            providerCategoryTotal += p.Tot_Srvcs || 0;
          }
        });
        
        if (providerCategoryTotal > 0) {
          providerCategoryTotSrvcs[providerNpi] = providerCategoryTotal;
        }
      });
      
      // Find the max Tot_Srvcs for this category (now only from neurosurgeons, not entities)
      const maxCategoryTotSrvcs = Object.values(providerCategoryTotSrvcs).length > 0 
        ? Math.max(...Object.values(providerCategoryTotSrvcs)) 
        : 1;
      
      // Debug logging for category filter
      console.log('🔍 Category filter debug:', {
        category,
        categoryCptCodes: cptCodesByCategory[category]?.map(c => c.code) || [],
        categoryCptCodesCount: cptCodesByCategory[category]?.length || 0,
        providerCategoryTotSrvcsCount: Object.keys(providerCategoryTotSrvcs).length,
        sampleProviderCategoryTotSrvcs: Object.entries(providerCategoryTotSrvcs).slice(0, 5),
        maxCategoryTotSrvcs,
        totalProvidersToFilter: Object.keys(filteredProviderScores).length
      });
      
      // Now, filter clinical volume based on category CPT codes for each provider
      Object.keys(filteredProviderScores).forEach((npi, index) => {
        const scoreData = filteredProviderScores[npi];
        const categoryTotSrvcs = providerCategoryTotSrvcs[npi] || 0;
        const hasCategoryCptCodes = categoryTotSrvcs > 0;
        
        // Add logging for first few providers
        if (index < 5) {
          const originalCV = scoreData.weighted_breakdown?.breakdown_details?.clinical_volume?.weighted_points || 0;
          const originalRaw = scoreData.weighted_breakdown?.breakdown_details?.clinical_volume?.raw || 0;
          console.log(`🔍 Provider ${npi} (${index + 1}/${Math.min(5, Object.keys(filteredProviderScores).length)}): categoryTotSrvcs=${categoryTotSrvcs}, hasCategoryCptCodes=${hasCategoryCptCodes}, originalCV=${originalCV}, originalRaw=${originalRaw}`);
        }
        
        if (hasCategoryCptCodes && scoreData.weighted_breakdown) {
          // Calculate percentage based on max Tot_Srvcs for this category only
          const categoryPct = maxCategoryTotSrvcs > 0 ? (categoryTotSrvcs / maxCategoryTotSrvcs) : 0;
          
          // Calculate percentile for this category
          const categoryTotSrvcsValues = Object.values(providerCategoryTotSrvcs);
          const categoryPercentile = categoryTotSrvcsValues.length > 0 && categoryTotSrvcs > 0
            ? ((categoryTotSrvcsValues.filter(v => v < categoryTotSrvcs).length / categoryTotSrvcsValues.length) * 100)
            : 0;
          
          // Update the weighted breakdown
          if (scoreData.weighted_breakdown.breakdown_details?.clinical_volume) {
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.raw = categoryTotSrvcs;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.max_raw = maxCategoryTotSrvcs;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentage = categoryPct * 100;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points = categoryPct * SCORING_WEIGHTS.CLINICAL_VOLUME;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentile = Math.round(categoryPercentile * 100) / 100; // Round to 2 decimal places
            
            // Recalculate final score
            const cv = scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points || 0;
            const pubmed = scoreData.weighted_breakdown.breakdown_details.pubmed?.weighted_points || 0;
            const training = scoreData.weighted_breakdown.breakdown_details.training?.weighted_points || 0;
            const experience = scoreData.weighted_breakdown.breakdown_details.experience?.weighted_points || 0;
            const vumedi = scoreData.weighted_breakdown.breakdown_details.vumedi?.weighted_points || 0;
            scoreData.weighted_breakdown.final_score = cv + pubmed + training + experience + vumedi;
            scoreData.score = scoreData.weighted_breakdown.final_score;
          }
        } else {
          // Provider doesn't have CPT codes in this category - set clinical volume to 0
          if (scoreData.weighted_breakdown?.breakdown_details?.clinical_volume) {
            const beforeCV = scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points || 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.raw = 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.max_raw = maxCategoryTotSrvcs; // Still set max so percentage calculation is correct
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentage = 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points = 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentile = 0;
            
            // Recalculate final score without clinical volume
            const pubmed = scoreData.weighted_breakdown.breakdown_details.pubmed?.weighted_points || 0;
            const training = scoreData.weighted_breakdown.breakdown_details.training?.weighted_points || 0;
            const experience = scoreData.weighted_breakdown.breakdown_details.experience?.weighted_points || 0;
            const vumedi = scoreData.weighted_breakdown.breakdown_details.vumedi?.weighted_points || 0;
            scoreData.weighted_breakdown.final_score = pubmed + training + experience + vumedi;
            scoreData.score = scoreData.weighted_breakdown.final_score;
            
            // Log for first few providers
            if (index < 5) {
              console.log(`🔍 Provider ${npi}: Set clinical volume to 0 (was ${beforeCV}), new final_score=${scoreData.score}`);
            }
          } else if (index < 5) {
            console.log(`🔍 Provider ${npi}: No weighted_breakdown.breakdown_details.clinical_volume found`);
          }
        }
      });
    } else if (category === 'All') {
      // For "All", restore original max values and recalculate raw from all CPT codes
      const cmsData = specialistRecommendationData?.cms_data || location.state?.aiRecommendations?.cms_data;
      const userProviderNPIs = new Set(
        (providers || location.state?.providers || []).map((p: Provider) => String(p.npi))
      );
      
      // Calculate Tot_Srvcs per provider across ALL CPT codes (not filtered by category)
      const providerAllTotSrvcs: { [npi: string]: number } = {};
      if (cmsData?.results) {
        cmsData.results.forEach((provider: any) => {
          const npi = String(provider.Rndrng_NPI || '');
          if (npi && userProviderNPIs.has(npi)) {
            if (!providerAllTotSrvcs[npi]) {
              providerAllTotSrvcs[npi] = 0;
            }
            providerAllTotSrvcs[npi] += provider.Tot_Srvcs || 0;
          }
        });
      }
      
      // Restore original max and recalculate scores for each provider
      Object.keys(filteredProviderScores).forEach((npi) => {
        const scoreData = filteredProviderScores[npi];
        if (scoreData.weighted_breakdown?.breakdown_details?.clinical_volume) {
          const originalMax = scoreData.weighted_breakdown.breakdown_details.clinical_volume.max;
          const allTotSrvcs = providerAllTotSrvcs[npi] || 0;
          
          // Restore original max (from all CPT codes) and use recalculated raw
          if (originalMax) {
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.raw = allTotSrvcs;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.max_raw = originalMax;
            
            // Recalculate percentage using original max
            const originalPct = originalMax > 0 ? (allTotSrvcs / originalMax) : 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentage = originalPct * 100;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points = originalPct * SCORING_WEIGHTS.CLINICAL_VOLUME;
            
            // Recalculate final score
            const cv = scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points || 0;
            const pubmed = scoreData.weighted_breakdown.breakdown_details.pubmed?.weighted_points || 0;
            const training = scoreData.weighted_breakdown.breakdown_details.training?.weighted_points || 0;
            const experience = scoreData.weighted_breakdown.breakdown_details.experience?.weighted_points || 0;
            const vumedi = scoreData.weighted_breakdown.breakdown_details.vumedi?.weighted_points || 0;
            scoreData.weighted_breakdown.final_score = cv + pubmed + training + experience + vumedi;
            scoreData.score = scoreData.weighted_breakdown.final_score;
          }
        }
      });
      console.log('🔍 Showing all categories - using original max values from all CPT codes, recalculated raw values');
    }
    
    // Sort providers by their total score (descending) after updating scores
    const sortedProviders = [...allProviders].sort((a, b) => {
      const scoreA = filteredProviderScores[a.npi]?.score || filteredProviderScores[a.npi]?.weighted_breakdown?.final_score || 0;
      const scoreB = filteredProviderScores[b.npi]?.score || filteredProviderScores[b.npi]?.weighted_breakdown?.final_score || 0;
      return scoreB - scoreA; // Sort descending (highest score first)
    });
    
    setRankedProviders(sortedProviders);
    setProviderLinks(allProviderLinks);
    setProviderScores(filteredProviderScores);
    
    setCurrentPage(1);
    saveFilterState();
  };

  const resetFilters = () => {
    setSearchTerm('');
    setCurrentPage(1);
    saveFilterState();
  };

  const saveFilterState = () => {
    console.log('saveFilterState called with current state:', {
      searchTerm,
      currentPage,
      providersPerPage
    });
    
    const savedData = localStorage.getItem('mdspecialist_search_results');
    if (savedData) {
      try {
        const parsed = JSON.parse(savedData);
        const updatedData = {
          ...parsed,
          filters: {
            searchTerm,
            currentPage,
            providersPerPage
          }
        };
        localStorage.setItem('mdspecialist_search_results', JSON.stringify(updatedData));
        console.log('Filter state saved successfully');
      } catch (error) {
        console.error('Error saving filter state:', error);
      }
    } else {
      console.log('No existing search data to update with filters');
    }
  };

  if (isLoading || isGeneratingSpecialists) {
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
            {isGeneratingSpecialists ? 'Generating specialist recommendations...' : 'Finding specialists in your area...'}
          </h2>
          
          {/* Sleek info card */}
          <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-white/20 p-6 mb-6">
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0">
                <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <div className="flex-1">
                <p className="text-gray-700 text-sm leading-relaxed">
                  <span className="font-semibold text-gray-900">Please wait...</span> {isGeneratingSpecialists 
                    ? 'This process may take 2-3 minutes as we analyze thousands of specialists and match them to your specific needs.'
                    : 'This process may take 1-2 minutes as we analyze thousands of specialists and match them to your specific needs.'}
                </p>
              </div>
            </div>
          </div>
          
          {/* Important notice */}
          <div className="flex items-center justify-center space-x-2 text-gray-600">
            <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <span className="text-sm font-medium">Please do not close this browser tab while we search</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 pb-8">
        {/* Header */}
        {/* Secondary Header Bar */}
        <div className="flex justify-between items-center mb-4 py-4 border-b border-gray-200">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/')}
              className="text-gray-900 hover:text-gray-700 flex items-center"
            >
              ← Back to Search
            </button>
            

          </div>
          
          {/* View Toggle */}
          <div className="flex space-x-8">
            {(searchParams?.icd10_description || location.state?.aiRecommendations?.patient_profile?.icd10_description) && (
              <button
                onClick={() => setActiveView('assessment')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'assessment'
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                </svg>
                <span>Medical Assessment</span>
              </button>
            )}
            {filteredProviders.length > 0 && (
              <button
                onClick={() => setActiveView('specialists')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'specialists'
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <i className="fas fa-user-md h-4 w-4"></i>
                <span>Specialists</span>
              </button>
            )}
            {filteredProviders.length > 0 && specialistRecommendationData && (
              <button
                onClick={() => setActiveView('debug')}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeView === 'debug'
                    ? 'text-primary-600 bg-primary-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                <span>Debug</span>
              </button>
            )}
          </div>
        </div>



                {/* Medical Assessment */}
        {activeView === 'assessment' && (searchParams?.icd10_description || location.state?.aiRecommendations?.patient_profile?.icd10_description) && (
          <>
            {/* Medical Assessment Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                Medical Assessment
              </h1>
            </div>
            
            <div className="mx-auto space-y-6">
              {/* Diagnosis Information */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
                <h2 className="text-2xl font-semibold text-gray-900 mb-4">Diagnosis Analysis</h2>
                
                <div className="space-y-4">
                  {/* User-Entered Diagnosis */}
                  <div className="border-l-4 border-blue-500 pl-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Your Diagnosis</h3>
                    <p className="text-gray-700">{searchParams?.diagnosis || 'No diagnosis provided'}</p>
                  </div>

                  {/* ICD Codes Results */}
                  {(searchParams?.icd10_description || (searchParams?.predicted_icd10_codes && searchParams.predicted_icd10_codes.length > 0)) && (
                    <div className="border-l-4 border-green-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-3">ICD Codes</h3>
                      <div className="max-h-96 overflow-y-auto space-y-2 pr-2">
                        {searchParams.predicted_icd10_codes && Array.isArray(searchParams.predicted_icd10_codes) && searchParams.predicted_icd10_codes.length > 0 ? (
                          // Show all codes with their descriptions in a list format
                          <div className="space-y-1">
                            {searchParams.predicted_icd10_codes.map((code: string, idx: number) => {
                              const llmDescription = searchParams.icd10_llm_descriptions?.[code];
                              const dbDescription = searchParams.icd10_descriptions?.[code];
                              const relevancyScore = searchParams.icd10_relevancy_scores?.[code];
                              return (
                                <div key={idx} className="flex items-start gap-3 py-2 px-2 bg-gray-50 rounded border border-gray-200 min-h-0">
                                  <code className="bg-white px-2 py-1 rounded text-sm font-mono font-semibold text-gray-800 border border-gray-300 flex-shrink-0">
                                    {code}
                                  </code>
                                  {relevancyScore !== undefined && (
                                    <span className="text-xs font-medium text-gray-600 bg-gray-200 px-1.5 py-0.5 rounded flex-shrink-0">
                                      {relevancyScore}%
                                    </span>
                                  )}
                                  <div className="flex-1 min-w-0 text-sm">
                                    {llmDescription && (
                                      <div className="leading-tight">
                                        <span className="text-xs font-semibold text-blue-600 uppercase">LLM DESCRIPTION: </span>
                                        <span className="text-gray-700">{llmDescription}</span>
                                      </div>
                                    )}
                                    {dbDescription && (
                                      <div className="leading-tight mt-0.5">
                                        <span className="text-xs font-semibold text-green-600 uppercase">DATABASE DESCRIPTION: </span>
                                        <span className="text-gray-700">{dbDescription}</span>
                                      </div>
                                    )}
                                    {!llmDescription && !dbDescription && (
                                      <span className="text-gray-500 text-xs">No descriptions available</span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          // Fallback: single code display (backward compatibility)
                          <div className="space-y-2">
                            <div className="flex items-start gap-3 p-2 bg-gray-50 rounded-md">
                              <code className="bg-white px-3 py-1.5 rounded text-sm font-mono font-semibold text-gray-800 border border-gray-300 flex-shrink-0">
                                {searchParams.predicted_icd10 || 'N/A'}
                              </code>
                              <span className="text-gray-700 text-sm flex-1 pt-1">
                                {searchParams.icd10_description || 'Description not available'}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ICD-10 Code Generation — two steps: generation then relevancy scoring */}
                  {(icd10PromptText || searchParams?.icd10_prompt_text) && (
                    <div className="border-l-4 border-green-500 pl-4 space-y-3">
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Step 1: ICD-10 Generation Prompt (codes + descriptions) — Click to view/edit and re-run
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">Prompt sent to GPT to generate ICD-10 codes and brief descriptions (no relevancy yet):</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={editableIcd10PromptText || icd10PromptText || searchParams?.icd10_prompt_text || ''}
                            onChange={(e) => setEditableIcd10PromptText(e.target.value)}
                            placeholder="Prompt text..."
                          />
                          <div className="mt-3 flex justify-end">
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.preventDefault();
                                await handleRegenerateICD10(true);
                              }}
                              disabled={isRegeneratingICD10 || !editableIcd10PromptText}
                              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                            >
                              {isRegeneratingICD10 ? (
                                <span className="flex items-center gap-2">
                                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Regenerating...
                                </span>
                              ) : (
                                'Re-run ICD-10 Code Generation'
                              )}
                            </button>
                          </div>
                        </div>
                      </details>
                      {(searchParams?.icd10_scoring_prompt_text || location.state?.aiRecommendations?.patient_profile?.icd10_scoring_prompt_text) && (
                        <details className="bg-gray-50 rounded-lg border border-gray-200">
                          <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                            <span className="flex items-center gap-2">
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Step 2: Relevancy Scoring Prompt (database descriptions)
                            </span>
                          </summary>
                          <div className="p-4 border-t border-gray-200">
                            <p className="text-xs text-gray-600 mb-2">Prompt sent to GPT to assign relevancy scores using official (database) code descriptions:</p>
                            <pre className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[120px] max-h-[300px] overflow-y-auto whitespace-pre-wrap">
                              {searchParams?.icd10_scoring_prompt_text || location.state?.aiRecommendations?.patient_profile?.icd10_scoring_prompt_text || ''}
                            </pre>
                          </div>
                        </details>
                      )}
                    </div>
                  )}



                  {/* Search Query — show parsed diagnostic and anatomic terms as two lists */}
                  {searchParams?.search_query && (() => {
                    const diagnosticTerms = searchParams.search_query_diagnostic_terms ?? parseSearchQuery(searchParams.search_query).diagnostic;
                    const anatomicTerms = searchParams.search_query_anatomic_terms ?? parseSearchQuery(searchParams.search_query).anatomic;
                    const hasDiagnostic = diagnosticTerms.length > 0;
                    const hasAnatomic = anatomicTerms.length > 0;
                    if (!hasDiagnostic && !hasAnatomic) return null;
                    return (
                      <div className="border-l-4 border-indigo-500 pl-4">
                        <h3 className="text-lg font-medium text-gray-900 mb-2">Search Query Variations</h3>
                        <p className="text-sm text-gray-600 mb-3">Terms used to find relevant specialists (at least one diagnostic and one anatomic match required):</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="bg-indigo-50/60 p-3 rounded-lg border border-indigo-100 flex flex-col min-h-0">
                            <h4 className="text-xs font-semibold text-indigo-700 uppercase tracking-wide mb-2 shrink-0">Diagnostic terms</h4>
                            <div className="min-h-0 max-h-32 overflow-y-auto">
                              {hasDiagnostic ? (
                                <ul className="text-sm text-gray-800 space-y-1">
                                  {diagnosticTerms.map((t, i) => (
                                    <li key={i} className="flex items-center gap-2">
                                      <span className="text-indigo-500">•</span>
                                      <span>{t}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-sm text-gray-500 italic">None</p>
                              )}
                            </div>
                          </div>
                          <div className="bg-amber-50/60 p-3 rounded-lg border border-amber-100 flex flex-col min-h-0">
                            <h4 className="text-xs font-semibold text-amber-800 uppercase tracking-wide mb-2 shrink-0">Anatomic terms</h4>
                            <div className="min-h-0 max-h-32 overflow-y-auto">
                              {hasAnatomic ? (
                                <ul className="text-sm text-gray-800 space-y-1">
                                  {anatomicTerms.map((t, i) => (
                                    <li key={i} className="flex items-center gap-2">
                                      <span className="text-amber-600">•</span>
                                      <span>{t}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="text-sm text-gray-500 italic">None</p>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Search Query Generation Prompt (collapsed by default) */}
                  {(searchQueryPromptText || searchParams?.search_query_prompt_text) && (
                    <div className="border-l-4 border-indigo-500 pl-4">
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Search Query Generation Prompt (Click to view/edit and re-run)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to generate the search query:</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={editableSearchQueryPromptText || searchQueryPromptText || searchParams?.search_query_prompt_text || ''}
                            onChange={(e) => setEditableSearchQueryPromptText(e.target.value)}
                            placeholder="Prompt text..."
                          />
                          <div className="mt-3 flex justify-end">
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.preventDefault();
                                await handleRegenerateSearchQuery(true);
                              }}
                              disabled={isRegeneratingSearchQuery || !editableSearchQueryPromptText}
                              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                            >
                              {isRegeneratingSearchQuery ? (
                                <span className="flex items-center gap-2">
                                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Regenerating...
                                </span>
                              ) : (
                                'Re-run Search Query Generation'
                              )}
                            </button>
                          </div>
                        </div>
                      </details>
                    </div>
                  )}

                  {/* Determined Specialty */}
                  {searchParams?.determined_specialty && (
                    <div className="border-l-4 border-purple-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-2">Recommended Specialty</h3>
                      <p className="text-gray-700">{searchParams.determined_specialty}</p>
                    </div>
                  )}

                  {/* Patient Age Category */}
                  {searchParams?.patient_age_category && (
                    <div className="border-l-4 border-teal-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-2">Patient Age Category</h3>
                      <p className="text-gray-700">
                        {searchParams.patient_age_category === 'adult' ? 'Adult' : 'Child'} ({searchParams.patient_age_category === 'adult' ? '≥18 years' : '<18 years'})
                      </p>
                    </div>
                  )}
                </div>
              </div>
              {/* Button to generate CPT codes */}
              {(() => {
                const searchQuery = searchParams?.search_query || location.state?.aiRecommendations?.patient_profile?.search_query;
                const existingCptCodes = cptCodes || searchParams?.cpt_codes;
                const hasCptCodes = Array.isArray(existingCptCodes) && existingCptCodes.length > 0;
                const hasCptCodesByCategory = Object.keys(cptCodesByCategory).length > 0;
                
                // Don't show button if CPT codes already exist (either legacy or category-based)
                if (hasCptCodes || hasCptCodesByCategory) {
                  return null;
                }
                
                // Always show the button (will be disabled if searchQuery is missing)
                return (
                  <div className="text-center mt-6">
                    <button
                      onClick={() => handleGenerateCPTCodes(false)}
                      disabled={isGeneratingCPTCodes || !searchQuery}
                      className="inline-flex items-center gap-3 bg-gradient-to-r from-green-600 to-teal-600 text-white px-6 py-3 rounded-lg font-semibold text-lg hover:from-green-700 hover:to-teal-700 focus:ring-4 focus:ring-green-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                      title={!searchQuery ? "Search query is required to generate CPT codes" : ""}
                    >
                      {isGeneratingCPTCodes ? (
                        <>
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                          Generating CPT Codes...
                        </>
                      ) : (
                        <>
                          Generate CPT Codes
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        </>
                      )}
                    </button>
                    {!searchQuery && (
                      <p className="text-sm text-gray-500 mt-2">Waiting for search query to be generated...</p>
                    )}
                  </div>
                );
              })()}
              
              {/* CPT Codes Section - only show if we have actual CPT codes or database codes */}
              {(() => {
                // Show section if we have GPT codes OR database codes
                const hasAnyCptCodes = hasCptCodes || (dbCptCodes && dbCptCodes.length > 0);
                if (!hasAnyCptCodes) {
                  return null;
                }
                
                const hasCptCodesByCategory = Object.keys(cptCodesByCategory).length > 0;
                
                // Prefer category-based codes if available, otherwise fall back to legacy format
                const categories = hasCptCodesByCategory ? Object.keys(cptCodesByCategory) : [];
                const displayCategory = selectedCptCategory || (categories.length > 0 ? categories[0] : null);
                
                return (
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-semibold text-gray-900">Relevant CPT Codes</h2>
                    {hasCptCodesByCategory && activeCptSourceTab === 'gpt' && (
                      <div className="text-sm text-gray-600">
                        Total: {Object.values(cptCodesByCategory).flat().length} codes across {categories.length} {categories.length === 1 ? 'category' : 'categories'}
                      </div>
                    )}
                    {activeCptSourceTab === 'database' && dbCptCodes && (
                      <div className="text-sm text-gray-600">
                        {Object.keys(dbCptCodesByCategory).length > 0 ? (
                          <>
                            {dbCptCodes.length} {dbCptCodes.length === 1 ? 'code' : 'codes'} across {Object.keys(dbCptCodesByCategory).length} {Object.keys(dbCptCodesByCategory).length === 1 ? 'category' : 'categories'} from ICD-10 mapping
                          </>
                        ) : (
                          <>
                            {dbCptCodes.length} {dbCptCodes.length === 1 ? 'code' : 'codes'} from ICD-10 mapping
                          </>
                        )}
                      </div>
                    )}
                    {activeCptSourceTab === 'comparison' && hasCptCodes && dbCptCodes && (
                      <div className="text-sm text-gray-600">
                        {(() => {
                          const gptCodesSet = new Set(
                            hasCptCodesByCategory 
                              ? Object.values(cptCodesByCategory).flat().map((c: any) => c.code)
                              : (cptCodes || []).map((c: any) => c.code)
                          );
                          const dbCodesSet = new Set(dbCptCodes.map((c: any) => c.code));
                          const unionSet = new Set([...gptCodesSet, ...dbCodesSet]);
                          const intersectionSet = new Set([...gptCodesSet].filter(c => dbCodesSet.has(c)));
                          const gptOnly = gptCodesSet.size - intersectionSet.size;
                          const dbOnly = dbCodesSet.size - intersectionSet.size;
                          return (
                            <>
                              {unionSet.size} total codes • {intersectionSet.size} in both • {gptOnly} GPT only • {dbOnly} AAPC only
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                  
                  {/* Source Tabs - GPT vs Database */}
                  <div className="mb-4 border-b border-gray-200">
                    <div className="flex space-x-1">
                      {hasCptCodes && (
                        <button
                          onClick={() => setActiveCptSourceTab('gpt')}
                          className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                            activeCptSourceTab === 'gpt'
                              ? 'border-blue-600 text-blue-600'
                              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                          }`}
                        >
                          GPT CPT Codes
                          {hasCptCodesByCategory && (
                            <span className="ml-2 text-xs">({Object.values(cptCodesByCategory).flat().length})</span>
                          )}
                          {!hasCptCodesByCategory && cptCodes && (
                            <span className="ml-2 text-xs">({cptCodes.length})</span>
                          )}
                        </button>
                      )}
                      {dbCptCodes && dbCptCodes.length > 0 && (
                        <button
                          onClick={() => setActiveCptSourceTab('database')}
                          className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                            activeCptSourceTab === 'database'
                              ? 'border-green-600 text-green-600'
                              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                          }`}
                        >
                          AAPC ICD → CPT Crosswalk
                          <span className="ml-2 text-xs">({dbCptCodes.length})</span>
                        </button>
                      )}
                      {hasCptCodes && dbCptCodes && dbCptCodes.length > 0 && (
                        <button
                          onClick={() => setActiveCptSourceTab('comparison')}
                          className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                            activeCptSourceTab === 'comparison'
                              ? 'border-purple-600 text-purple-600'
                              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                          }`}
                        >
                          Comparison
                          <span className="ml-2 text-xs">({(() => {
                            // Calculate union count
                            const gptCodesSet = new Set(
                              hasCptCodesByCategory 
                                ? Object.values(cptCodesByCategory).flat().map((c: any) => c.code)
                                : (cptCodes || []).map((c: any) => c.code)
                            );
                            const dbCodesSet = new Set(dbCptCodes.map((c: any) => c.code));
                            const unionSet = new Set([...gptCodesSet, ...dbCodesSet]);
                            return unionSet.size;
                          })()})</span>
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* GPT CPT Codes Tab Content */}
                  {activeCptSourceTab === 'gpt' && hasCptCodes && (
                    <>
                      {/* Category Tabs - only show if we have multiple categories */}
                      {hasCptCodesByCategory && categories.length > 1 && (
                        <div className="mb-4 border-b border-gray-200">
                          <div className="flex space-x-1 overflow-x-auto">
                            {categories.map((category) => {
                              const categoryCodes = cptCodesByCategory[category] || [];
                              const isSelected = displayCategory === category;
                              return (
                                <button
                                  key={category}
                                  onClick={() => setSelectedCptCategory(category)}
                                  className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                    isSelected
                                      ? 'border-blue-600 text-blue-600'
                                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                  }`}
                                >
                                  {category} ({categoryCodes.length})
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      
                      {/* Both LLM prompts: Generation (Step 1) and Categorization (Step 2) */}
                      {displayCategory && (cptPromptTextByCategory[displayCategory] || cptCategorizationPromptText) && (
                    <div className="mb-4 space-y-3">
                      {cptPromptTextByCategory[displayCategory] && (
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Step 1: Generation Prompt (CPT codes + descriptions)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">Prompt sent to the LLM to generate CPT codes and descriptions:</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={editablePromptTextByCategory[displayCategory] || cptPromptTextByCategory[displayCategory] || ''}
                            onChange={(e) => {
                              setEditablePromptTextByCategory(prev => ({
                                ...prev,
                                [displayCategory]: e.target.value
                              }));
                            }}
                            placeholder="Prompt text..."
                          />
                          <div className="mt-3 flex justify-end">
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.preventDefault();
                                await handleGenerateCPTCodes(true);
                              }}
                              disabled={isGeneratingCPTCodes || !editablePromptTextByCategory[displayCategory]}
                              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                            >
                              {isGeneratingCPTCodes && isGeneratingCPTCodesForCategory === displayCategory ? (
                                <span className="flex items-center gap-2">
                                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Generating...
                                </span>
                              ) : (
                                'Rerun with Edited Prompt'
                              )}
                            </button>
                          </div>
                        </div>
                      </details>
                      )}
                      {cptCategorizationPromptText && (
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            Step 2: Categorization Prompt (relevancy scores + categories)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">Prompt sent to the LLM with codes and database descriptions to assign categories and relevancy scores:</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={cptCategorizationPromptText}
                            readOnly
                            placeholder="Categorization prompt..."
                          />
                        </div>
                      </details>
                      )}
                    </div>
                      )}
                      
                      {/* Fallback prompt section: show both LLM prompts (Generation + Categorization) */}
                      {!hasCptCodesByCategory && (cptPromptText || searchParams?.cpt_prompt_text || cptCategorizationPromptText || searchParams?.cpt_categorization_prompt_text) && (
                    <div className="mb-4 space-y-3">
                      {/* Step 1: Generation prompt (code + description only) */}
                      {(cptPromptText || searchParams?.cpt_prompt_text) && (
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            Step 1: Generation Prompt (CPT codes + descriptions)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">Prompt sent to the LLM to generate CPT codes and descriptions (no category or relevancy):</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={editablePromptText || cptPromptText || searchParams?.cpt_prompt_text || ''}
                            onChange={(e) => setEditablePromptText(e.target.value)}
                            placeholder="Prompt text..."
                          />
                          <div className="mt-3 flex justify-end">
                            <button
                              type="button"
                              onClick={async (e) => {
                                e.preventDefault();
                                await handleGenerateCPTCodes(true);
                              }}
                              disabled={isGeneratingCPTCodes || !editablePromptText}
                              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                            >
                              {isGeneratingCPTCodes ? (
                                <span className="flex items-center gap-2">
                                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Generating...
                                </span>
                              ) : (
                                'Rerun with Edited Prompt'
                              )}
                            </button>
                          </div>
                        </div>
                      </details>
                      )}
                      {/* Step 2: Categorization prompt (relevancy + category using DB descriptions) */}
                      {(cptCategorizationPromptText || searchParams?.cpt_categorization_prompt_text) && (
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            Step 2: Categorization Prompt (relevancy scores + categories)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">Prompt sent to the LLM with codes and database descriptions to assign categories and relevancy scores:</p>
                          <textarea
                            className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                            value={cptCategorizationPromptText || searchParams?.cpt_categorization_prompt_text || ''}
                            readOnly
                            placeholder="Categorization prompt..."
                          />
                        </div>
                      </details>
                      )}
                    </div>
                      )}
                      
                      <div className="text-sm text-gray-600 mb-3">
                        {displayCategory 
                          ? `Procedural codes for ${displayCategory} category:`
                          : 'Procedural codes that could be used by a neurosurgeon to treat this condition:'}
                      </div>
                      
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {((hasCptCodesByCategory && displayCategory && cptCodesByCategory[displayCategory]
                          ? cptCodesByCategory[displayCategory]
                          : (cptCodes || searchParams?.cpt_codes || [])
                        ).slice().sort((a: any, b: any) => (b.relevancy_score ?? 0) - (a.relevancy_score ?? 0))
                        ).map((cpt: any, index: number) => {
                          const llmDescription = cpt.description;
                          const dbDescription = cptDbDescriptions[cpt.code];
                          const isIrrelevant = cpt.relevant === false || (typeof cpt.relevancy_score === 'number' && cpt.relevancy_score < 40);
                          return (
                            <div key={index} className="flex items-start gap-3 py-2 px-2 bg-amber-50 rounded border border-amber-200 min-h-0">
                              <code className="bg-amber-100 px-2 py-1 rounded text-sm font-semibold text-amber-900 whitespace-nowrap flex-shrink-0">
                                {cpt.code}
                              </code>
                              {cpt.relevancy_score !== undefined && (
                                <span className="text-xs font-medium text-gray-600 bg-gray-200 px-1.5 py-0.5 rounded flex-shrink-0">
                                  {cpt.relevancy_score}%
                                </span>
                              )}
                              {isIrrelevant && (
                                <span
                                  className="inline-flex flex-shrink-0 text-red-600 cursor-help"
                                  title="Excluded from clinical volume (relevancy < 40%)"
                                >
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                  </svg>
                                </span>
                              )}
                              <div className="flex-1 min-w-0 text-sm">
                                {llmDescription && (
                                  <div className="leading-tight">
                                    <span className="text-xs font-semibold text-blue-600 uppercase">LLM DESCRIPTION: </span>
                                    <span className="text-gray-700">{llmDescription}</span>
                                  </div>
                                )}
                                {dbDescription && (
                                  <div className="leading-tight mt-0.5">
                                    <span className="text-xs font-semibold text-green-600 uppercase">DATABASE DESCRIPTION: </span>
                                    <span className="text-gray-700">{dbDescription}</span>
                                  </div>
                                )}
                                {!llmDescription && !dbDescription && (
                                  <span className="text-gray-500 text-xs">No descriptions available</span>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                  
                  {/* Database CPT Codes Tab Content */}
                  {activeCptSourceTab === 'database' && dbCptCodes && dbCptCodes.length > 0 && (
                    <>
                      <div className="text-sm text-gray-600 mb-3">
                        CPT codes mapped from ICD-10 code(s): <code className="bg-gray-100 px-2 py-1 rounded text-xs font-mono">
                          {(() => {
                            const codes = searchParams?.predicted_icd10_codes || location.state?.aiRecommendations?.patient_profile?.predicted_icd10_codes;
                            if (codes && Array.isArray(codes) && codes.length > 0) {
                              return codes.join(', ');
                            }
                            return searchParams?.predicted_icd10 || location.state?.aiRecommendations?.patient_profile?.predicted_icd10 || 'N/A';
                          })()}
                        </code>
                      </div>
                      
                      {/* Categorization GPT Prompt Instructions (collapsed by default) */}
                      {categorizationPromptText && (
                        <div className="mb-4">
                          <details className="bg-gray-50 rounded-lg border border-gray-200">
                            <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                              <span className="flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                View GPT Prompt Instructions for Categorization (for debugging)
                              </span>
                            </summary>
                            <div className="p-4 border-t border-gray-200">
                              <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to categorize the database CPT codes:</p>
                              <textarea
                                className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                                value={editableCategorizationPromptText || categorizationPromptText || ''}
                                onChange={(e) => setEditableCategorizationPromptText(e.target.value)}
                                placeholder="Prompt text..."
                              />
                              <div className="mt-3 flex justify-end">
                                <button
                                  type="button"
                                  onClick={async (e) => {
                                    e.preventDefault();
                                    await handleRecategorizeCPTCodes(true);
                                  }}
                                  disabled={isRecategorizingCPTCodes || !editableCategorizationPromptText}
                                  className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                                >
                                  {isRecategorizingCPTCodes ? (
                                    <span className="flex items-center gap-2">
                                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                      </svg>
                                      Recategorizing...
                                    </span>
                                  ) : (
                                    'Rerun with Edited Prompt'
                                  )}
                                </button>
                              </div>
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Category Tabs - only show if we have multiple categories */}
                      {(() => {
                        const dbCategories = Object.keys(dbCptCodesByCategory);
                        const hasDbCategories = dbCategories.length > 1;
                        const dbDisplayCategory = selectedCptCategory && dbCategories.includes(selectedCptCategory) 
                          ? selectedCptCategory 
                          : (dbCategories.length > 0 ? dbCategories[0] : null);
                        
                        return (
                          <>
                            {hasDbCategories && (
                              <div className="mb-4 border-b border-gray-200">
                                <div className="flex space-x-1 overflow-x-auto">
                                  {dbCategories.map((category) => {
                                    const categoryCodes = dbCptCodesByCategory[category] || [];
                                    const isSelected = dbDisplayCategory === category;
                                    return (
                                      <button
                                        key={category}
                                        onClick={() => setSelectedCptCategory(category)}
                                        className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                          isSelected
                                            ? 'border-green-600 text-green-600'
                                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                        }`}
                                      >
                                        {category} ({categoryCodes.length})
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                            
                            <div className="text-sm text-gray-600 mb-3">
                              {dbDisplayCategory 
                                ? `Procedural codes for ${dbDisplayCategory} category:`
                                : 'Procedural codes from ICD-10 mapping:'}
                            </div>
                            
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                              {((hasDbCategories && dbDisplayCategory && dbCptCodesByCategory[dbDisplayCategory]
                                ? dbCptCodesByCategory[dbDisplayCategory]
                                : dbCptCodes
                              ).slice().sort((a: any, b: any) => (b.relevancy_score ?? 0) - (a.relevancy_score ?? 0))
                              ).map((cpt: any, index: number) => {
                                const isIrrelevant = cpt.relevant === false || (typeof cpt.relevancy_score === 'number' && cpt.relevancy_score < 40);
                                return (
                                <div key={index} className="bg-green-50 rounded-lg p-3 border border-green-200">
                                  <div className="flex items-start gap-3">
                                    <code className="bg-green-100 px-2 py-1 rounded text-sm font-semibold text-green-900 whitespace-nowrap">
                                      {cpt.code}
                                    </code>
                                    <span className="text-sm text-gray-700 flex-1">{cpt.description}</span>
                                    {cpt.relevancy_score !== undefined && (
                                      <span className="text-xs font-medium text-gray-600 bg-gray-200 px-2 py-1 rounded flex-shrink-0">
                                        {cpt.relevancy_score}%
                                      </span>
                                    )}
                                    {isIrrelevant && (
                                      <span
                                        className="inline-flex flex-shrink-0 text-red-600 cursor-help"
                                        title="Excluded from clinical volume (relevancy < 40%)"
                                      >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                                        </svg>
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );})}
                            </div>
                          </>
                        );
                      })()}
                      
                      <div className="mt-3 text-xs text-gray-500 italic">
                        Note: These database-mapped CPT codes are shown for reference only and are not yet used for CMS/PubMed queries.
                      </div>
                    </>
                  )}
                  
                  {/* Comparison Tab Content */}
                  {activeCptSourceTab === 'comparison' && hasCptCodes && dbCptCodes && dbCptCodes.length > 0 && (
                    <>
                      {(() => {
                        // Get all GPT codes (flattened from categories or legacy format)
                        const allGptCodes: Array<{ code: string; description: string; category?: string }> = hasCptCodesByCategory
                          ? Object.entries(cptCodesByCategory).flatMap(([category, codes]: [string, any[]]) =>
                              codes.map((c: any) => ({ ...c, category }))
                            )
                          : (cptCodes || []).map((c: any) => ({ ...c, category: undefined }));
                        
                        // Get all DB codes (flattened from categories or flat list)
                        const allDbCodes: Array<{ code: string; description: string; category?: string }> = Object.keys(dbCptCodesByCategory).length > 0
                          ? Object.entries(dbCptCodesByCategory).flatMap(([category, codes]: [string, any[]]) =>
                              codes.map((c: any) => ({ ...c, category }))
                            )
                          : (dbCptCodes || []).map((c: any) => ({ ...c, category: undefined }));
                        
                        // Create maps for quick lookup
                        const gptCodeMap = new Map<string, { description: string; category?: string; relevancy_score?: number }>();
                        allGptCodes.forEach(c => {
                          gptCodeMap.set(c.code, { description: c.description, category: c.category, relevancy_score: (c as any).relevancy_score });
                        });
                        
                        const dbCodeMap = new Map<string, { description: string; category?: string; relevancy_score?: number }>();
                        allDbCodes.forEach(c => {
                          dbCodeMap.set(c.code, { description: c.description, category: c.category, relevancy_score: (c as any).relevancy_score });
                        });
                        
                        // Get all categories from both sources (union)
                        const gptCategories = hasCptCodesByCategory ? Object.keys(cptCodesByCategory) : [];
                        const dbCategories = Object.keys(dbCptCodesByCategory);
                        const allCategories = Array.from(new Set([...gptCategories, ...dbCategories])).sort();
                        const hasCategories = allCategories.length > 1;
                        
                        // Determine the display category
                        const comparisonDisplayCategory = selectedCptCategory && allCategories.includes(selectedCptCategory)
                          ? selectedCptCategory
                          : (allCategories.length > 0 ? allCategories[0] : null);
                        
                        // Get codes for the selected category
                        const getCodesForCategory = (category: string | null) => {
                          if (!category) {
                            // Return all codes if no category
                            const allCodesSet = new Set([...allGptCodes.map(c => c.code), ...allDbCodes.map(c => c.code)]);
                            return Array.from(allCodesSet).sort();
                          }
                          
                          // Get codes that are in this category in either source
                          const gptCodesInCategory = allGptCodes.filter(c => c.category === category).map(c => c.code);
                          const dbCodesInCategory = allDbCodes.filter(c => c.category === category).map(c => c.code);
                          const codesSet = new Set([...gptCodesInCategory, ...dbCodesInCategory]);
                          return Array.from(codesSet).sort();
                        };
                        
                        const displayCodes = getCodesForCategory(comparisonDisplayCategory);
                        
                        // Count codes per category for tabs
                        const getCodeCountForCategory = (category: string) => {
                          const gptCodesInCategory = allGptCodes.filter(c => c.category === category).map(c => c.code);
                          const dbCodesInCategory = allDbCodes.filter(c => c.category === category).map(c => c.code);
                          return new Set([...gptCodesInCategory, ...dbCodesInCategory]).size;
                        };
                        
                        return (
                          <>
                            {/* Category Tabs */}
                            {hasCategories && (
                              <div className="mb-4 border-b border-gray-200">
                                <div className="flex space-x-1 overflow-x-auto">
                                  {allCategories.map((category) => {
                                    const codeCount = getCodeCountForCategory(category);
                                    const isSelected = comparisonDisplayCategory === category;
                                    return (
                                      <button
                                        key={category}
                                        onClick={() => setSelectedCptCategory(category)}
                                        className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                          isSelected
                                            ? 'border-purple-600 text-purple-600'
                                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                        }`}
                                      >
                                        {category} ({codeCount})
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                            
                            <div className="text-sm text-gray-600 mb-3">
                              {comparisonDisplayCategory 
                                ? `Comparison of GPT and AAPC codes for ${comparisonDisplayCategory}:`
                                : 'Side-by-side comparison of GPT-generated and AAPC database-mapped CPT codes:'}
                            </div>
                            
                            <div className="space-y-1.5 max-h-96 overflow-y-auto">
                              {displayCodes.map((code, index) => {
                                const inGpt = gptCodeMap.has(code);
                                const inDb = dbCodeMap.has(code);
                                const gptInfo = gptCodeMap.get(code);
                                const dbInfo = dbCodeMap.get(code);
                                
                                // Determine background color based on source
                                let bgColor = 'bg-gray-50';
                                let borderColor = 'border-gray-200';
                                if (inGpt && inDb) {
                                  bgColor = 'bg-purple-50';
                                  borderColor = 'border-purple-300';
                                } else if (inGpt) {
                                  bgColor = 'bg-blue-50';
                                  borderColor = 'border-blue-200';
                                } else if (inDb) {
                                  bgColor = 'bg-green-50';
                                  borderColor = 'border-green-200';
                                }
                                
                                return (
                                  <div key={index} className={`${bgColor} rounded-lg p-2 border-2 ${borderColor}`}>
                                    <div className="flex items-start gap-2">
                                      <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                          <code className="bg-white px-2 py-0.5 rounded text-sm font-semibold text-gray-900 border border-gray-300">
                                            {code}
                                          </code>
                                          <div className="flex gap-1.5">
                                            {inGpt && inDb ? (
                                              <span className="px-1.5 py-0.5 bg-purple-100 text-purple-700 text-xs font-medium rounded-full">
                                                Both
                                              </span>
                                            ) : (
                                              <>
                                                {inGpt && (
                                                  <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                                                    GPT
                                                  </span>
                                                )}
                                                {inDb && (
                                                  <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-xs font-medium rounded-full">
                                                    AAPC
                                                  </span>
                                                )}
                                              </>
                                            )}
                                          </div>
                                        </div>
                                        <p className="text-xs text-gray-700 mb-1">
                                          {gptInfo?.description || dbInfo?.description || 'No description available'}
                                        </p>
                                        <div className="flex gap-3 text-xs">
                                          {inGpt && gptInfo?.relevancy_score !== undefined && (
                                            <span className="text-gray-600">
                                              GPT: <span className="font-medium">{gptInfo.relevancy_score}%</span>
                                            </span>
                                          )}
                                          {inDb && dbInfo?.relevancy_score !== undefined && (
                                            <span className="text-gray-600">
                                              AAPC: <span className="font-medium">{dbInfo.relevancy_score}%</span>
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </>
                        );
                      })()}
                    </>
                  )}
                  
                  {/* Button to generate specialist recommendations */}
                  <div className="text-center mt-6">
                    <button
                      onClick={handleShowSpecialists}
                      disabled={isGeneratingSpecialists}
                      className="inline-flex items-center gap-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 rounded-lg font-semibold text-lg hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-300 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                    >
                      {isGeneratingSpecialists ? (
                        <>
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                          Generating Specialists...
                        </>
                      ) : (
                        <>
                          Show me suggested specialists
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                          </svg>
                        </>
                      )}
                    </button>
                  </div>
                </div>
                );
              })()}
            </div>
        </>
        )}

        {/* Specialists Section */}
        {activeView === 'specialists' && (
          <>
            {/* Specialists Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                {searchParams?.determined_specialty ? `${searchParams.determined_specialty} Specialists` : 'Specialists'}
              </h1>
              

        </div>

        {/* Search and Filter Controls */}
        <div className="py-2 mb-3">
          <div className="flex flex-col gap-4">
            {/* Search Bar - Expandable (shown when expanded) */}
            {isSearchExpanded && (
              <div className="flex items-center justify-center">
                <div className="relative w-full max-w-xs">
                  <input
                    type="text"
                    id="search"
                    placeholder="Search specialists..."
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                      setCurrentPage(1);
                      saveFilterState();
                    }}
                    onBlur={() => {
                      if (!searchTerm) {
                        setIsSearchExpanded(false);
                      }
                    }}
                    autoFocus
                    className="w-full pl-8 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 bg-white/50"
                  />
                  <svg className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {searchTerm && (
                    <button
                      onClick={() => {
                        setSearchTerm('');
                        setIsSearchExpanded(false);
                        setCurrentPage(1);
                        saveFilterState();
                      }}
                      className="absolute right-2.5 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 hover:text-gray-600"
                    >
                      <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Category Tabs */}
            {(() => {
              // Get categories from CPT codes (combine GPT and AAPC)
              const allCategories = new Set<string>();
              Object.keys(cptCodesByCategory).forEach(cat => allCategories.add(cat));
              Object.keys(dbCptCodesByCategory).forEach(cat => allCategories.add(cat));
              const categories = getCategoriesFromCptCodes(
                Object.assign({}, cptCodesByCategory, dbCptCodesByCategory)
              );
              
              if (categories.length > 0 && Object.keys(treatmentRankings).length > 0) {
                // Group treatments by category (for handleCategoryFilterChange - not used for filtering anymore)
                const treatmentsByCategory: { [category: string]: Array<{ id: string; treatment: any }> } = {};
                Object.entries(treatmentRankings).forEach(([treatmentId, treatment]) => {
                  const category = (treatment as any).category || 'Medical';
                  if (!treatmentsByCategory[category]) {
                    treatmentsByCategory[category] = [];
                  }
                  treatmentsByCategory[category].push({ id: treatmentId, treatment });
                });
                
                return (
                  <div className="flex items-center justify-center gap-2">
                    {/* "All" button first */}
                    <button
                      onClick={() => {
                        setSelectedCategory('All');
                        handleCategoryFilterChange('All', treatmentsByCategory);
                      }}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        (selectedCategory || 'All') === 'All'
                          ? 'bg-blue-500 text-white shadow-sm'
                          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      All
                    </button>
                    {categories.map((category) => {
                      const isSelected = selectedCategory === category;
                      return (
                        <button
                          key={category}
                          onClick={() => {
                            setSelectedCategory(category);
                            handleCategoryFilterChange(category, treatmentsByCategory);
                          }}
                          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                            isSelected
                              ? 'bg-blue-500 text-white shadow-sm'
                              : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                          }`}
                        >
                          {category}
                        </button>
                      );
                    })}
                    {!isSearchExpanded && (
                      <button
                        onClick={() => setIsSearchExpanded(true)}
                        className="ml-2 text-gray-600 hover:text-gray-800 transition-colors"
                        title="Search specialists"
                      >
                        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                      </button>
                    )}
                  </div>
                );
              }
              return null;
            })()}
          </div>
        </div>
          </>
        )}


        {/* Results */}
        {activeView === 'specialists' && (
        <div className="space-y-6">
          {currentProviders.map((provider, index) => {
            const rank = indexOfFirstProvider + index + 1;
            const { score, breakdown } = getProviderScore(provider);
            const scoreData = providerScores[provider.npi];
            const isCertified = scoreData?.is_certified === true || scoreData?.certification_points > 0;
            
            return (
              <div key={provider.id} className="relative">
                <NPIProviderCard
                  key={`${provider.npi}-${selectedCategory || 'all'}`}
                  provider={provider}
                  onClick={handleProviderClick}
                  score={score}
                  scoreBreakdown={breakdown}
                  scoreData={scoreData}
                  isCertified={isCertified}
                  providerContent={(() => {
                    const contentData = providerLinks[provider.npi];
                    console.log(`DEBUG: Looking for content for provider "${provider.name}" (NPI: "${provider.npi}") - found:`, contentData);
                    console.log('DEBUG: Available provider content:', providerLinks);
                    return contentData;
                  })()}
                  patientDiagnosis={searchParams?.diagnosis}
                  searchQuery={searchParams?.search_query}
                  patientAgeCategory={searchParams?.patient_age_category}
                />
              </div>
            );
          })}
        </div>
        )}

        {/* Page Size Selector and Pagination */}
        {activeView === 'specialists' && (
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
        )}

        {/* Footer Info */}
        {activeView === 'specialists' && (
          <div className="mt-8 text-center text-gray-500">
            <p>Showing {indexOfFirstProvider + 1}-{Math.min(indexOfLastProvider, filteredProviders.length)} of {filteredProviders.length} providers</p>
          </div>
        )}

        {/* Debug Section */}
        {activeView === 'debug' && (
          <div className="bg-gray-900 text-gray-100 rounded-lg p-6 shadow-lg">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                <svg className="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                Search Process Debugging
              </h2>
              <button
                onClick={() => {
                  const debugData = {
                    searchInputs: {
                      userDiagnosis: searchParams?.diagnosis,
                      medicalAnalysisDiagnosis: searchParams?.icd10_description,
                      icd10Code: (searchParams?.predicted_icd10_codes && searchParams.predicted_icd10_codes.length > 0) 
                        ? searchParams.predicted_icd10_codes.join(',')
                        : searchParams?.predicted_icd10,
                      city: searchParams?.city,
                      state: searchParams?.state,
                      specialty: searchParams?.determined_specialty
                    },
                    searchResults: location.state?.aiRecommendations,
                    providers: providers,
                    treatmentRankings: treatmentRankings
                  };
                  navigator.clipboard.writeText(JSON.stringify(debugData, null, 2));
                  alert('Debug data copied to clipboard!');
                }}
                className="text-sm px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors"
              >
                Copy All Debug Data
              </button>
            </div>

            <div className="space-y-6">
              {/* Search Inputs Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-blue-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  1. Search Inputs
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">User-Entered Diagnosis:</span>
                    <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">{searchParams?.diagnosis || 'N/A'}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Medical Analysis Diagnosis:</span>
                    <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">{searchParams?.icd10_description || 'N/A'}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">ICD-10 Code:</span>
                    <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                      {(() => {
                        const codes = searchParams?.predicted_icd10_codes;
                        if (codes && Array.isArray(codes) && codes.length > 0) {
                          return codes.join(', ');
                        }
                        return searchParams?.predicted_icd10 || 'N/A';
                      })()}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-400">Location:</span>
                    <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">{searchParams?.city}, {searchParams?.state}</p>
                  </div>
                </div>
              </div>

              {/* PubMed Articles Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-orange-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  2. PubMed Articles Found
                </h3>
                <div className="space-y-3">
                  {(() => {
                    // Extract results from shared specialist information
                    const sharedInfo = 
                      specialistRecommendationData?.shared_specialist_information ||
                      location.state?.aiRecommendations?.shared_specialist_information;
                    
                    let specialistResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        specialistResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      specialistResults = sharedInfo;
                    }
                    
                    if (specialistResults && Array.isArray(specialistResults)) {
                      const pubmedArticles = specialistResults.filter((item: any) => item._source === 'pubmed');
                      
                      if (pubmedArticles.length > 0) {
                        return (
                          <>
                            <p className="text-gray-400 mb-3">Found {pubmedArticles.length} PubMed articles:</p>
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                              {pubmedArticles.map((article: any, idx: number) => (
                                <div key={idx} className={`rounded p-3 border-l-4 ${
                                  article._verified === true 
                                    ? 'bg-gray-900 border-green-500' 
                                    : 'bg-gray-900 border-red-500'
                                }`}>
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2 mb-2">
                                        <span className={`px-1.5 py-0.5 rounded text-xs ${
                                          article._verified === true 
                                            ? 'bg-green-100 text-green-800 border border-green-200' 
                                            : 'bg-red-100 text-red-800 border border-red-200'
                                        }`}>
                                          {article._verified === true ? '✓ Verified' : '✗ Unverified'}
                                        </span>
                                        {article._score !== null && article._score !== undefined ? (
                                          <span className="px-2 py-1 bg-blue-600 text-white rounded text-xs font-semibold">
                                            Score: {article._score.toFixed(3)}
                                          </span>
                                        ) : (
                                          <span className="px-2 py-1 bg-gray-600 text-white rounded text-xs font-semibold">
                                            No Score
                                          </span>
                                        )}
                                      </div>
                                      <h4 className="text-white font-medium text-sm mb-1">{article.title || 'No title'}</h4>
                                      <p className="text-gray-300 text-xs mb-2">Authors: {article.authors || 'Unknown'}</p>
                                      {article._id && (
                                        <div className="flex items-center gap-2">
                                          <span className="text-gray-400 text-xs">PMID:</span>
                                          <a 
                                            href={`https://pubmed.ncbi.nlm.nih.gov/${article._id}/`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-blue-300 hover:text-blue-200 text-xs underline"
                                          >
                                            {article._id}
                                          </a>
                                          <svg className="h-3 w-3 text-blue-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                          </svg>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </>
                        );
                      }
                    }
                    
                    return (
                      <p className="text-yellow-400">No PubMed articles found in specialist results</p>
                    );
                  })()}
                </div>
              </div>

              {/* Vumedi Videos Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-purple-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  3. Vumedi Videos Found
                </h3>
                <div className="space-y-3">
                  {(() => {
                    // Extract results from shared specialist information
                    const sharedInfo = 
                      specialistRecommendationData?.shared_specialist_information ||
                      location.state?.aiRecommendations?.shared_specialist_information;
                    
                    let specialistResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        specialistResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      specialistResults = sharedInfo;
                    }
                    
                    if (specialistResults && Array.isArray(specialistResults)) {
                      const vumediVideos = specialistResults.filter((item: any) => item._source === 'vumedi');
                      
                      if (vumediVideos.length > 0) {
                        return (
                          <>
                            <p className="text-gray-400 mb-3">Found {vumediVideos.length} Vumedi videos:</p>
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                              {vumediVideos.map((video: any, idx: number) => (
                                <div key={idx} className={`rounded p-3 border-l-4 ${
                                  video._verified === true 
                                    ? 'bg-gray-900 border-green-500' 
                                    : 'bg-gray-900 border-red-500'
                                }`}>
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1">
                                      <div className="flex items-center gap-2 mb-2">
                                        <span className={`px-1.5 py-0.5 rounded text-xs ${
                                          video._verified === true 
                                            ? 'bg-green-100 text-green-800 border border-green-200' 
                                            : 'bg-red-100 text-red-800 border border-red-200'
                                        }`}>
                                          {video._verified === true ? '✓ Verified' : '✗ Unverified'}
                                        </span>
                                        {video._score !== null && video._score !== undefined ? (
                                          <span className="px-2 py-1 bg-blue-600 text-white rounded text-xs font-semibold">
                                            Score: {video._score.toFixed(3)}
                                          </span>
                                        ) : (
                                          <span className="px-2 py-1 bg-gray-600 text-white rounded text-xs font-semibold">
                                            No Score
                                          </span>
                                        )}
                                      </div>
                                      <h4 className="text-white font-medium text-sm mb-1">{video.title || 'No title'}</h4>
                                      <p className="text-gray-300 text-xs mb-1">Featuring: {video.featuring || 'Unknown'}</p>
                                      <p className="text-gray-300 text-xs mb-2">Author: {video.author || 'Unknown'}</p>
                                      {video.link && (
                                        <div className="flex items-center gap-2">
                                          <a 
                                            href={video.link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-blue-300 hover:text-blue-200 text-xs underline flex items-center gap-1"
                                          >
                                            Watch Video
                                            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                            </svg>
                                          </a>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </>
                        );
                      }
                    }
                    
                    return (
                      <p className="text-yellow-400">No Vumedi videos found in specialist results</p>
                    );
                  })()}
                </div>
              </div>

              {/* GPT Search Queries Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-yellow-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  4. GPT Search Queries Used
                </h3>
                <div className="space-y-3">
                  <div className="bg-gray-900 rounded p-3">
                    <p className="text-gray-400 mb-2">Search Query:</p>
                    <p className="text-white font-mono bg-gray-800 p-2 rounded text-sm whitespace-pre-wrap">
                      {(() => {
                        // Try to find the search query from various sources
                        const query = 
                          specialistRecommendationData?.search_query ||
                          location.state?.aiRecommendations?.search_query ||
                          location.state?.search_query ||
                          'Search query not available in response data';
                        return query;
                      })()}
                    </p>
                    <details className="bg-gray-900 rounded p-3 mt-3">
                      <summary className="cursor-pointer text-blue-300 hover:text-blue-200 font-semibold text-sm">
                        Debug: Search query data sources
                      </summary>
                      <div className="mt-3 max-h-96 overflow-y-auto">
                        <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                          {JSON.stringify({
                            hasSpecialistData: !!specialistRecommendationData,
                            hasSearchQuery: !!specialistRecommendationData?.search_query,
                            searchQueryValue: specialistRecommendationData?.search_query,
                            specialistDataKeys: specialistRecommendationData ? Object.keys(specialistRecommendationData) : [],
                            fullSpecialistData: specialistRecommendationData
                          }, null, 2)}
                        </pre>
                      </div>
                    </details>
                  </div>
                </div>
              </div>

              {/* Specialist Results Summary Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-green-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  5. Specialist Search Results Summary
                </h3>
                <div className="space-y-3">
                  {(() => {
                    const sharedInfo = 
                      specialistRecommendationData?.shared_specialist_information ||
                      location.state?.aiRecommendations?.shared_specialist_information;
                    
                    let specialistResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        specialistResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      specialistResults = sharedInfo;
                    }
                    
                    if (specialistResults && Array.isArray(specialistResults) && specialistResults.length > 0) {
                      const verifiedResults = specialistResults.filter((item: any) => item._verified === true);
                      const unverifiedResults = specialistResults.filter((item: any) => item._verified !== true);
                      
                      return (
                        <>
                          <div className="grid grid-cols-4 gap-4 text-sm mb-2">
                            <div>
                              <span className="text-gray-400">Total Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {specialistResults.length}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-400">Vumedi Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {specialistResults.filter((item: any) => item._source === 'vumedi').length}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-400">PubMed Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {specialistResults.filter((item: any) => item._source === 'pubmed').length}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-400">Verification Status:</span>
                              <div className="mt-1 space-y-1">
                                <p className="text-green-400 font-mono bg-gray-900 p-1 rounded text-xs">
                                  ✅ Verified: {verifiedResults.length}
                                </p>
                                <p className="text-red-400 font-mono bg-gray-900 p-1 rounded text-xs">
                                  ❌ Unverified: {unverifiedResults.length}
                                </p>
                              </div>
                            </div>
                          </div>
                          <details className="bg-gray-900 rounded p-3">
                            <summary className="cursor-pointer text-blue-300 hover:text-blue-200 font-semibold">
                              View All Specialist Results ({specialistResults.length} items)
                            </summary>
                            <div className="mt-3 max-h-96 overflow-y-auto space-y-2">
                              {specialistResults.map((result: any, index: number) => (
                                <div key={index} className={`p-3 rounded border-l-4 ${
                                  result._verified === true 
                                    ? 'bg-green-900/20 border-green-500' 
                                    : 'bg-red-900/20 border-red-500'
                                }`}>
                                  <div className="flex items-center gap-2 mb-2">
                                    <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                      result._verified === true 
                                        ? 'bg-green-600 text-white' 
                                        : 'bg-red-600 text-white'
                                    }`}>
                                      {result._verified === true ? '✅ VERIFIED' : '❌ UNVERIFIED'}
                                    </span>
                                    <span className="px-2 py-1 bg-blue-600 text-white rounded text-xs font-semibold">
                                      {result._source?.toUpperCase()}
                                    </span>
                                  </div>
                                  <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                                    {JSON.stringify(result, null, 2)}
                                  </pre>
                                </div>
                              ))}
                            </div>
                          </details>
                        </>
                      );
                    }
                    
                    return (
                      <p className="text-yellow-400">No specialist search results available</p>
                    );
                  })()}
                </div>
              </div>

              {/* CMS API Results Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-cyan-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  6. CMS API Results (CPT Code Data)
                </h3>
                <div className="space-y-3">
                  {(() => {
                    // Check specialistRecommendationData first (from button click), then fall back to location.state
                    const cmsData = specialistRecommendationData?.cms_data || location.state?.aiRecommendations?.cms_data;
                    
                    if (cmsData) {
                      return (
                        <>
                          {/* CMS API URL(s) - Collapsed by default */}
                          <details className="bg-gray-900 rounded p-3">
                            <summary className="cursor-pointer text-cyan-300 hover:text-cyan-200 font-semibold text-sm">
                              API URL{cmsData.urls && cmsData.urls.length > 1 ? 's' : ''}:
                              {cmsData.urls && cmsData.urls.length > 1 && (
                                <span className="text-gray-500 ml-2">({cmsData.urls.length} calls)</span>
                              )}
                            </summary>
                            <div className="mt-3 space-y-2">
                              {cmsData.urls && cmsData.urls.length > 0 ? (
                                cmsData.urls.map((url: string, idx: number) => (
                                  <div key={idx} className="bg-gray-800 p-2 rounded">
                                    {cmsData.urls.length > 1 && (
                                      <p className="text-xs text-gray-500 mb-1">Call {idx + 1}:</p>
                                    )}
                                    <p className="text-xs text-cyan-300 font-mono break-all">{url}</p>
                                  </div>
                                ))
                              ) : cmsData.url ? (
                                <div className="bg-gray-800 p-2 rounded">
                                  <p className="text-xs text-cyan-300 font-mono break-all">{cmsData.url}</p>
                                </div>
                              ) : (
                                <p className="text-yellow-400 text-sm">No URL available</p>
                              )}
                            </div>
                          </details>

                          {/* Results Summary */}
                          <div className="grid grid-cols-3 gap-4">
                            <div className="bg-gray-900 rounded p-3">
                              <p className="text-gray-400 text-sm mb-1">Total Raw Results:</p>
                              <p className="text-white font-mono text-lg">{cmsData.total_results || 0}</p>
                            </div>
                            <div className="bg-gray-900 rounded p-3">
                              <p className="text-gray-400 text-sm mb-1">Total Providers:</p>
                              <p className="text-white font-mono text-lg">{cmsData.total_providers || cmsData.results?.length || 0}</p>
                            </div>
                            <div className="bg-gray-900 rounded p-3">
                              <p className="text-gray-400 text-sm mb-1">CPT Codes Searched:</p>
                              <p className="text-white font-mono text-lg">{cmsData.cpt_codes_searched?.length || 0}</p>
                            </div>
                          </div>

                          {/* Raw CMS API Results */}
                          <details className="bg-gray-900 rounded p-3 mt-4">
                            <summary className="cursor-pointer text-cyan-300 hover:text-cyan-200 font-semibold text-sm">
                              Raw CMS API Results ({cmsData.results?.length || 0} providers)
                            </summary>
                            <div className="mt-3 max-h-96 overflow-y-auto">
                              <div className="mb-3 flex items-center justify-between">
                                <p className="text-gray-400 text-xs">
                                  Showing all raw provider data from CMS API (unfiltered, ungrouped)
                                </p>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(JSON.stringify(cmsData.results, null, 2));
                                    alert('Raw CMS results copied to clipboard!');
                                  }}
                                  className="text-xs px-2 py-1 bg-cyan-600 hover:bg-cyan-700 text-white rounded transition-colors"
                                >
                                  Copy Raw Data
                                </button>
                              </div>
                              <div className="space-y-2">
                                {cmsData.results && cmsData.results.length > 0 ? (
                                  cmsData.results.map((provider: any, index: number) => (
                                    <details key={provider.Rndrng_NPI || index} className="bg-gray-800 rounded p-2 border-l-4 border-cyan-500">
                                      <summary className="cursor-pointer text-white hover:text-cyan-200 font-medium text-sm">
                                        {provider.Rndrng_Prvdr_First_Name || ''} {provider.Rndrng_Prvdr_Last_Org_Name || ''}
                                        {provider.Rndrng_NPI && (
                                          <span className="text-gray-400 ml-2">(NPI: {provider.Rndrng_NPI})</span>
                                        )}
                                        {provider.Tot_Srvcs && (
                                          <span className="text-cyan-300 ml-2">- {provider.Tot_Srvcs.toLocaleString()} services</span>
                                        )}
                                      </summary>
                                      <div className="mt-2">
                                        <pre className="text-xs text-gray-300 whitespace-pre-wrap bg-gray-900 p-2 rounded overflow-x-auto">
                                          {JSON.stringify(provider, null, 2)}
                                        </pre>
                                      </div>
                                    </details>
                                  ))
                                ) : (
                                  <p className="text-yellow-400 text-sm">No raw results available</p>
                                )}
                              </div>
                            </div>
                          </details>

                          {/* Error Display */}
                          {cmsData.error && (
                            <div className="bg-red-900/20 border border-red-500 rounded p-3">
                              <p className="text-red-400 text-sm font-semibold mb-1">Error:</p>
                              <p className="text-red-300 text-sm">{cmsData.error}</p>
                            </div>
                          )}

                          {/* CMS Results Table - Grouped by Provider */}
                          {cmsData.results && cmsData.results.length > 0 && (() => {
                            // State abbreviation mapping (full name to 2-letter code)
                            const stateAbbreviationMap: { [key: string]: string } = {
                              'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
                              'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
                              'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
                              'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
                              'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
                              'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
                              'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
                              'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
                              'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
                              'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
                              'District of Columbia': 'DC'
                            };
                            
                            // Get user's selected state and convert to 2-letter code
                            const userState = searchParams?.state || location.state?.state || '';
                            const userStateCode = userState.length === 2 
                              ? userState.toUpperCase() 
                              : (stateAbbreviationMap[userState] || userState.toUpperCase());
                            
                            // Debug logging
                            console.log('🔍 CMS Filter Debug:', {
                              userState,
                              userStateCode,
                              totalResults: cmsData.results?.length || 0,
                              sampleProviderStates: cmsData.results?.slice(0, 5).map((p: any) => p.Rndrng_Prvdr_State_Abrvtn) || []
                            });
                            
                            // Get user's neurosurgeon NPIs to filter out entities/facilities
                            const userProviderNPIs = new Set(
                              (providers || location.state?.providers || []).map((p: Provider) => String(p.npi))
                            );
                            
                            // Filter results by state AND by NPI (neurosurgeons only)
                            // Backend now filters by state before selecting top 25, so results should already be filtered
                            let filteredResults = userStateCode 
                              ? (cmsData.results || []).filter((provider: any) => {
                                  const providerState = (provider.Rndrng_Prvdr_State_Abrvtn || '').toUpperCase().trim();
                                  const providerNPI = String(provider.Rndrng_NPI || '');
                                  const matchesState = providerState === userStateCode;
                                  const isNeurosurgeon = userProviderNPIs.has(providerNPI);
                                  if (!matchesState && userStateCode) {
                                    console.log(`❌ Provider ${provider.Rndrng_Prvdr_First_Name} ${provider.Rndrng_Prvdr_Last_Org_Name} state mismatch: "${providerState}" !== "${userStateCode}"`);
                                  }
                                  if (!isNeurosurgeon) {
                                    console.log(`❌ Provider ${provider.Rndrng_Prvdr_First_Name} ${provider.Rndrng_Prvdr_Last_Org_Name} (NPI: ${providerNPI}) is not in user's search - excluding entity/facility`);
                                  }
                                  return matchesState && isNeurosurgeon;
                                })
                              : (cmsData.results || []).filter((provider: any) => {
                                  const providerNPI = String(provider.Rndrng_NPI || '');
                                  const isNeurosurgeon = userProviderNPIs.has(providerNPI);
                                  if (!isNeurosurgeon) {
                                    console.log(`❌ Provider ${provider.Rndrng_Prvdr_First_Name} ${provider.Rndrng_Prvdr_Last_Org_Name} (NPI: ${providerNPI}) is not in user's search - excluding entity/facility`);
                                  }
                                  return isNeurosurgeon;
                                });
                            
                            // If no results in selected state, show empty message (don't show all results)
                            const showAllResults = false; // Never show all results if filtering by state
                            
                            // Group CMS results by category
                            console.log('🔍 Debug: cptCodesByCategory keys:', Object.keys(cptCodesByCategory));
                            console.log('🔍 Debug: cptCodesByCategory values:', Object.keys(cptCodesByCategory).map(k => ({ category: k, count: cptCodesByCategory[k]?.length || 0 })));
                            
                            const cptToCategoryMap = getCptCodeToCategoryMap(cptCodesByCategory);
                            console.log('🔍 Debug: CPT to category map size:', Object.keys(cptToCategoryMap).length);
                            console.log('🔍 Debug: Sample CPT codes in map:', Object.keys(cptToCategoryMap).slice(0, 5));
                            
                            const resultsByCategory: { [category: string]: any[] } = {};
                            const uncategorizedResults: any[] = [];
                            
                            filteredResults.forEach((provider: any) => {
                              const providerCptCodes = Array.isArray(provider.HCPCS_Codes) ? provider.HCPCS_Codes : [];
                              const providerCategories = new Set<string>();
                              
                              providerCptCodes.forEach((code: string) => {
                                if (cptToCategoryMap[code]) {
                                  providerCategories.add(cptToCategoryMap[code]);
                                  console.log(`🔍 Provider ${provider.Rndrng_Prvdr_First_Name} ${provider.Rndrng_Prvdr_Last_Org_Name}: CPT code ${code} mapped to category ${cptToCategoryMap[code]}`);
                                }
                              });
                              
                              if (providerCategories.size > 0) {
                                // Provider has CPT codes that belong to categories
                                providerCategories.forEach(category => {
                                  if (!resultsByCategory[category]) {
                                    resultsByCategory[category] = [];
                                  }
                                  // Add provider to each category it belongs to
                                  resultsByCategory[category].push(provider);
                                });
                              } else {
                                // Provider has no categorized CPT codes
                                uncategorizedResults.push(provider);
                              }
                            });
                            
                            // Remove duplicates from each category (provider might appear in multiple categories)
                            Object.keys(resultsByCategory).forEach(category => {
                              const seen = new Set<string>();
                              resultsByCategory[category] = resultsByCategory[category].filter((provider: any) => {
                                const npi = provider.Rndrng_NPI;
                                if (seen.has(npi)) {
                                  return false;
                                }
                                seen.add(npi);
                                return true;
                              });
                            });
                            
                            const categories = Object.keys(resultsByCategory).sort();
                            
                            // Initialize selectedDebugCategory if not set and categories exist
                            if (categories.length > 0 && !selectedDebugCategory) {
                              setSelectedDebugCategory(categories[0]);
                            }
                            
                            return (
                              <div className="bg-gray-900 rounded p-3">
                                <div className="flex items-center justify-between mb-3">
                                  <p className="text-gray-400 text-sm font-semibold">
                                    {filteredResults.length} Providers by Total Services
                                    {userStateCode && !showAllResults && (
                                      <span className="text-gray-500 ml-2">in {userStateCode}</span>
                                    )}
                                    {cmsData.total_providers && cmsData.total_providers > filteredResults.length && (
                                      <span className="text-gray-500 ml-2">(of {cmsData.total_providers} total)</span>
                                    )}
                                  </p>
                                </div>
                                
                                {userStateCode && filteredResults.length === 0 && (
                                  <p className="text-yellow-400 text-sm mb-3">
                                    No providers found in {userStateCode} among the providers by total services.
                                  </p>
                                )}
                                
                                {/* Category Tabs for CMS Results */}
                                {categories.length > 0 && (
                                  <div className="mb-4 border-b border-gray-700">
                                    <div className="flex space-x-1 overflow-x-auto">
                                      {categories.map((category) => {
                                        const categoryResults = resultsByCategory[category] || [];
                                        const isSelected = selectedDebugCategory === category;
                                        return (
                                          <button
                                            key={category}
                                            onClick={() => setSelectedDebugCategory(category)}
                                            className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                              isSelected
                                                ? 'border-cyan-400 text-cyan-400'
                                                : 'border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-500'
                                            }`}
                                          >
                                            {category} ({categoryResults.length})
                                          </button>
                                        );
                                      })}
                                      {uncategorizedResults.length > 0 && (
                                        <button
                                          onClick={() => setSelectedDebugCategory('Uncategorized')}
                                          className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                                            selectedDebugCategory === 'Uncategorized'
                                              ? 'border-cyan-400 text-cyan-400'
                                              : 'border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-500'
                                          }`}
                                        >
                                          Uncategorized ({uncategorizedResults.length})
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                )}
                                
                                {filteredResults.length > 0 ? (
                                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                                    <table className="w-full text-sm">
                                      <thead className="bg-gray-800 sticky top-0">
                                        <tr>
                                          <th className="px-3 py-2 text-left text-cyan-400 font-semibold">Provider Name</th>
                                          <th className="px-3 py-2 text-left text-cyan-400 font-semibold">Location</th>
                                          <th className="px-3 py-2 text-left text-cyan-400 font-semibold">CPT Codes & Descriptions</th>
                                          <th className="px-3 py-2 text-right text-cyan-400 font-semibold">Total Services</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {(() => {
                                          // Show results for selected category, or all if no categories
                                          const displayResults = categories.length > 0 && selectedDebugCategory
                                            ? (selectedDebugCategory === 'Uncategorized' 
                                                ? uncategorizedResults 
                                                : (resultsByCategory[selectedDebugCategory] || []))
                                            : filteredResults;
                                          
                                          return displayResults.map((provider: any, index: number) => {
                                            const cptCodes = Array.isArray(provider.HCPCS_Codes) 
                                              ? provider.HCPCS_Codes 
                                              : [];
                                            const cptDescriptions = Array.isArray(provider.HCPCS_Descriptions)
                                              ? provider.HCPCS_Descriptions
                                              : [];
                                            
                                            // Pair up codes with descriptions by index (ensured 1:1 mapping from backend)
                                            const codeDescriptionPairs = cptCodes.map((code: string, idx: number) => ({
                                              code,
                                              description: idx < cptDescriptions.length ? cptDescriptions[idx] : null
                                            }));
                                            
                                            return (
                                              <tr key={provider.Rndrng_NPI || index} className="border-t border-gray-700 hover:bg-gray-800">
                                                <td className="px-3 py-2 text-white">
                                                  {provider.Rndrng_Prvdr_First_Name || ''} {provider.Rndrng_Prvdr_Last_Org_Name || ''}
                                                </td>
                                                <td className="px-3 py-2 text-gray-300">
                                                  {provider.Rndrng_Prvdr_City || 'N/A'}, {provider.Rndrng_Prvdr_State_Abrvtn || 'N/A'}
                                                </td>
                                                <td className="px-3 py-2 text-gray-300 max-w-lg">
                                                  <div className="space-y-2">
                                                    {codeDescriptionPairs.length > 0 ? (
                                                      codeDescriptionPairs.map((pair: { code: string; description: string | null }, pairIdx: number) => (
                                                        <div key={pairIdx} className="border-l-2 border-cyan-500 pl-2 py-1">
                                                          <div className="flex items-start gap-2">
                                                            <span className="text-cyan-300 font-mono text-xs bg-gray-800 px-1.5 py-0.5 rounded whitespace-nowrap">
                                                              {pair.code}
                                                            </span>
                                                            {pair.description ? (
                                                              <span className="text-gray-400 text-xs flex-1">
                                                                {pair.description}
                                                              </span>
                                                            ) : (
                                                              <span className="text-gray-500 text-xs italic">No description available</span>
                                                            )}
                                                          </div>
                                                        </div>
                                                      ))
                                                    ) : (
                                                      <span className="text-gray-500 text-xs">N/A</span>
                                                    )}
                                                  </div>
                                                </td>
                                                <td className="px-3 py-2 text-right text-white font-semibold">
                                                  {provider.Tot_Srvcs?.toLocaleString() || '0'}
                                                </td>
                                              </tr>
                                            );
                                          });
                                        })()}
                                    </tbody>
                                  </table>
                                </div>
                                ) : null}
                              </div>
                            );
                          })()}
                        </>
                      );
                    }
                    
                    return (
                      <p className="text-yellow-400">CMS API data not available (only available when specialists are searched)</p>
                    );
                  })()}
                </div>
              </div>

              {/* Raw API Response Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-red-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                  </svg>
                  7. Raw API Response Data
                </h3>
                <details className="bg-gray-900 rounded p-3">
                  <summary className="cursor-pointer text-blue-300 hover:text-blue-200 font-semibold">
                    View Full Specialist Recommendation Data
                  </summary>
                  <div className="mt-3 max-h-96 overflow-y-auto">
                    <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                      {JSON.stringify(location.state?.aiRecommendations, null, 2)}
                    </pre>
                  </div>
                </details>
              </div>
            </div>
          </div>
        )}
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
