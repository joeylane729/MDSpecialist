import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { NPIProvider, getSpecialistRecommendations, SpecialistRecommendationRequest, searchNPIProviders, rankNPIProviders, NPISearchRequest, NPIRankingRequest, ProviderContent, generateCPTCodes, getMedicalAnalysis } from '../services/api';
import NPIProviderCard from '../components/NPIProviderCard';

interface Provider extends NPIProvider {
  email?: string;
  website?: string;
  rating?: number;
  languages?: string[];
  insurance?: string[];
}

interface SearchParams {
  state: string;
  city: string;
  symptoms: string;
  diagnosis: string;
  determined_specialty?: string;
  predicted_icd10?: string;
  icd10_description?: string;
  treatment_options?: Array<{
    name: string;
    outcomes: string;
    complications: string;
    category?: string;
  }>;
  cpt_codes?: Array<{
    code: string;
    description: string;
  }>;
  cpt_prompt_text?: string;  // GPT prompt text used to generate CPT codes
  diagnoses_prompt_text?: string;  // GPT prompt text used to generate diagnoses/treatment options
  search_query?: string;  // Pre-generated search query for Pinecone
  searchOptions?: {
    diagnosis: boolean;
    specialists: boolean;
  };
}

interface TreatmentOption {
  name: string;
  outcomes: string;
  complications: string;
  category?: string;
}

// Function to get treatment options from GPT-generated data
const getTreatmentOptions = (searchParams: any, aiRecommendations?: any): TreatmentOption[] | null => {
  // Use GPT-generated treatment options if available from searchParams
  if (searchParams?.treatment_options && Array.isArray(searchParams.treatment_options) && searchParams.treatment_options.length > 0) {
    return searchParams.treatment_options.map((option: any) => ({
      name: option.name || "Treatment Option",
      outcomes: option.outcomes || "Outcomes not specified",
      complications: option.complications || "Complications not specified",
      category: option.category || "Other"
    }));
  }

  // Fallback to AI recommendations if searchParams doesn't have treatment options
  if (aiRecommendations?.patient_profile?.treatment_options && Array.isArray(aiRecommendations.patient_profile.treatment_options) && aiRecommendations.patient_profile.treatment_options.length > 0) {
    return aiRecommendations.patient_profile.treatment_options.map((option: any) => ({
      name: option.name || "Treatment Option",
      outcomes: option.outcomes || "Outcomes not specified",
      complications: option.complications || "Complications not specified",
      category: option.category || "Other"
    }));
  }

  // Return null if no treatment options found
  return null;
};

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

// Helper function to get categories from treatment options
const getCategoriesFromTreatmentOptions = (treatmentOptions: TreatmentOption[] | null): string[] => {
  if (!treatmentOptions || treatmentOptions.length === 0) return [];
  const categories = new Set<string>();
  treatmentOptions.forEach(option => {
    if (option.category) {
      categories.add(option.category);
    }
  });
  return Array.from(categories).sort();
};

const ResultsPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchParams, setSearchParams] = useState<SearchParams | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [providersPerPage, setProvidersPerPage] = useState(20);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTreatmentOptions, setSelectedTreatmentOptions] = useState<string[]>([]);
  const [isBackNavigation, setIsBackNavigation] = useState(false);
  const [rankedProviders, setRankedProviders] = useState<Provider[]>([]);
  const [filteredProviders, setFilteredProviders] = useState<Provider[]>([]);
  const [providerLinks, setProviderLinks] = useState<{ [npi: string]: ProviderContent }>({});
  const [providerScores, setProviderScores] = useState<{ [npi: string]: any }>({});
  const [treatmentRankings, setTreatmentRankings] = useState<{ [treatmentId: string]: any }>({});
  const [selectedTreatmentId, setSelectedTreatmentId] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>(''); // For specialists page filtering
  const [selectedDebugCategory, setSelectedDebugCategory] = useState<string>(''); // For debug page CMS results
  const [activeView, setActiveView] = useState<'assessment' | 'specialists' | 'ai-recommendations' | 'debug'>('assessment');
  const [specialistRecommendationData, setSpecialistRecommendationData] = useState<any>(null);
  const [cptCodes, setCptCodes] = useState<Array<{ code: string; description: string }> | null>(null);
  const [cptCodesByCategory, setCptCodesByCategory] = useState<{ [category: string]: Array<{ code: string; description: string }> }>({});
  const [cptPromptTextByCategory, setCptPromptTextByCategory] = useState<{ [category: string]: string }>({});
  const [editablePromptTextByCategory, setEditablePromptTextByCategory] = useState<{ [category: string]: string }>({});
  const [selectedCptCategory, setSelectedCptCategory] = useState<string | null>(null);
  const [cptPromptText, setCptPromptText] = useState<string | null>(null);
  const [editablePromptText, setEditablePromptText] = useState<string | null>(null);
  const [diagnosesPromptText, setDiagnosesPromptText] = useState<string | null>(null);
  const [editableDiagnosesPromptText, setEditableDiagnosesPromptText] = useState<string | null>(null);
  const [isGeneratingCPTCodes, setIsGeneratingCPTCodes] = useState(false);
  const [isGeneratingCPTCodesForCategory, setIsGeneratingCPTCodesForCategory] = useState<string | null>(null);
  const [isRegeneratingDiagnoses, setIsRegeneratingDiagnoses] = useState(false);
  const [isGeneratingSpecialists, setIsGeneratingSpecialists] = useState(false);
  const [selectedTreatmentIndices, setSelectedTreatmentIndices] = useState<Set<number>>(new Set());
  const hasInitializedTreatments = useRef(false);
  const hasInitializedCategoryFilter = useRef(false);
  
  // Set initial view based on search options
  useEffect(() => {
    if (searchParams?.searchOptions) {
      if (searchParams.searchOptions.specialists) {
        setActiveView('specialists');
      } else if (searchParams.searchOptions.diagnosis) {
        setActiveView('assessment');
      } else {
        setActiveView('ai-recommendations');
      }
    }
  }, [searchParams?.searchOptions]);
  
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
      console.log('ResultsPage - recommendations:', location.state.aiRecommendations.recommendations);
      
      // Debug treatment options specifically
      if (location.state.aiRecommendations.patient_profile?.treatment_options) {
        console.log('🔍 DEBUG: ResultsPage found treatment_options in aiRecommendations:', location.state.aiRecommendations.patient_profile.treatment_options);
      } else {
        console.log('🔍 DEBUG: ResultsPage - No treatment_options in aiRecommendations patient_profile');
      }
      
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
    
    // Debug searchParams treatment options
    if (searchParams?.treatment_options) {
      console.log('🔍 DEBUG: ResultsPage found treatment_options in searchParams:', searchParams.treatment_options);
    } else {
      console.log('🔍 DEBUG: ResultsPage - No treatment_options in searchParams');
      console.log('🔍 DEBUG: searchParams keys:', searchParams ? Object.keys(searchParams) : 'searchParams is null');
    }
    
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

  // Initialize cptCodesByCategory from treatment options and CMS CPT codes if empty
  useEffect(() => {
    // Only try to reconstruct if cptCodesByCategory is empty and we have treatment options
    if (Object.keys(cptCodesByCategory).length === 0) {
      const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
      const cmsData = location.state?.aiRecommendations?.cms_data || specialistRecommendationData?.cms_data;
      const cmsCptCodes = cmsData?.cpt_codes_searched;
      
      if (treatmentOptions && treatmentOptions.length > 0 && cmsCptCodes && Array.isArray(cmsCptCodes) && cmsCptCodes.length > 0) {
        console.log('⚠️ cptCodesByCategory is empty, attempting to reconstruct from treatment options and CMS CPT codes...');
        console.log('🔍 Treatment options:', treatmentOptions);
        console.log('🔍 CMS CPT codes searched:', cmsCptCodes);
        
        // Group treatment options by category
        const optionsByCategory: { [category: string]: TreatmentOption[] } = {};
        treatmentOptions.forEach(option => {
          const category = option.category || 'Other';
          if (!optionsByCategory[category]) {
            optionsByCategory[category] = [];
          }
          optionsByCategory[category].push(option);
        });
        
        console.log('🔍 Options by category:', Object.keys(optionsByCategory));
        
        // Note: We can't perfectly reconstruct without knowing which CPT codes belong to which category
        // This is a limitation - we'd need the actual mapping from when CPT codes were generated
        // For now, we'll log a warning
        console.warn('⚠️ Cannot fully reconstruct cptCodesByCategory - need actual CPT codes per category mapping');
      }
    }
  }, [searchParams, location.state, specialistRecommendationData, cptCodesByCategory]);

  // Initialize selected category when treatmentRankings are available
  useEffect(() => {
    if (Object.keys(treatmentRankings).length > 0 && !selectedCategory) {
      const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
      const categories = getCategoriesFromTreatmentOptions(treatmentOptions);
      if (categories.length > 0) {
        const firstCategory = categories[0];
        setSelectedCategory(firstCategory);
        console.log('🔍 Auto-selecting first category:', firstCategory);
      }
    }
  }, [treatmentRankings, selectedCategory, searchParams, location.state?.aiRecommendations]);

  // Apply category filter when selectedCategory is set for the first time
  useEffect(() => {
    if (selectedCategory && Object.keys(treatmentRankings).length > 0 && !hasInitializedCategoryFilter.current) {
      const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
      const categories = getCategoriesFromTreatmentOptions(treatmentOptions);
      
      if (categories.includes(selectedCategory)) {
        // Group treatments by category for the filter change handler
        const treatmentsByCategory: { [category: string]: Array<{ id: string; treatment: any }> } = {};
        Object.entries(treatmentRankings).forEach(([treatmentId, treatment]) => {
          const category = (treatment as any).category || 'Other';
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
    }
  }, [searchParams, cptCodes]);
  
  // Initialize diagnoses prompt text from searchParams if available
  useEffect(() => {
    if (searchParams?.diagnoses_prompt_text && !diagnosesPromptText) {
      setDiagnosesPromptText(searchParams.diagnoses_prompt_text);
      setEditableDiagnosesPromptText(searchParams.diagnoses_prompt_text);
    }
  }, [searchParams, diagnosesPromptText]);
  
  // Initialize selected treatment indices - all checked by default (only once)
  useEffect(() => {
    // Only initialize once, even if searchParams changes later
    if (hasInitializedTreatments.current) {
      return;
    }
    
    // Only run if we have searchParams or aiRecommendations
    if (!searchParams && !location.state?.aiRecommendations) {
      return;
    }
    
    const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
    if (treatmentOptions && treatmentOptions.length > 0) {
      // Only initialize if we don't have any selected yet
      if (selectedTreatmentIndices.size === 0) {
        // Set all treatment options as selected by default
        setSelectedTreatmentIndices(new Set(treatmentOptions.map((_, index) => index)));
        hasInitializedTreatments.current = true;
      }
    }
  }, [searchParams, location.state?.aiRecommendations, selectedTreatmentIndices.size]);

  // Initialize cptCodesByCategory from searchParams if available
  useEffect(() => {
    // Only initialize if cptCodesByCategory is empty and we have CPT codes in searchParams
    if (Object.keys(cptCodesByCategory).length === 0 && searchParams?.cpt_codes) {
      console.log('🔍 Attempting to initialize cptCodesByCategory from searchParams...');
      // Try to reconstruct from treatment options and CPT codes
      const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
      if (treatmentOptions && treatmentOptions.length > 0 && Array.isArray(searchParams.cpt_codes)) {
        // This is a fallback - ideally we'd have the actual category mapping
        // For now, we'll group by treatment option categories
        const reconstructed: { [category: string]: Array<{ code: string; description: string }> } = {};
        treatmentOptions.forEach(option => {
          const category = option.category || 'Other';
          if (!reconstructed[category]) {
            reconstructed[category] = [];
          }
          // Add all CPT codes to each category (this is approximate)
          // The real mapping should come from the actual CPT code generation
        });
        // Note: This won't work perfectly without the actual mapping
        console.log('⚠️ Cannot fully reconstruct cptCodesByCategory without category-specific CPT codes');
      }
    }
  }, [searchParams, location.state?.aiRecommendations, cptCodesByCategory]);

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
      breakdownParts.push(`  • Clinical Volume: 40%`);
      breakdownParts.push(`  • PubMed: 40%`);
      breakdownParts.push(`  • Training: 10%`);
      breakdownParts.push(`  • Experience: 6%`);
      breakdownParts.push(`  • Vumedi: 4%`);
      
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
    if (location.state?.searchParams && location.state.providers) {
      console.log('🔍 DEBUG: ResultsPage - location.state.searchParams:', location.state.searchParams);
      console.log('🔍 DEBUG: ResultsPage - search_query in searchParams:', location.state.searchParams.search_query);
      setSearchParams(location.state.searchParams);
      setProviders(location.state.providers);
      
      // Check if we have treatment rankings data to use for initial display
      if (location.state.treatmentRankings && Object.keys(location.state.treatmentRankings).length > 0) {
        console.log('🔍 Initializing with treatment rankings from location.state');
        setTreatmentRankings(location.state.treatmentRankings);
        
        // Use the first treatment's ranking as default
        const firstTreatmentId = Object.keys(location.state.treatmentRankings)[0];
        const firstTreatment = location.state.treatmentRankings[firstTreatmentId];
        setSelectedTreatmentId(firstTreatmentId);
        
        // Initialize selected category to first available category
        const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
        const categories = getCategoriesFromTreatmentOptions(treatmentOptions);
        if (categories.length > 0 && !selectedCategory) {
          const firstCategory = categories[0];
          setSelectedCategory(firstCategory);
          console.log('🔍 Initializing selected category to:', firstCategory);
        }
        
        // Get ranked providers for the first treatment
        const rankedNPIs = firstTreatment.ranked_providers;
        if (Array.isArray(rankedNPIs)) {
          const rankedNPIProviders = rankedNPIs.map((npi: string) => 
            location.state.providers.find((provider: Provider) => provider.npi === npi)
          ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
          setRankedProviders(rankedNPIProviders);
          console.log('🔍 Initial ranked providers from treatment rankings:', rankedNPIProviders.length);
        }
        
        // Set provider links for the first treatment
        setProviderLinks(firstTreatment.provider_links || {});
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
          setSearchParams(parsed.searchParams);
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
        symptoms: 'Fever, cough',
        diagnosis: 'A000',
        determined_specialty: 'Neurological Surgery'  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
      });
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

  const generateMockProviders = (params: SearchParams) => {
    setIsLoading(true);
    
    // Simulate API call delay
    setTimeout(() => {
      const mockProviders: Provider[] = [
        {
          id: '1',
          npi: '1234567890',
          name: 'Dr. Sarah Johnson',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
            residency: 'UCLA Medical Center'
          }
        },
        {
          id: '2',
          npi: '2345678901',
          name: 'Dr. Michael Chen',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
            residency: 'Cedars-Sinai Medical Center'
          }
        },
        {
          id: '3',
          npi: '3456789012',
          name: 'Dr. Emily Rodriguez',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
            residency: 'Johns Hopkins Hospital'
          }
        },
        {
          id: '4',
          npi: '4567890123',
          name: 'Dr. David Kim',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
            residency: 'UCLA Medical Center'
          }
        },
        {
          id: '5',
          npi: '5678901234',
          name: 'Dr. Lisa Thompson',
          specialty: 'Neurological Surgery',  // PROOF OF CONCEPT: Hard-coded to Neurological Surgery
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
      setIsRegeneratingDiagnoses(true);
      
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
        symptoms: searchParams.symptoms || location.state?.symptoms || '',
        diagnosis: searchParams.diagnosis || location.state?.diagnosis || '',
        medical_history: location.state?.medicalHistory || '',
        medications: location.state?.medications || '',
        surgical_history: location.state?.surgicalHistory || '',
        files: [], // Files are not persisted, so we can't include them in rerun
        custom_diagnoses_prompt: customPrompt
      });
      
      // Update searchParams with new results
      if (response.patient_profile) {
        const newSearchParams: SearchParams = {
          ...searchParams!,
          predicted_icd10: response.patient_profile.predicted_icd10,
          icd10_description: response.patient_profile.icd10_description,
          treatment_options: response.patient_profile.treatment_options,
          search_query: response.patient_profile.search_query,
          diagnoses_prompt_text: response.patient_profile.diagnoses_prompt_text
        };
        setSearchParams(newSearchParams);
        
        // Update prompt text state
        if (response.patient_profile.diagnoses_prompt_text) {
          setDiagnosesPromptText(response.patient_profile.diagnoses_prompt_text);
          // Only update editable prompt if we used the default (not custom), otherwise keep the edited version
          if (!useCustomPrompt) {
            setEditableDiagnosesPromptText(response.patient_profile.diagnoses_prompt_text);
          }
        }
        
        // Reset selected treatment indices since options may have changed
        if (response.patient_profile.treatment_options) {
          setSelectedTreatmentIndices(new Set(Array.from({length: response.patient_profile.treatment_options.length}, (_, i) => i)));
        }
        
        console.log('✅ Regenerated diagnoses and treatment options');
      }
    } catch (error) {
      console.error('Error regenerating diagnoses:', error);
      alert('Failed to regenerate diagnoses. Please try again.');
    } finally {
      setIsRegeneratingDiagnoses(false);
    }
  };

  const handleGenerateCPTCodes = async (useCustomPrompt: boolean = false, categoryFilter?: string) => {
    try {
      setIsGeneratingCPTCodes(true);
      
      // Get treatment options and search query from current data
      const allTreatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
      const searchQuery = searchParams?.search_query || location.state?.aiRecommendations?.patient_profile?.search_query;
      
      if (!allTreatmentOptions || allTreatmentOptions.length === 0) {
        alert('Treatment options are required to generate CPT codes');
        return;
      }
      
      // Filter to only selected treatment options
      let selectedTreatmentOptions = allTreatmentOptions.filter((_, index) => selectedTreatmentIndices.has(index));
      
      // Group selected treatment options by category
      const optionsByCategory: { [category: string]: TreatmentOption[] } = {};
      selectedTreatmentOptions.forEach(option => {
        const category = option.category || 'Other';
        if (!optionsByCategory[category]) {
          optionsByCategory[category] = [];
        }
        optionsByCategory[category].push(option);
      });
      
      // If a specific category is requested, only generate for that category
      const categoriesToGenerate = categoryFilter ? [categoryFilter] : Object.keys(optionsByCategory);
      
      if (categoriesToGenerate.length === 0) {
        alert('Please select at least one treatment option to generate CPT codes');
        return;
      }
      
      if (!searchQuery) {
        alert('Search query is required to generate CPT codes');
        return;
      }
      
      // Generate CPT codes for each category
      const newCptCodesByCategory: { [category: string]: Array<{ code: string; description: string }> } = {};
      const newCptPromptTextByCategory: { [category: string]: string } = {};
      
      for (const category of categoriesToGenerate) {
        const categoryOptions = optionsByCategory[category];
        if (!categoryOptions || categoryOptions.length === 0) continue;
        
        setIsGeneratingCPTCodesForCategory(category);
        
        // Use custom prompt if rerunning with edited prompt, otherwise use default (undefined)
        const customPrompt = useCustomPrompt && editablePromptText ? editablePromptText : undefined;
        
        try {
          const response = await generateCPTCodes({
            search_query: searchQuery,
            treatment_options: categoryOptions,
            custom_prompt: customPrompt
          });
          
          if (response.cpt_codes && response.cpt_codes.length > 0) {
            newCptCodesByCategory[category] = response.cpt_codes;
            newCptPromptTextByCategory[category] = response.cpt_prompt_text || '';
            // Initialize editable prompt text for this category
            setEditablePromptTextByCategory(prev => ({
              ...prev,
              [category]: response.cpt_prompt_text || ''
            }));
            console.log(`✅ Generated ${response.cpt_codes.length} CPT codes for category: ${category}`);
          } else {
            console.warn(`⚠️  Received 0 CPT codes for category: ${category}`);
          }
        } catch (error) {
          console.error(`❌ Error generating CPT codes for category ${category}:`, error);
        }
      }
      
      // Update state with all categories
      setCptCodesByCategory(prev => ({ ...prev, ...newCptCodesByCategory }));
      setCptPromptTextByCategory(prev => ({ ...prev, ...newCptPromptTextByCategory }));
      
      // Set first category as selected if none selected yet
      if (!selectedCptCategory && Object.keys(newCptCodesByCategory).length > 0) {
        setSelectedCptCategory(Object.keys(newCptCodesByCategory)[0]);
      }
      
      // Combine all CPT codes for backward compatibility and CMS API call
      const allCptCodes = Object.values(newCptCodesByCategory).flat();
      if (allCptCodes.length > 0) {
        setCptCodes(allCptCodes);
        
        // Update searchParams to include combined CPT codes
        if (searchParams) {
          setSearchParams({
            ...searchParams,
            cpt_codes: allCptCodes
          });
        }
        
        console.log(`✅ Generated total ${allCptCodes.length} CPT codes across ${Object.keys(newCptCodesByCategory).length} categories`);
      }
      
    } catch (error) {
      console.error('❌ Error generating CPT codes:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      alert('Failed to generate CPT codes: ' + errorMessage);
    } finally {
      setIsGeneratingCPTCodes(false);
      setIsGeneratingCPTCodesForCategory(null);
    }
  };

  const handleShowSpecialists = async () => {
    // If specialists are already available, just switch to the view
    if (searchParams?.searchOptions?.specialists && filteredProviders.length > 0) {
      setActiveView('specialists');
      return;
    }

    // Check if CPT codes are available - combine all categories if category-based codes exist
    let existingCptCodes = cptCodes || searchParams?.cpt_codes || 
                              location.state?.aiRecommendations?.patient_profile?.cpt_codes;
    
    // If we have category-based codes, combine them all
    if (Object.keys(cptCodesByCategory).length > 0) {
      const allCategoryCodes = Object.values(cptCodesByCategory).flat();
      if (allCategoryCodes.length > 0) {
        existingCptCodes = allCategoryCodes;
      }
    }
    
    if (!existingCptCodes || existingCptCodes.length === 0) {
      alert('Please generate CPT codes first before getting specialist recommendations');
      return;
    }

    // If specialists haven't been generated yet, call the APIs
    try {
      setIsGeneratingSpecialists(true);
      
      // Step 1: Get specialist recommendations
      // Reuse CPT codes from state or medical analysis to avoid duplicate generation
      const specialistRequest: SpecialistRecommendationRequest = {
        symptoms: searchParams?.symptoms || '',
        diagnosis: searchParams?.diagnosis || '',
        medical_history: location.state?.medicalHistory || '',
        medications: location.state?.medications || '',
        surgical_history: location.state?.surgicalHistory || '',
        state: searchParams?.state || location.state?.state || '',
        files: [],
        cpt_codes: existingCptCodes  // Pass existing CPT codes to reuse them
      };

      if (existingCptCodes && existingCptCodes.length > 0) {
        console.log('♻️ [Frontend] Reusing', existingCptCodes.length, 'CPT codes for specialist recommendations');
      }

      const specialistResponse = await getSpecialistRecommendations(specialistRequest);
      
      // Store the specialist response for debug display
      setSpecialistRecommendationData(specialistResponse);
      
      // Step 2: Search for NPI providers
      const npiSearchRequest: NPISearchRequest = {
        state: searchParams?.state || '',
        city: searchParams?.city || '',
        zipCode: location.state?.zipCode || '',
        proximity: location.state?.proximity || 'statewide',
        diagnosis: searchParams?.diagnosis || '',
        symptoms: searchParams?.symptoms || '',
        uploadedFiles: [],
        limit: 10000  // Increase limit to get all available providers
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
      
      const rankingRequest: NPIRankingRequest = {
        npi_providers: npiData.providers,
        patient_input: `Symptoms: ${searchParams?.symptoms}\nDiagnosis: ${searchParams?.diagnosis}`,
        shared_specialist_information: specialistResponse.shared_specialist_information || [],
        cms_data: specialistResponse.cms_data // Pass CMS data for clinical volume bonus
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
        
        // Use the first treatment's ranking as default
        const firstTreatmentId = Object.keys(treatmentRankingsData)[0];
        const firstTreatment = treatmentRankingsData[firstTreatmentId];
        
        console.log('🔍 First treatment ID:', firstTreatmentId);
        console.log('🔍 First treatment data:', firstTreatment);
        
        // Set the selected treatment
        setSelectedTreatmentId(firstTreatmentId);
        
        const rankedNPIs = firstTreatment.ranked_providers;
        if (Array.isArray(rankedNPIs)) {
          rankedNPIProviders = rankedNPIs.map((npi: string) => 
            providerLookup.get(npi)
          ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
          setRankedProviders(rankedNPIProviders);
          console.log('🔍 Initial ranked providers:', rankedNPIProviders.length);
        }
        
        // Capture the provider links and scores
        providerLinks = firstTreatment.provider_links || {};
        const providerScores = firstTreatment.provider_scores || {};
        
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
      
      // Update the search params to include specialists
      // This will trigger the useEffect to switch to specialists view
      setSearchParams(prev => ({
        ...prev!,
        searchOptions: {
          ...prev!.searchOptions!,
          specialists: true
        }
      }));
      
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

  const handleCategoryFilterChange = (category: string, treatmentsByCategory: { [category: string]: Array<{ id: string; treatment: any }> }) => {
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
    
    // Always require a category - modify ONLY clinical volume based on category-specific CPT codes
    if (category) {
      // Modify ONLY clinical volume based on category-specific CPT codes
      const categoryCptCodes = cptCodesByCategory[category] || [];
      const categoryCptCodeSet = new Set(categoryCptCodes.map(cpt => cpt.code));
      
      // Get CMS data to filter clinical volume by category
      const cmsData = specialistRecommendationData?.cms_data || location.state?.aiRecommendations?.cms_data;
      const cmsProvidersByNpi: { [npi: string]: any } = {};
      if (cmsData?.results) {
        cmsData.results.forEach((provider: any) => {
          const npi = provider.Rndrng_NPI;
          if (npi) {
            if (!cmsProvidersByNpi[npi]) {
              cmsProvidersByNpi[npi] = [];
            }
            cmsProvidersByNpi[npi].push(provider);
          }
        });
      }
      
      // First, calculate the max Tot_Srvcs for this category across all providers
      // This ensures all providers are compared against the same max value
      const providerCategoryTotSrvcs: { [npi: string]: number } = {};
      
      // Calculate Tot_Srvcs per provider for this category
      // CMS data has one row per provider-CPT code combination, so we need to sum Tot_Srvcs
      // for each provider where the CPT code matches the selected category
      Object.keys(cmsProvidersByNpi).forEach(providerNpi => {
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
      
      // Find the max Tot_Srvcs for this category
      const maxCategoryTotSrvcs = Object.values(providerCategoryTotSrvcs).length > 0 
        ? Math.max(...Object.values(providerCategoryTotSrvcs)) 
        : 1;
      
      // Now, filter clinical volume based on category CPT codes for each provider
      Object.keys(filteredProviderScores).forEach(npi => {
        const scoreData = filteredProviderScores[npi];
        const categoryTotSrvcs = providerCategoryTotSrvcs[npi] || 0;
        const hasCategoryCptCodes = categoryTotSrvcs > 0;
        
        if (hasCategoryCptCodes && scoreData.weighted_breakdown) {
          // Calculate percentage based on max Tot_Srvcs for this category only
          const categoryPct = maxCategoryTotSrvcs > 0 ? (categoryTotSrvcs / maxCategoryTotSrvcs) : 0;
          
          // Update the weighted breakdown
          if (scoreData.weighted_breakdown.breakdown_details?.clinical_volume) {
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.raw = categoryTotSrvcs;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.max_raw = maxCategoryTotSrvcs;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentage = categoryPct * 100;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points = categoryPct * 40;
            
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
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.raw = 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.max_raw = maxCategoryTotSrvcs; // Still set max so percentage calculation is correct
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.percentage = 0;
            scoreData.weighted_breakdown.breakdown_details.clinical_volume.weighted_points = 0;
            
            // Recalculate final score without clinical volume
            const pubmed = scoreData.weighted_breakdown.breakdown_details.pubmed?.weighted_points || 0;
            const training = scoreData.weighted_breakdown.breakdown_details.training?.weighted_points || 0;
            const experience = scoreData.weighted_breakdown.breakdown_details.experience?.weighted_points || 0;
            const vumedi = scoreData.weighted_breakdown.breakdown_details.vumedi?.weighted_points || 0;
            scoreData.weighted_breakdown.final_score = pubmed + training + experience + vumedi;
            scoreData.score = scoreData.weighted_breakdown.final_score;
          }
        }
      });
    }
    
    setRankedProviders(allProviders);
    setProviderLinks(allProviderLinks);
    setProviderScores(filteredProviderScores);
    
    setCurrentPage(1);
    saveFilterState();
  };

  const handleTreatmentFilterChange = (treatmentId: string) => {
    console.log('🔍 Treatment filter changed to:', treatmentId);
    console.log('🔍 Available treatment rankings:', treatmentRankings);
    console.log('🔍 Available providers:', providers.length);
    
    setSelectedTreatmentId(treatmentId);
    
    // Update ranked providers based on selected treatment
    if (treatmentRankings[treatmentId]) {
      const treatment = treatmentRankings[treatmentId];
      const rankedNPIs = treatment.ranked_providers;
      
      console.log('🔍 Treatment data:', treatment);
      console.log('🔍 Ranked NPIs:', rankedNPIs);
      
      // Find the original NPI providers from the current providers state
      const originalProviders = providers || [];
      const rankedNPIProviders = rankedNPIs.map((npi: string) => 
        originalProviders.find((provider: Provider) => provider.npi === npi)
      ).filter((provider: Provider | undefined): provider is NPIProvider => provider !== undefined);
      
      console.log('🔍 Filtered providers:', rankedNPIProviders.length);
      
      setRankedProviders(rankedNPIProviders);
      setProviderLinks(treatment.provider_links || {});
      setProviderScores(treatment.provider_scores || {});
    } else {
      console.log('🔍 No treatment data found for ID:', treatmentId);
    }
    
    setCurrentPage(1);
    saveFilterState();
  };

  const resetFilters = () => {
    setSearchTerm('');
    setSelectedTreatmentOptions([]);
    setSelectedTreatmentId('');
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
            {searchParams?.searchOptions?.diagnosis && (
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
            {searchParams?.searchOptions?.specialists && (
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
            <button
              onClick={() => setActiveView('ai-recommendations')}
              className={`hidden flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                activeView === 'ai-recommendations'
                  ? 'text-primary-600 bg-primary-50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span>AI Recommendations</span>
            </button>
            {(searchParams?.searchOptions?.specialists && specialistRecommendationData) && (
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
        {activeView === 'assessment' && searchParams?.searchOptions?.diagnosis && (searchParams?.icd10_description || location.state?.aiRecommendations?.patient_profile?.icd10_description) && (
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

                  {/* Medical Analysis Results */}
                  {searchParams?.icd10_description && (
                    <div className="border-l-4 border-green-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-2">Medical Analysis</h3>
                      <div className="space-y-2">
                        {searchParams.predicted_icd10 && (
                          <div>
                            <span className="font-medium text-gray-700">ICD-10 Code: </span>
                            <code className="bg-gray-100 px-2 py-1 rounded text-sm">{searchParams.predicted_icd10}</code>
                          </div>
                        )}
                        <div>
                          <span className="font-medium text-gray-700">Description: </span>
                          <span className="text-gray-700">{searchParams.icd10_description}</span>
                        </div>
                      </div>
                    </div>
                  )}



                  {/* Search Query */}
                  {searchParams?.search_query && (
                    <div className="border-l-4 border-indigo-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-2">Search Query Variations</h3>
                      <div className="bg-gray-50 p-3 rounded-lg">
                        <p className="text-sm text-gray-600 mb-2">The following search terms will be used to find relevant specialists:</p>
                        <div className="text-sm text-gray-800 font-mono break-words">
                          {searchParams?.search_query}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Determined Specialty */}
                  {searchParams?.determined_specialty && (
                    <div className="border-l-4 border-purple-500 pl-4">
                      <h3 className="text-lg font-medium text-gray-900 mb-2">Recommended Specialty</h3>
                      <p className="text-gray-700">{searchParams.determined_specialty}</p>
                    </div>
                  )}
                </div>
              </div>
              {/* Treatment Options with Outcomes and Complications */}
              <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">Treatment Options</h2>
              
              {/* GPT Prompt Instructions for Diagnoses/Treatment (collapsed by default) */}
              {(diagnosesPromptText || searchParams?.diagnoses_prompt_text) && (
                <div className="mb-4">
                  <details className="bg-gray-50 rounded-lg border border-gray-200">
                    <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                      <span className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        View GPT Prompt Instructions (for debugging)
                      </span>
                    </summary>
                    <div className="p-4 border-t border-gray-200">
                      <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to generate the diagnoses and treatment options:</p>
                      <textarea
                        className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                        value={editableDiagnosesPromptText || diagnosesPromptText || searchParams?.diagnoses_prompt_text || ''}
                        onChange={(e) => setEditableDiagnosesPromptText(e.target.value)}
                        placeholder="Prompt text..."
                      />
                      <div className="mt-3 flex justify-end">
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.preventDefault();
                            await handleRegenerateDiagnoses(true);
                          }}
                          disabled={isRegeneratingDiagnoses || !editableDiagnosesPromptText}
                          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                        >
                          {isRegeneratingDiagnoses ? (
                            <span className="flex items-center gap-2">
                              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Regenerating...
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
              {(() => {
                const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
                if (treatmentOptions && treatmentOptions.length > 0) {
                  return (
                    <div className="space-y-3">
                      {treatmentOptions.map((treatment, index) => {
                        const isChecked = selectedTreatmentIndices.has(index);
                        return (
                          <div key={index} className={`p-3 rounded-lg border-2 transition-colors ${isChecked ? 'bg-gray-50 border-blue-500' : 'bg-gray-50 border-gray-200'}`}>
                            <div className="flex items-start gap-3">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => {
                                  const newSelected = new Set(selectedTreatmentIndices);
                                  if (e.target.checked) {
                                    newSelected.add(index);
                                  } else {
                                    newSelected.delete(index);
                                  }
                                  setSelectedTreatmentIndices(newSelected);
                                }}
                                className="mt-1 h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                              />
                              <span className="text-sm text-gray-700 font-bold">{index + 1}.</span>
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-2">
                                  <h4 className="font-medium text-gray-900 text-sm">{treatment.name}</h4>
                                  {treatment.category && (
                                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs font-medium rounded-full">
                                      {treatment.category}
                                    </span>
                                  )}
                                </div>
                                <div className="grid grid-cols-2 gap-4 text-xs text-gray-600">
                                  <div><span className="font-medium">Outcomes:</span> {treatment.outcomes}</div>
                                  <div><span className="font-medium">Complications:</span> {treatment.complications}</div>
                                </div>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                } else {
                  return (
                    <div className="text-center py-8">
                      <div className="text-gray-500 mb-2">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                      </div>
                      <p className="text-gray-500 text-sm">No treatment options were generated for this case.</p>
                      <p className="text-gray-400 text-xs mt-1">Please consult with a healthcare provider for personalized treatment recommendations.</p>
                    </div>
                  );
                }
              })()}
              </div>
              
              {/* Button to generate CPT codes */}
              {(() => {
                const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
                const searchQuery = searchParams?.search_query || location.state?.aiRecommendations?.patient_profile?.search_query;
                const existingCptCodes = cptCodes || searchParams?.cpt_codes;
                const hasCptCodes = Array.isArray(existingCptCodes) && existingCptCodes.length > 0;
                const hasCptCodesByCategory = Object.keys(cptCodesByCategory).length > 0;
                
                // Show button if we have treatment options
                if (!treatmentOptions || treatmentOptions.length === 0) {
                  return null;
                }
                
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
              
              {/* CPT Codes Section - only show if we have actual CPT codes */}
              {(() => {
                const hasCptCodesByCategory = Object.keys(cptCodesByCategory).length > 0;
                const existingCptCodes = cptCodes || searchParams?.cpt_codes;
                const hasCptCodes = Array.isArray(existingCptCodes) && existingCptCodes.length > 0;
                
                // Prefer category-based codes if available, otherwise fall back to legacy format
                const categories = hasCptCodesByCategory ? Object.keys(cptCodesByCategory) : [];
                const displayCategory = selectedCptCategory || (categories.length > 0 ? categories[0] : null);
                
                if (!hasCptCodesByCategory && !hasCptCodes) {
                  return null;
                }
                
                return (
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-2xl font-semibold text-gray-900">Relevant CPT Codes</h2>
                    {hasCptCodesByCategory && (
                      <div className="text-sm text-gray-600">
                        Total: {Object.values(cptCodesByCategory).flat().length} codes across {categories.length} {categories.length === 1 ? 'category' : 'categories'}
                      </div>
                    )}
                  </div>
                  
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
                  
                  {/* GPT Prompt Instructions (collapsed by default) */}
                  {displayCategory && cptPromptTextByCategory[displayCategory] && (
                    <div className="mb-4">
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            View GPT Prompt Instructions for {displayCategory} (for debugging)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to generate the CPT codes for {displayCategory}:</p>
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
                                await handleGenerateCPTCodes(true, displayCategory);
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
                    </div>
                  )}
                  
                  {/* Fallback prompt section for legacy format */}
                  {!hasCptCodesByCategory && (cptPromptText || searchParams?.cpt_prompt_text) && (
                    <div className="mb-4">
                      <details className="bg-gray-50 rounded-lg border border-gray-200">
                        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-t-lg">
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            View GPT Prompt Instructions (for debugging)
                          </span>
                        </summary>
                        <div className="p-4 border-t border-gray-200">
                          <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to generate the CPT codes:</p>
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
                    </div>
                  )}
                  
                  <div className="text-sm text-gray-600 mb-3">
                    {displayCategory 
                      ? `Procedural codes for ${displayCategory} category:`
                      : 'Procedural codes that could be used by a neurosurgeon to treat this condition:'}
                  </div>
                  
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {(hasCptCodesByCategory && displayCategory && cptCodesByCategory[displayCategory]
                      ? cptCodesByCategory[displayCategory]
                      : (cptCodes || searchParams?.cpt_codes || [])
                    ).map((cpt: any, index: number) => (
                      <div key={index} className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                        <div className="flex items-start gap-3">
                          <code className="bg-amber-100 px-2 py-1 rounded text-sm font-semibold text-amber-900 whitespace-nowrap">
                            {cpt.code}
                          </code>
                          <span className="text-sm text-gray-700 flex-1">{cpt.description}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  
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
        {activeView === 'specialists' && searchParams?.searchOptions?.specialists && (
          <>
            {/* Specialists Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-blue-800 to-indigo-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                {searchParams?.determined_specialty ? `${searchParams.determined_specialty} Specialists` : 'Specialists'}
              </h1>
              

        </div>

        {/* Search and Filter Controls */}
        <div className="py-2 mb-3">
          <div className="flex items-center gap-3 justify-center">
            {/* Search */}
            <div className="flex-1 max-w-md">
              <div className="relative">
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
                  className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200 bg-white/50"
                />
                <svg className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
            </div>

            {/* Compare Outcomes Button */}
            <button
              onClick={() => {
                // TODO: Implement compare outcomes functionality
                console.log('Compare outcomes clicked');
              }}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 bg-white/50 border border-gray-300 rounded-lg hover:bg-gray-50 hover:text-gray-800 transition-colors"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Compare Outcomes
            </button>

            {/* Category Dropdown */}
            {(() => {
              const treatmentOptions = getTreatmentOptions(searchParams, location.state?.aiRecommendations);
              const categories = getCategoriesFromTreatmentOptions(treatmentOptions);
              
              if (categories.length > 0 && Object.keys(treatmentRankings).length > 0) {
                // Group treatments by category
                const treatmentsByCategory: { [category: string]: Array<{ id: string; treatment: any }> } = {};
                Object.entries(treatmentRankings).forEach(([treatmentId, treatment]) => {
                  const category = (treatment as any).category || 'Other';
                  if (!treatmentsByCategory[category]) {
                    treatmentsByCategory[category] = [];
                  }
                  treatmentsByCategory[category].push({ id: treatmentId, treatment });
                });
                
                return (
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <svg className="h-4 w-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                      </svg>
                      <span className="text-sm font-medium text-gray-700">Category:</span>
                    </div>
                    <select
                      value={selectedCategory || categories[0] || ''}
                      onChange={(e) => {
                        const category = e.target.value;
                        if (category) {
                          setSelectedCategory(category);
                          handleCategoryFilterChange(category, treatmentsByCategory);
                        }
                      }}
                      className={`px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm bg-white/50 ${
                        selectedCategory || categories[0]
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-300'
                      }`}
                    >
                      {categories.map((category) => (
                        <option key={category} value={category}>
                          {category}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              }
              return null;
            })()}

            {/* Reset Button */}
            <button
              onClick={resetFilters}
              className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-50 transition-colors rounded-lg font-medium text-sm"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reset
            </button>
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
            const isTopResult = rank === 1;
            const scoreData = providerScores[provider.npi];
            const isCertified = scoreData?.is_certified === true || scoreData?.certification_points > 0;
            
            return (
              <div key={provider.id} className="relative">
                {/* Top result indicator */}
                {isTopResult && (
                  <div className="absolute -right-2 -top-2 bg-gradient-to-r from-yellow-400 to-yellow-600 text-white px-3 py-1 rounded-full text-xs font-bold shadow-lg z-10 flex items-center gap-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                    BEST
                  </div>
                )}
                
                <NPIProviderCard
                  key={`${provider.npi}-${selectedCategory || 'all'}`}
                  provider={provider}
                  onClick={handleProviderClick}
                  isHighlighted={isTopResult}
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


        {/* AI Recommendations Section */}
        {activeView === 'ai-recommendations' && (
          <>
            {/* AI Recommendations Header */}
            <div className="text-center mb-4">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-gray-900 via-purple-800 to-pink-800 bg-clip-text text-transparent mb-3 leading-tight py-1">
                AI-Powered Specialist Recommendations
              </h1>
              <p className="text-lg text-gray-600 max-w-2xl mx-auto">
                Based on your symptoms and diagnosis, our AI has analyzed medical content to recommend relevant specialists
              </p>
            </div>

            {/* Debug Info */}
            {!location.state?.aiRecommendations && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                <h3 className="text-red-800 font-semibold">Debug: No AI Recommendations Data</h3>
                <p className="text-red-700">location.state: {JSON.stringify(location.state, null, 2)}</p>
              </div>
            )}

            {location.state?.aiRecommendations && !location.state.aiRecommendations.recommendations && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <h3 className="text-yellow-800 font-semibold">Debug: No Recommendations Array</h3>
                <p className="text-yellow-700">aiRecommendations: {JSON.stringify(location.state.aiRecommendations, null, 2)}</p>
              </div>
            )}

            {/* AI Recommendations Content */}
            {location.state?.aiRecommendations ? (
              <div className="space-y-6">
                {/* Patient Profile Summary */}
                <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-200">
                  <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                    <svg className="w-5 h-5 mr-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    Patient Profile Analysis
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="font-medium text-gray-700 mb-2">Symptoms Identified:</h4>
                      <div className="flex flex-wrap gap-2">
                        {location.state.aiRecommendations.patient_profile.symptoms.map((symptom: string, index: number) => (
                          <span key={index} className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm">
                            {symptom}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-700 mb-2">Specialties Needed:</h4>
                      <div className="flex flex-wrap gap-2">
                        {location.state.aiRecommendations.patient_profile.specialties_needed.map((specialty: string, index: number) => (
                          <span key={index} className="bg-pink-100 text-pink-800 px-3 py-1 rounded-full text-sm">
                            {specialty}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Summary Stats */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-purple-600">{location.state.aiRecommendations.recommendations.length}</div>
                    <div className="text-sm text-gray-600">Specialists Recommended</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-pink-600">{location.state.aiRecommendations.total_candidates_found}</div>
                    <div className="text-sm text-gray-600">Medical Records Analyzed</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                    <div className="text-2xl font-bold text-indigo-600">{Math.round(location.state.aiRecommendations.processing_time_ms / 1000)}s</div>
                    <div className="text-sm text-gray-600">Processing Time</div>
                  </div>
                </div>

                {/* Specialist Recommendations */}
                <div className="space-y-4">
                  <h3 className="text-2xl font-semibold text-gray-800 mb-4">Recommended Specialists</h3>
                  
                  {location.state.aiRecommendations.recommendations && location.state.aiRecommendations.recommendations.length > 0 ? (
                    location.state.aiRecommendations.recommendations.map((recommendation: any, index: number) => (
                    <div key={index} className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex-1">
                          <h4 className="text-xl font-semibold text-gray-800 mb-2">{recommendation.name}</h4>
                          <p className="text-gray-600 mb-2">{recommendation.specialty}</p>
                          <p className="text-sm text-gray-500 mb-3">{recommendation.reasoning}</p>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-purple-600">
                            {Math.round(recommendation.confidence_score * 100)}%
                          </div>
                          <div className="text-sm text-gray-500">Confidence</div>
                        </div>
                      </div>
                      
                      {/* Source Information */}
                      {recommendation.metadata && (
                        <div className="bg-gray-50 rounded-lg p-4">
                          <h5 className="font-medium text-gray-700 mb-2">Source Information:</h5>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div>
                              <span className="font-medium">Content:</span> {recommendation.metadata.title}
                            </div>
                            <div>
                              <span className="font-medium">Author:</span> {recommendation.metadata.author}
                            </div>
                            <div>
                              <span className="font-medium">Date:</span> {recommendation.metadata.date}
                            </div>
                            <div>
                              <span className="font-medium">Duration:</span> {recommendation.metadata.duration}
                            </div>
                          </div>
                          {recommendation.metadata.link && (
                            <div className="mt-3">
                              <a 
                                href={recommendation.metadata.link} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-purple-600 hover:text-purple-800 text-sm font-medium"
                              >
                                View Source Content →
                              </a>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                  ) : (
                    <div className="text-center py-12">
                      <div className="text-gray-400 text-6xl mb-4">📋</div>
                      <h3 className="text-xl font-semibold text-gray-700 mb-2">No Specialist Recommendations Found</h3>
                      <p className="text-gray-500">The AI analysis did not find specific specialist recommendations for your condition.</p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <div className="text-gray-400 text-6xl mb-4">🤖</div>
                <h3 className="text-xl font-semibold text-gray-700 mb-2">No AI Recommendations Available</h3>
                <p className="text-gray-500">AI recommendations were not generated for this search.</p>
              </div>
            )}
          </>
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
                      icd10Code: searchParams?.predicted_icd10,
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
                    <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">{searchParams?.predicted_icd10 || 'N/A'}</p>
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
                    
                    let pineconeResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        pineconeResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      pineconeResults = sharedInfo;
                    }
                    
                    if (pineconeResults && Array.isArray(pineconeResults)) {
                      const pubmedArticles = pineconeResults.filter((item: any) => item._source === 'pubmed');
                      
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
                      <p className="text-yellow-400">No PubMed articles found in Pinecone results</p>
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
                    
                    let pineconeResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        pineconeResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      pineconeResults = sharedInfo;
                    }
                    
                    if (pineconeResults && Array.isArray(pineconeResults)) {
                      const vumediVideos = pineconeResults.filter((item: any) => item._source === 'vumedi');
                      
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
                      <p className="text-yellow-400">No Vumedi videos found in Pinecone results</p>
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
                    <p className="text-gray-400 mb-2">Pinecone Search Query:</p>
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

              {/* Pinecone Summary Section */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-green-400 mb-3 flex items-center gap-2">
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  5. Pinecone Search Results Summary
                </h3>
                <div className="space-y-3">
                  {(() => {
                    const sharedInfo = 
                      specialistRecommendationData?.shared_specialist_information ||
                      location.state?.aiRecommendations?.shared_specialist_information;
                    
                    let pineconeResults: any[] = [];
                    if (sharedInfo && typeof sharedInfo === 'object') {
                      const treatmentKeys = Object.keys(sharedInfo);
                      if (treatmentKeys.length > 0) {
                        const firstTreatment = sharedInfo[treatmentKeys[0]];
                        pineconeResults = firstTreatment?.results || [];
                      }
                    } else if (Array.isArray(sharedInfo)) {
                      pineconeResults = sharedInfo;
                    }
                    
                    if (pineconeResults && Array.isArray(pineconeResults) && pineconeResults.length > 0) {
                      const verifiedResults = pineconeResults.filter((item: any) => item._verified === true);
                      const unverifiedResults = pineconeResults.filter((item: any) => item._verified !== true);
                      
                      return (
                        <>
                          <div className="grid grid-cols-4 gap-4 text-sm mb-2">
                            <div>
                              <span className="text-gray-400">Total Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {pineconeResults.length}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-400">Vumedi Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {pineconeResults.filter((item: any) => item._source === 'vumedi').length}
                              </p>
                            </div>
                            <div>
                              <span className="text-gray-400">PubMed Results:</span>
                              <p className="text-white font-mono bg-gray-900 p-2 rounded mt-1">
                                {pineconeResults.filter((item: any) => item._source === 'pubmed').length}
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
                              View All Pinecone Results ({pineconeResults.length} items)
                            </summary>
                            <div className="mt-3 max-h-96 overflow-y-auto space-y-2">
                              {pineconeResults.map((result: any, index: number) => (
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
                      <p className="text-yellow-400">No Pinecone search results available</p>
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
                            
                            // Filter results by state (backend should already filter, but keep as safety net)
                            // Backend now filters by state before selecting top 25, so results should already be filtered
                            let filteredResults = userStateCode 
                              ? (cmsData.results || []).filter((provider: any) => {
                                  const providerState = (provider.Rndrng_Prvdr_State_Abrvtn || '').toUpperCase().trim();
                                  const matches = providerState === userStateCode;
                                  if (!matches && userStateCode) {
                                    console.log(`❌ Provider ${provider.Rndrng_Prvdr_First_Name} ${provider.Rndrng_Prvdr_Last_Org_Name} state mismatch: "${providerState}" !== "${userStateCode}"`);
                                  }
                                  return matches;
                                })
                              : (cmsData.results || []);
                            
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
                    View Full AI Recommendations Response
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
