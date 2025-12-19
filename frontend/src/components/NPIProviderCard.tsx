import React, { useState } from 'react';
import { MapPin, Phone, Star, Award, Calendar, Building, HelpCircle, Clock, FileText, Shield, ExternalLink, BookOpen, Flag, ChevronDown, ChevronUp, TrendingUp, GraduationCap, Briefcase, Video, Activity, Loader2 } from 'lucide-react';
import { NPIProvider, ProviderContent, VumediContent, PubMedArticle, generatePreAuthLetter } from '../services/api';
import SchedulingModal from './SchedulingModal';
import ProviderReviews from './ProviderReviews';

interface NPIProviderCardProps {
  provider: NPIProvider;
  onClick?: (provider: NPIProvider) => void;
  isHighlighted?: boolean;
  score?: number;
  scoreBreakdown?: string;
  scoreData?: any;
  isCertified?: boolean;
  providerContent?: ProviderContent;
  patientDiagnosis?: string;
  patientSymptoms?: string;
  searchQuery?: string;  // Pre-generated search query from backend (same as PubMed)
}

// Red flag types and their descriptions
type RedFlagType = 'not_certified' | 'excluded' | 'low_clinical_volume' | string;

interface RedFlagInfo {
  type: RedFlagType;
  title: string;
  description: string;
  severity: 'warning' | 'error';
}

const RED_FLAG_DEFINITIONS: Record<RedFlagType, RedFlagInfo> = {
  not_certified: {
    type: 'not_certified',
    title: 'Not Board Certified',
    description: 'This provider is not board certified. Board certification indicates that a physician has met specific education, training, and examination requirements in their specialty.',
    severity: 'warning'
  },
  excluded: {
    type: 'excluded',
    title: 'Excluded Provider',
    description: 'This provider is listed in the federal exclusions database (LEIE - List of Excluded Individuals/Entities). This means they are excluded from participating in federal healthcare programs such as Medicare and Medicaid.',
    severity: 'error'
  },
  low_clinical_volume: {
    type: 'low_clinical_volume',
    title: 'Low Clinical Volume',
    description: 'This provider has low clinical volume (<25%) compared to other providers in the search results. This may indicate limited experience with the specific procedures or treatments relevant to your condition.',
    severity: 'error'
  }
};

export default function NPIProviderCard({ provider, onClick, isHighlighted = false, score, scoreBreakdown, scoreData, isCertified = false, providerContent, patientDiagnosis, patientSymptoms, searchQuery }: NPIProviderCardProps) {
  const [isSchedulingModalOpen, setIsSchedulingModalOpen] = useState(false);
  const [isQuestionsModalOpen, setIsQuestionsModalOpen] = useState(false);
  const [isPreAuthModalOpen, setIsPreAuthModalOpen] = useState(false);
  const [isInsuranceModalOpen, setIsInsuranceModalOpen] = useState(false);
  const [showAllVumedi, setShowAllVumedi] = useState(false);
  const [showAllPubMed, setShowAllPubMed] = useState(false);
  const [isScoreBreakdownModalOpen, setIsScoreBreakdownModalOpen] = useState(false);
  const [redFlagModalOpen, setRedFlagModalOpen] = useState(false);
  const [selectedRedFlagType, setSelectedRedFlagType] = useState<RedFlagType | null>(null);
  const [isGeneratingLetter, setIsGeneratingLetter] = useState(false);
  const [generatedLetter, setGeneratedLetter] = useState<string | null>(null);
  const [letterError, setLetterError] = useState<string | null>(null);
  const [userFirstName, setUserFirstName] = useState('');
  const [userLastName, setUserLastName] = useState('');
  const [insuranceCompanyName, setInsuranceCompanyName] = useState('');
  const [insuranceCompanyEmail, setInsuranceCompanyEmail] = useState('');
  const [promptText, setPromptText] = useState<string | null>(null);
  const [editablePromptText, setEditablePromptText] = useState<string>('');
  
  const MAX_ITEMS_TO_SHOW = 5;

  const yearsExperienceValue = provider.yearsExperience;
  const yearsExperienceLabel = typeof yearsExperienceValue === 'number' && !Number.isNaN(yearsExperienceValue)
    ? `${yearsExperienceValue} year${yearsExperienceValue === 1 ? '' : 's'} of experience`
    : '-- years of experience';


  const openSchedulingModal = () => {
    setIsSchedulingModalOpen(true);
  };

  // Get all active red flags for this provider
  const getActiveRedFlags = (): RedFlagType[] => {
    const flags: RedFlagType[] = [];
    if (!isCertified) {
      flags.push('not_certified');
    }
    if (provider.isExcluded) {
      flags.push('excluded');
    }
    
    // Check for low clinical volume (<25%, including 0)
    if (scoreData?.weighted_breakdown?.breakdown_details?.clinical_volume) {
      const clinicalVolumeBreakdown = scoreData.weighted_breakdown.breakdown_details.clinical_volume;
      const clinicalVolumeRaw = clinicalVolumeBreakdown.raw ?? 0;
      const clinicalVolumeMaxRaw = clinicalVolumeBreakdown.max_raw ?? clinicalVolumeBreakdown.max ?? 1;
      const clinicalVolumePercentage = clinicalVolumeMaxRaw > 0 ? (clinicalVolumeRaw / clinicalVolumeMaxRaw * 100) : 0;
      
      if (clinicalVolumePercentage < 25) {
        flags.push('low_clinical_volume');
      }
    }
    
    return flags;
  };

  const handleRedFlagClick = (flagType: RedFlagType) => {
    setSelectedRedFlagType(flagType);
    setRedFlagModalOpen(true);
  };

  const handleGeneratePreAuthLetter = async (useCustomPrompt: boolean = false) => {
    if (!patientDiagnosis) {
      setLetterError('Patient diagnosis is required to generate the letter.');
      return;
    }

    if (!userFirstName.trim()) {
      setLetterError('Your first name is required.');
      return;
    }

    if (!userLastName.trim()) {
      setLetterError('Your last name is required.');
      return;
    }

    if (!insuranceCompanyName.trim()) {
      setLetterError('Insurance company name is required.');
      return;
    }

    if (!insuranceCompanyEmail.trim()) {
      setLetterError('Insurance company email is required.');
      return;
    }

    setIsGeneratingLetter(true);
    setLetterError(null);
    if (!useCustomPrompt) {
      setGeneratedLetter(null);
    }

    try {
      // Collect provider information
      const providerInfo: any = {
        name: provider.name,
        npi: provider.npi,
        specialty: provider.specialty,
        years_experience: provider.yearsExperience,
        yearsExperience: provider.yearsExperience,
        education: provider.education || {},
      };

      // Add publications from providerContent
      if (providerContent?.pubmed_articles && providerContent.pubmed_articles.length > 0) {
        providerInfo.publications = providerContent.pubmed_articles.map(article => ({
          title: article.title,
          pmid: article.pmid
        }));
      }

      // Add clinical volume from scoreData
      if (scoreData?.weighted_breakdown?.breakdown_details?.clinical_volume) {
        const clinicalVolumeData = scoreData.weighted_breakdown.breakdown_details.clinical_volume;
        providerInfo.clinical_volume = {
          raw: clinicalVolumeData.raw || 0,
          tot_srvcs: clinicalVolumeData.raw || 0,
        };
      }

      // Prepare specificity/relevance data
      const specificityRelevance = scoreData ? {
        score: score || 0,
        ...scoreData
      } : undefined;

      // Generate the letter
      const response = await generatePreAuthLetter({
        provider_info: providerInfo,
        patient_diagnosis: patientDiagnosis,
        patient_symptoms: patientSymptoms || undefined,
        specificity_relevance: specificityRelevance,
        user_first_name: userFirstName.trim(),
        user_last_name: userLastName.trim(),
        insurance_company_name: insuranceCompanyName.trim(),
        insurance_company_email: insuranceCompanyEmail.trim(),
        custom_prompt: useCustomPrompt && editablePromptText ? editablePromptText : undefined
      });

      setGeneratedLetter(response.letter);
      setPromptText(response.prompt_text);
      setEditablePromptText(response.prompt_text);
    } catch (error: any) {
      console.error('Error generating pre-authorization letter:', error);
      setLetterError(error.message || 'Failed to generate pre-authorization letter. Please try again.');
    } finally {
      setIsGeneratingLetter(false);
    }
  };

  const activeRedFlags = getActiveRedFlags();

  // Get score color based on score value (updated for 3x content scoring)
  const getScoreColor = (score: number): string => {
    if (score >= 8) return 'bg-gradient-to-r from-emerald-500 to-green-600';  // Excellent (5+ results)
    if (score >= 5) return 'bg-gradient-to-r from-blue-500 to-indigo-600';      // Good (3+ results)
    if (score >= 3) return 'bg-gradient-to-r from-amber-500 to-orange-500';     // Fair (2+ results)
    if (score >= 1) return 'bg-gradient-to-r from-orange-500 to-red-500';       // Poor (1+ result)
    return 'bg-gradient-to-r from-red-500 to-pink-600';                         // Very poor (0 results)
  };

  // Parse breakdown text into structured sections
  const parseBreakdown = (breakdownText: string) => {
    if (!breakdownText || breakdownText === 'No score data available') {
      return { sections: [], total: null };
    }

    const lines = breakdownText.split('\n').filter(line => line.trim());
    const sections: Array<{ title: string; items: string[]; isSubsection?: boolean }> = [];
    let currentSection: { title: string; items: string[] } | null = null;
    let total: string | null = null;

    for (const line of lines) {
      const trimmed = line.trim();
      
      // Check if it's a total line
      if (trimmed.toLowerCase().startsWith('total:')) {
        total = trimmed;
        continue;
      }

      // Check if it's indented (sub-item)
      const isIndented = /^\s{2,}/.test(line);
      
      // Check if it's a section title (contains colon, not indented, and might not have equals)
      const hasColon = trimmed.includes(':');
      const hasEquals = trimmed.includes('=');
      const isTitle = hasColon && !isIndented && (!hasEquals || trimmed.includes('total:'));
      
      if (isTitle) {
        // Save previous section
        if (currentSection) {
          sections.push(currentSection);
        }
        // Start new section
        currentSection = { title: trimmed, items: [] };
      } else if (currentSection) {
        // Add item to current section (could be indented sub-item)
        currentSection.items.push(trimmed);
      } else if (!isIndented && !trimmed.toLowerCase().startsWith('total')) {
        // Orphan line that's not a total, create a new section for it
        if (trimmed) {
          sections.push({ title: 'Score Components', items: [trimmed] });
        }
      }
    }

    // Add last section
    if (currentSection) {
      sections.push(currentSection);
    }

    return { sections, total };
  };

  return (
    <>
      <div 
        className={`rounded-lg shadow-sm border p-6 hover:shadow-md transition-all ${
          isHighlighted 
            ? 'bg-white border-2 border-yellow-400 shadow-lg' 
            : 'bg-white border border-gray-200'
        }`}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Provider Header */}
            <div className="flex items-center mb-3">
              <h2 className="text-xl font-semibold text-gray-900 mr-3">
                {provider.name}
              </h2>
              {score !== undefined && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsScoreBreakdownModalOpen(true);
                  }}
                  className={`inline-flex items-center justify-center w-12 h-8 ${getScoreColor(score)} text-white text-sm font-bold rounded-lg shadow-sm cursor-pointer hover:shadow-md transition-shadow`}
                  title="Click to view score breakdown"
                >
                  {score.toFixed(2)}
                </button>
              )}
            </div>

            {/* Specialty and Experience */}
            <div className="flex items-center text-gray-600 mb-3 flex-wrap gap-2">
              <span className="font-medium">{provider.specialty}</span>
              <span className="mx-2">•</span>
              <Calendar className="h-4 w-4 mr-1" />
              <span>{yearsExperienceLabel}</span>
              {isCertified && (
                <div className="flex items-center gap-1 ml-2 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                  <Shield className="h-3 w-3" />
                  <span>Board Certified</span>
                </div>
              )}
              {/* Red Flags - Show as clickable icons */}
              {activeRedFlags.map((flagType) => {
                const flagInfo = RED_FLAG_DEFINITIONS[flagType];
                return (
                  <button
                    key={flagType}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRedFlagClick(flagType);
                    }}
                    className="ml-2 p-1.5 bg-red-100 text-red-700 rounded-full hover:bg-red-200 transition-colors cursor-pointer"
                    title={`Click to learn more about this flag`}
                  >
                    <Flag className="h-4 w-4" />
                  </button>
                );
              })}
            </div>

            {/* Location */}
            <div className="flex items-center text-gray-600 mb-3">
              <MapPin className="h-4 w-4 mr-2" />
              <span>{provider.address}, {provider.city}, {provider.state} {provider.zip}</span>
            </div>

            {/* Contact Info */}
            <div className="flex items-center space-x-6 text-gray-600 mb-4">
              {provider.phone && (
                <div className="flex items-center">
                  <Phone className="h-4 w-4 mr-2" />
                  <span>{provider.phone}</span>
                </div>
              )}
            </div>

            {/* Additional Info */}
            <div className="mt-4">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">Education</h3>
              {provider.education && (provider.education.medicalSchool || provider.education.residency || provider.education.fellowship) ? (
                <div className="text-gray-600 space-y-2">
                  {provider.education.medicalSchool && (
                    <div>
                      <span className="text-sm font-medium text-gray-500 uppercase tracking-wide">Medical School</span>
                      <div className="break-words mt-1">{provider.education.medicalSchool}</div>
                    </div>
                  )}
                  {provider.education.residency && (
                    <div>
                      <span className="text-sm font-medium text-gray-500 uppercase tracking-wide">Residency</span>
                      <div className="break-words mt-1">{provider.education.residency}</div>
                    </div>
                  )}
                  {provider.education.fellowship && (
                    <div>
                      <span className="text-sm font-medium text-gray-500 uppercase tracking-wide">Fellowship</span>
                      <div className="break-words mt-1">{provider.education.fellowship}</div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-gray-600 mt-1">--</p>
              )}
            </div>

            {/* Status */}
            <div className="mt-4">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                Accepting Patients
              </span>
            </div>

            {/* Provider Content - Vumedi and PubMed */}
            {providerContent && (
              <div className="mt-4 space-y-3">
                {/* Vumedi Content */}
                {providerContent.vumedi_content && providerContent.vumedi_content.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Educational Videos ({providerContent.vumedi_content.length})
                    </h4>
                    <div className="space-y-2">
                      {(showAllVumedi ? providerContent.vumedi_content : providerContent.vumedi_content.slice(0, MAX_ITEMS_TO_SHOW)).map((content, index) => (
                        <a
                          key={index}
                          href={content.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="block p-2 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
                        >
                          <div className="text-sm font-medium text-purple-800 break-words">
                            {content.title}
                          </div>
                          <div className="text-xs text-purple-600 mt-1">
                            View Video →
                          </div>
                        </a>
                      ))}
                    </div>
                    {providerContent.vumedi_content.length > MAX_ITEMS_TO_SHOW && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowAllVumedi(!showAllVumedi);
                        }}
                        className="mt-2 text-sm text-purple-600 hover:text-purple-800 font-medium flex items-center gap-1"
                      >
                        {showAllVumedi ? (
                          <>
                            <span>Show less</span>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                          </>
                        ) : (
                          <>
                            <span>Show all {providerContent.vumedi_content.length} videos</span>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}

                {/* PubMed Articles */}
                {providerContent.pubmed_articles && providerContent.pubmed_articles.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                      <BookOpen className="w-4 h-4 mr-1" />
                      Research Articles ({providerContent.pubmed_articles.length})
                    </h4>
                    <div className="space-y-2">
                      {(showAllPubMed ? providerContent.pubmed_articles : providerContent.pubmed_articles.slice(0, MAX_ITEMS_TO_SHOW)).map((article, index) => (
                        <a
                          key={index}
                          href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="block p-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                        >
                          <div className="text-sm font-medium text-blue-800 break-words">
                            {article.title}
                          </div>
                          <div className="text-xs text-blue-600 mt-1">
                            PMID: {article.pmid} →
                          </div>
                        </a>
                      ))}
                    </div>
                    {providerContent.pubmed_articles.length > MAX_ITEMS_TO_SHOW && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowAllPubMed(!showAllPubMed);
                        }}
                        className="mt-2 text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                      >
                        {showAllPubMed ? (
                          <>
                            <span>Show less</span>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                            </svg>
                          </>
                        ) : (
                          <>
                            <span>Show all {providerContent.pubmed_articles.length} articles</span>
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Patient Reviews */}
            <ProviderReviews 
              npi={provider.npi} 
              searchQuery={searchQuery}
            />
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col space-y-2 w-48 flex-shrink-0">
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setIsQuestionsModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <HelpCircle className="h-4 w-4" />
              <span>Questions to Ask</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                openSchedulingModal();
              }}
              className="flex items-center justify-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <Clock className="h-4 w-4" />
              <span>Book appointment</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setGeneratedLetter(null);
                setLetterError(null);
                setUserFirstName('');
                setUserLastName('');
                setInsuranceCompanyName('');
                setInsuranceCompanyEmail('');
                setPromptText(null);
                setEditablePromptText('');
                setIsPreAuthModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <FileText className="h-4 w-4" />
              <span>Pre-authorization Letter</span>
            </button>
            
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setIsInsuranceModalOpen(true);
              }}
              className="flex items-center justify-center space-x-2 bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 transition-colors text-xs font-bold whitespace-nowrap"
            >
              <Shield className="h-4 w-4" />
              <span>Insurance approval</span>
            </button>
          </div>
        </div>
      </div>

      {/* Scheduling Modal */}
      <SchedulingModal
        isOpen={isSchedulingModalOpen}
        onClose={() => setIsSchedulingModalOpen(false)}
        provider={provider}
      />

      {/* Questions Modal */}
      {isQuestionsModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Questions to Ask Your Specialist</h3>
              <button
                onClick={() => setIsQuestionsModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-2">About Your Condition</h4>
                <ul className="text-blue-800 space-y-1 text-sm">
                  <li>• What is the exact diagnosis and what does it mean?</li>
                  <li>• What are the potential causes of this condition?</li>
                  <li>• How will this condition progress over time?</li>
                  <li>• What are the long-term implications?</li>
                </ul>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold text-green-900 mb-2">About Treatment Options</h4>
                <ul className="text-green-800 space-y-1 text-sm">
                  <li>• What are all available treatment options?</li>
                  <li>• What are the risks and benefits of each option?</li>
                  <li>• What is the recommended treatment and why?</li>
                  <li>• Are there any alternative or complementary treatments?</li>
                </ul>
              </div>
              <div className="bg-purple-50 p-4 rounded-lg">
                <h4 className="font-semibold text-purple-900 mb-2">About Procedures/Surgery</h4>
                <ul className="text-purple-800 space-y-1 text-sm">
                  <li>• What does the procedure involve?</li>
                  <li>• What are the success rates and potential complications?</li>
                  <li>• What is the recovery process like?</li>
                  <li>• How many of these procedures have you performed?</li>
                </ul>
              </div>
              <div className="bg-orange-50 p-4 rounded-lg">
                <h4 className="font-semibold text-orange-900 mb-2">About Follow-up and Care</h4>
                <ul className="text-orange-800 space-y-1 text-sm">
                  <li>• What follow-up care will I need?</li>
                  <li>• What symptoms should I watch for?</li>
                  <li>• When should I contact you or seek emergency care?</li>
                  <li>• How will we monitor my progress?</li>
                </ul>
              </div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setIsQuestionsModalOpen(false)}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Pre-authorization Modal */}
      {isPreAuthModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Pre-authorization Letter</h3>
              <button
                onClick={() => {
                  setIsPreAuthModalOpen(false);
                  setGeneratedLetter(null);
                  setLetterError(null);
                  setUserFirstName('');
                  setUserLastName('');
                  setInsuranceCompanyName('');
                  setInsuranceCompanyEmail('');
                  setPromptText(null);
                  setEditablePromptText('');
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {!generatedLetter && !isGeneratingLetter && (
              <div className="space-y-4">
                <p className="text-gray-600">
                    We'll generate a professional pre-authorization email for your insurance company. 
                    This email will explain why the specialist consultation is medically necessary and 
                    highlight the provider's qualifications.
                </p>
                <div className="bg-gray-50 p-4 rounded-lg">
                    <h4 className="font-semibold text-gray-900 mb-2">What We'll Include:</h4>
                  <ul className="text-gray-700 space-y-1 text-sm">
                    <li>• Medical necessity justification</li>
                      <li>• Provider qualifications (publications, clinical volume, education, experience)</li>
                      <li>• Relevance of provider expertise to your condition</li>
                    <li>• Expected outcomes and benefits</li>
                  </ul>
                </div>
                  {!patientDiagnosis && (
                    <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                      <p className="text-yellow-800 text-sm">
                        ⚠️ Patient diagnosis information is required to generate the letter.
                      </p>
                  </div>
                  )}
                
                <div className="border-t pt-4 mt-4">
                  <h4 className="font-semibold text-gray-900 mb-2">Your Information</h4>
                  <p className="text-xs text-gray-500 mb-4">Optional - placeholders will be used if left blank</p>
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <label htmlFor="userFirstName" className="block text-sm font-medium text-gray-700 mb-1">
                        Your First Name
                      </label>
                      <input
                        type="text"
                        id="userFirstName"
                        value={userFirstName}
                        onChange={(e) => setUserFirstName(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        placeholder="John"
                      />
                    </div>
                    <div>
                      <label htmlFor="userLastName" className="block text-sm font-medium text-gray-700 mb-1">
                        Your Last Name
                      </label>
                      <input
                        type="text"
                        id="userLastName"
                        value={userLastName}
                        onChange={(e) => setUserLastName(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        placeholder="Doe"
                      />
                    </div>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-semibold text-gray-900 mb-2">Insurance Company Information</h4>
                  <p className="text-xs text-gray-500 mb-4">Optional - placeholders will be used if left blank</p>
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="insuranceCompanyName" className="block text-sm font-medium text-gray-700 mb-1">
                        Insurance Company Name
                      </label>
                      <input
                        type="text"
                        id="insuranceCompanyName"
                        value={insuranceCompanyName}
                        onChange={(e) => setInsuranceCompanyName(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        placeholder="Blue Cross Blue Shield"
                      />
                    </div>
                    <div>
                      <label htmlFor="insuranceCompanyEmail" className="block text-sm font-medium text-gray-700 mb-1">
                        Insurance Company Email
                      </label>
                      <input
                        type="email"
                        id="insuranceCompanyEmail"
                        value={insuranceCompanyEmail}
                        onChange={(e) => setInsuranceCompanyEmail(e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        placeholder="preauth@insurance.com"
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {isGeneratingLetter && (
              <div className="flex flex-col items-center justify-center py-12">
                <Loader2 className="w-12 h-12 text-green-600 animate-spin mb-4" />
                <p className="text-gray-600">Generating your pre-authorization letter...</p>
                <p className="text-gray-500 text-sm mt-2">This may take a few moments</p>
              </div>
            )}

            {letterError && (
              <div className="bg-red-50 border border-red-200 p-4 rounded-lg mb-4">
                <p className="text-red-800 text-sm">{letterError}</p>
              </div>
            )}

            {generatedLetter && (
              <div className="space-y-4">
                <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
                  <p className="text-green-800 text-sm font-semibold mb-2">✅ Letter Generated Successfully</p>
                  <p className="text-green-700 text-sm">You can copy the letter below and customize it as needed.</p>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                  <div className="flex justify-between items-center mb-2">
                    <h4 className="font-semibold text-gray-900">Generated Letter</h4>
              <button
                      onClick={() => {
                        navigator.clipboard.writeText(generatedLetter);
                        alert('Letter copied to clipboard!');
                      }}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                      Copy to Clipboard
              </button>
                  </div>
                  <div className="bg-white p-4 rounded border border-gray-300 max-h-96 overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans">
                      {generatedLetter}
                    </pre>
                  </div>
                </div>

                {promptText && (
                  <details className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                    <summary className="cursor-pointer font-semibold text-gray-900 mb-2">
                      GPT Prompt (Click to view/edit and re-run)
                    </summary>
                    <div className="mt-4">
                      <p className="text-xs text-gray-600 mb-2">The following prompt was sent to GPT to generate the letter:</p>
                      <textarea
                        className="w-full text-xs text-gray-800 bg-white p-3 rounded border border-gray-300 font-mono min-h-[200px] resize-y"
                        value={editablePromptText || promptText || ''}
                        onChange={(e) => setEditablePromptText(e.target.value)}
                        placeholder="Prompt text..."
                      />
                      <div className="mt-3 flex justify-end">
                        <button
                          type="button"
                          onClick={async (e) => {
                            e.preventDefault();
                            await handleGeneratePreAuthLetter(true);
                          }}
                          disabled={isGeneratingLetter || !editablePromptText}
                          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                        >
                          {isGeneratingLetter && <Loader2 className="w-4 h-4 animate-spin" />}
                          Re-run with Edited Prompt
                        </button>
                      </div>
                    </div>
                  </details>
                )}
              </div>
            )}

            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => {
                  setIsPreAuthModalOpen(false);
                  setGeneratedLetter(null);
                  setLetterError(null);
                  setUserFirstName('');
                  setUserLastName('');
                  setInsuranceCompanyName('');
                  setInsuranceCompanyEmail('');
                  setPromptText(null);
                  setEditablePromptText('');
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                disabled={isGeneratingLetter}
              >
                {generatedLetter ? 'Close' : 'Cancel'}
              </button>
              {!generatedLetter && (
                <button
                  onClick={handleGeneratePreAuthLetter}
                  disabled={isGeneratingLetter || !patientDiagnosis}
                  className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
              >
                  {isGeneratingLetter && <Loader2 className="w-4 h-4 animate-spin" />}
                Generate Letter
              </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Insurance Approval Modal */}
      {isInsuranceModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-semibold text-gray-900">Insurance Approval Assistance</h3>
              <button
                onClick={() => setIsInsuranceModalOpen(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-4">
              <p className="text-gray-600">
                We'll help you navigate the insurance approval process and gather the necessary information 
                to ensure your specialist consultation is covered.
              </p>
              
              <div className="bg-blue-50 p-4 rounded-lg">
                <h4 className="font-semibold text-blue-900 mb-3">Insurance Information</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Insurance Company</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="e.g., Blue Cross Blue Shield"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Policy Number</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter your policy number"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Group Number (if applicable)</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Enter group number"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold text-green-900 mb-3">Primary Care Physician Information</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">PCP Name</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                      placeholder="Dr. John Smith"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">PCP Address</label>
                    <textarea
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-green-500 focus:border-green-500"
                      rows={3}
                      placeholder="123 Main St, City, State 12345"
                    />
                  </div>
                </div>
              </div>

              <div className="bg-orange-50 p-4 rounded-lg">
                <h4 className="font-semibold text-orange-900 mb-2">Insurance Card Upload</h4>
                <p className="text-orange-800 text-sm mb-3">
                  Upload a clear photo of the front of your insurance card for verification.
                </p>
                <div className="border-2 border-dashed border-orange-300 rounded-lg p-4 text-center">
                  <svg className="mx-auto h-12 w-12 text-orange-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                    <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <p className="mt-2 text-sm text-orange-600">Click to upload or drag and drop</p>
                  <p className="text-xs text-orange-500">PNG, JPG up to 10MB</p>
                </div>
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => setIsInsuranceModalOpen(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  // TODO: Implement insurance approval assistance
                  alert('Insurance approval assistance will be implemented soon!');
                  setIsInsuranceModalOpen(false);
                }}
                className="bg-orange-600 text-white px-4 py-2 rounded-lg hover:bg-orange-700 transition-colors"
              >
                Submit for Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Score Breakdown Modal */}
      {isScoreBreakdownModalOpen && (scoreBreakdown || scoreData) && (
        <ScoreBreakdownModal
          provider={provider}
          score={score}
          scoreData={scoreData}
          onClose={() => setIsScoreBreakdownModalOpen(false)}
        />
      )}

      {/* Red Flag Modal */}
      {redFlagModalOpen && selectedRedFlagType && RED_FLAG_DEFINITIONS[selectedRedFlagType] && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setRedFlagModalOpen(false)}>
          <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-full ${RED_FLAG_DEFINITIONS[selectedRedFlagType].severity === 'error' ? 'bg-red-100' : 'bg-amber-100'}`}>
                  <Flag className={`h-6 w-6 ${RED_FLAG_DEFINITIONS[selectedRedFlagType].severity === 'error' ? 'text-red-600' : 'text-amber-600'}`} />
                </div>
                <h3 className="text-xl font-semibold text-gray-900">{RED_FLAG_DEFINITIONS[selectedRedFlagType].title}</h3>
              </div>
              <button
                onClick={() => setRedFlagModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className={`p-4 rounded-lg mb-4 ${RED_FLAG_DEFINITIONS[selectedRedFlagType].severity === 'error' ? 'bg-red-50 border border-red-200' : 'bg-amber-50 border border-amber-200'}`}>
              <p className="text-gray-700 leading-relaxed">{RED_FLAG_DEFINITIONS[selectedRedFlagType].description}</p>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => setRedFlagModalOpen(false)}
                className={`px-6 py-2 rounded-lg font-semibold transition-colors ${
                  RED_FLAG_DEFINITIONS[selectedRedFlagType].severity === 'error'
                    ? 'bg-red-600 text-white hover:bg-red-700'
                    : 'bg-amber-600 text-white hover:bg-amber-700'
                }`}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// Score Breakdown Modal Component
interface ScoreBreakdownModalProps {
  provider: NPIProvider;
  score?: number;
  scoreData?: any;
  onClose: () => void;
}

function ScoreBreakdownModal({ provider, score, scoreData, onClose }: ScoreBreakdownModalProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  
  const toggleSection = (sectionKey: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(sectionKey)) {
      newExpanded.delete(sectionKey);
    } else {
      newExpanded.add(sectionKey);
    }
    setExpandedSections(newExpanded);
  };

  const getScoreColor = (score: number): string => {
    if (score >= 80) return 'bg-gradient-to-r from-emerald-500 to-green-600';
    if (score >= 60) return 'bg-gradient-to-r from-blue-500 to-indigo-600';
    if (score >= 40) return 'bg-gradient-to-r from-amber-500 to-orange-500';
    if (score >= 20) return 'bg-gradient-to-r from-orange-500 to-red-500';
    return 'bg-gradient-to-r from-red-500 to-pink-600';
  };

  if (!scoreData?.weighted_breakdown) {
    // Fallback to old text-based breakdown
    return (
      <div 
        className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        onClick={onClose}
      >
        <div 
          className="bg-white rounded-xl shadow-2xl max-w-2xl w-full mx-4 max-h-[85vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 rounded-t-xl">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold mb-1">Score Breakdown</h2>
                <p className="text-blue-100 text-sm">{provider.name}</p>
              </div>
              <button
                onClick={onClose}
                className="text-white hover:text-gray-200 transition-colors p-2 hover:bg-white/20 rounded-lg"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
          <div className="p-6">
            <p className="text-gray-500">Score breakdown data not available</p>
          </div>
        </div>
      </div>
    );
  }

  const { weighted_breakdown } = scoreData;
  const {
    clinical_volume,
    pubmed,
    training,
    experience,
    vumedi
  } = weighted_breakdown;

  const {
    vumedi_count = 0,
    pubmed_count = 0,
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
    med_school_score = 0,
    residency_score = 0,
    certification_points = 0,
    abns_points = 0,
    aoa_points = 0,
    years_experience
  } = scoreData;

  // Recalculate clinical volume percentage from raw values for accuracy
  const clinicalVolumeBreakdown = weighted_breakdown?.breakdown_details?.clinical_volume;
  const clinicalVolumeRaw = clinicalVolumeBreakdown?.raw ?? 0;
  const clinicalVolumeMaxRaw = clinicalVolumeBreakdown?.max_raw ?? clinicalVolumeBreakdown?.max ?? 1;
  const clinicalVolumePercentageRecalc = clinicalVolumeMaxRaw > 0 ? (clinicalVolumeRaw / clinicalVolumeMaxRaw * 100) : 0;
  const clinicalVolumeWeightedPointsRecalc = (clinicalVolumePercentageRecalc / 100) * clinical_volume.weight;

  const sections = [
    {
      key: 'clinical_volume',
      title: 'Clinical Volume',
      icon: Activity,
      color: 'bg-blue-50 border-blue-200',
      iconColor: 'text-blue-600',
      barColor: 'bg-blue-600',
      weight: clinical_volume.weight,
      percentage: clinicalVolumePercentageRecalc, // Use recalculated percentage
      weightedPoints: clinicalVolumeWeightedPointsRecalc, // Use recalculated weighted points
      summary: clinicalVolumeBreakdown ? `✓ ${clinicalVolumePercentageRecalc.toFixed(1)}% of max Tot_Srvcs` : 'Not in CMS results',
      details: (() => {
        const breakdownDetails = weighted_breakdown?.breakdown_details?.clinical_volume;
        if (!breakdownDetails) {
          return <div className="text-sm text-gray-600">This provider is not in the CMS results for the searched CPT codes or has no recorded services for this category.</div>;
        }
        
        const totSrvcs = breakdownDetails?.raw ?? 0;
        const maxTotSrvcs = breakdownDetails?.max_raw ?? breakdownDetails?.max ?? 1; // Support both max_raw and max for backward compatibility
        // Recalculate percentage from raw values to ensure accuracy
        const percentageCalc = maxTotSrvcs > 0 ? (totSrvcs / maxTotSrvcs * 100) : 0;
        const percentageDisplay = percentageCalc.toFixed(1);
        // Recalculate weighted points from the recalculated percentage
        const weightedPointsCalc = (percentageCalc / 100) * clinical_volume.weight;
        
        return (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Status:</span>
              <span className="font-semibold text-green-700">✓ In CMS Results</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Total Services (Tot_Srvcs):</span>
              <span className="font-semibold">{totSrvcs.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Max Total Services (in category):</span>
              <span className="font-semibold">{maxTotSrvcs.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Percentage Calculation:</span>
              <span className="font-semibold">{totSrvcs.toLocaleString()} ÷ {maxTotSrvcs.toLocaleString()} = {percentageDisplay}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Weighted Points:</span>
              <span className="font-semibold">{(percentageCalc / 100).toFixed(2)} × {clinical_volume.weight}% = {weightedPointsCalc.toFixed(2)} points</span>
            </div>
          </div>
        );
      })()
    },
    {
      key: 'pubmed',
      title: 'PubMed Articles',
      icon: FileText,
      color: 'bg-purple-50 border-purple-200',
      iconColor: 'text-purple-600',
      barColor: 'bg-purple-600',
      weight: pubmed.weight,
      percentage: pubmed.percentage,
      weightedPoints: pubmed.weighted_points,
      summary: `${pubmed_count} article${pubmed_count !== 1 ? 's' : ''}`,
      details: (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-gray-600">Total Articles:</span>
              <span className="ml-2 font-semibold">{pubmed_count}</span>
            </div>
            <div>
              <span className="text-gray-600">Weighted Points:</span>
              <span className="ml-2 font-semibold">{pubmed_weighted_points.toFixed(2)}</span>
            </div>
          </div>
          {(pubmed_first_author_count > 0 || pubmed_middle_author_count > 0 || pubmed_last_author_count > 0) && (
            <div className="border-t pt-3">
              <div className="font-semibold text-gray-700 mb-2">Author Positions:</div>
              <div className="space-y-1">
                {pubmed_first_author_count > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">First author:</span>
                    <span>{pubmed_first_author_count} × 2 pts = {pubmed_first_author_count * 2} pts</span>
                  </div>
                )}
                {pubmed_middle_author_count > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Middle author:</span>
                    <span>{pubmed_middle_author_count} × 1 pt = {pubmed_middle_author_count} pts</span>
                  </div>
                )}
                {pubmed_last_author_count > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Last author:</span>
                    <span>{pubmed_last_author_count} × 3 pts = {pubmed_last_author_count * 3} pts</span>
                  </div>
                )}
                <div className="flex justify-between font-semibold pt-2 border-t">
                  <span>Base Points:</span>
                  <span>{pubmed_base_points.toFixed(1)} pts</span>
                </div>
              </div>
            </div>
          )}
          {(pubmed_quartile_q1_count > 0 || pubmed_quartile_q2_count > 0 || pubmed_quartile_q3_count > 0 || pubmed_quartile_q4_count > 0 || pubmed_quartile_no_data_count > 0) && (
            <div className="border-t pt-3">
              <div className="font-semibold text-gray-700 mb-2">Journal Quartiles:</div>
              <div className="space-y-1">
                {pubmed_quartile_q1_count > 0 && <div className="flex justify-between"><span className="text-gray-600">Q1:</span><span>{pubmed_quartile_q1_count} articles (×1.0)</span></div>}
                {pubmed_quartile_q2_count > 0 && <div className="flex justify-between"><span className="text-gray-600">Q2:</span><span>{pubmed_quartile_q2_count} articles (×0.75)</span></div>}
                {pubmed_quartile_q3_count > 0 && <div className="flex justify-between"><span className="text-gray-600">Q3:</span><span>{pubmed_quartile_q3_count} articles (×0.5)</span></div>}
                {pubmed_quartile_q4_count > 0 && <div className="flex justify-between"><span className="text-gray-600">Q4:</span><span>{pubmed_quartile_q4_count} articles (×0.25)</span></div>}
                {pubmed_quartile_no_data_count > 0 && <div className="flex justify-between"><span className="text-gray-600">No quartile:</span><span>{pubmed_quartile_no_data_count} articles (×1.0)</span></div>}
              </div>
            </div>
          )}
          <div className="border-t pt-3">
            <div className="font-semibold text-gray-700 mb-2">Calculation:</div>
            <div className="space-y-1 text-xs text-gray-600 font-mono">
              <div>Raw Score: {pubmed_weighted_points.toFixed(2)} pts</div>
              <div>Percentage: {pubmed.percentage.toFixed(1)}% (relative to max in batch)</div>
              <div>Weighted: {pubmed.percentage.toFixed(1)}% × {pubmed.weight}% = {pubmed.weighted_points.toFixed(2)} points</div>
            </div>
          </div>
        </div>
      )
    },
    {
      key: 'training',
      title: 'Training',
      icon: GraduationCap,
      color: 'bg-indigo-50 border-indigo-200',
      iconColor: 'text-indigo-600',
      barColor: 'bg-indigo-600',
      weight: training.weight,
      percentage: training.percentage,
      weightedPoints: training.weighted_points,
      summary: `Med School + Residency + Certifications`,
      details: (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-gray-600">Medical School:</span>
              <span className="ml-2 font-semibold">{med_school_score} pts</span>
            </div>
            <div>
              <span className="text-gray-600">Residency:</span>
              <span className="ml-2 font-semibold">{residency_score} pts</span>
            </div>
          </div>
          {certification_points > 0 && (
            <div className="border-t pt-3">
              <div className="font-semibold text-gray-700 mb-2">Certifications:</div>
              <div className="space-y-1">
                {abns_points > 0 && <div className="flex justify-between"><span className="text-gray-600">ABNS:</span><span>{abns_points} pts</span></div>}
                {aoa_points > 0 && <div className="flex justify-between"><span className="text-gray-600">AOA:</span><span>{aoa_points} pts</span></div>}
                <div className="flex justify-between font-semibold pt-2 border-t">
                  <span>Total Certification Points:</span>
                  <span>{certification_points} pts</span>
                </div>
              </div>
            </div>
          )}
          <div className="border-t pt-3">
            <div className="font-semibold text-gray-700 mb-2">Calculation:</div>
            <div className="space-y-1 text-xs text-gray-600 font-mono">
              <div>Raw Score: {med_school_score + residency_score + certification_points} pts</div>
              <div>Percentage: {training.percentage.toFixed(1)}% (relative to max in batch)</div>
              <div>Weighted: {training.percentage.toFixed(1)}% × {training.weight}% = {training.weighted_points.toFixed(2)} points</div>
            </div>
          </div>
        </div>
      )
    },
    {
      key: 'experience',
      title: 'Years of Experience',
      icon: Briefcase,
      color: 'bg-green-50 border-green-200',
      iconColor: 'text-green-600',
      barColor: 'bg-green-600',
      weight: experience.weight,
      percentage: experience.percentage,
      weightedPoints: experience.weighted_points,
      summary: years_experience ? `${years_experience} year${years_experience !== 1 ? 's' : ''}` : 'Not available',
      details: (
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Years of Experience:</span>
            <span className="font-semibold">{years_experience || 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Experience Points:</span>
            <span className="font-semibold">{scoreData.experience_points || 0} pts</span>
          </div>
          <div className="border-t pt-3">
            <div className="font-semibold text-gray-700 mb-2">Calculation:</div>
            <div className="space-y-1 text-xs text-gray-600 font-mono">
              <div>Raw Score: {scoreData.experience_points || 0} pts</div>
              <div>Percentage: {experience.percentage.toFixed(1)}% (relative to max in batch)</div>
              <div>Weighted: {experience.percentage.toFixed(1)}% × {experience.weight}% = {experience.weighted_points.toFixed(2)} points</div>
            </div>
          </div>
        </div>
      )
    },
    {
      key: 'vumedi',
      title: 'Medical Lectures (Vumedi)',
      icon: Video,
      color: 'bg-pink-50 border-pink-200',
      iconColor: 'text-pink-600',
      barColor: 'bg-pink-600',
      weight: vumedi.weight,
      percentage: vumedi.percentage,
      weightedPoints: vumedi.weighted_points,
      summary: `${vumedi_count} video${vumedi_count !== 1 ? 's' : ''}`,
      details: (
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Total Videos:</span>
            <span className="font-semibold">{vumedi_count}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Raw Score:</span>
            <span className="font-semibold">{vumedi_count * 4} pts ({vumedi_count} × 4)</span>
          </div>
          <div className="border-t pt-3">
            <div className="font-semibold text-gray-700 mb-2">Calculation:</div>
            <div className="space-y-1 text-xs text-gray-600 font-mono">
              <div>Raw Score: {vumedi_count * 4} pts</div>
              <div>Percentage: {vumedi.percentage.toFixed(1)}% (relative to max in batch)</div>
              <div>Weighted: {vumedi.percentage.toFixed(1)}% × {vumedi.weight}% = {vumedi.weighted_points.toFixed(2)} points</div>
            </div>
          </div>
        </div>
      )
    }
  ];

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 rounded-t-xl z-10">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold mb-1">Score Breakdown</h2>
              <p className="text-blue-100 text-sm">{provider.name}</p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 transition-colors p-2 hover:bg-white/20 rounded-lg"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {score !== undefined && (
            <div className="mt-4">
              <div className={`inline-flex items-center justify-center px-4 py-2 ${getScoreColor(score)} text-white text-lg font-bold rounded-lg shadow-lg`}>
                Total Score: {score.toFixed(2)} / 100
              </div>
            </div>
          )}
        </div>

        {/* Modal Content */}
        <div className="p-6">
          <div className="mb-6">
            <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4 border border-gray-200">
              <h3 className="font-semibold text-gray-900 mb-2">Weight Distribution</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
                <div className="text-center">
                  <div className="font-bold text-blue-600">40%</div>
                  <div className="text-gray-600 text-xs">Clinical Volume</div>
                </div>
                <div className="text-center">
                  <div className="font-bold text-purple-600">40%</div>
                  <div className="text-gray-600 text-xs">PubMed</div>
                </div>
                <div className="text-center">
                  <div className="font-bold text-indigo-600">10%</div>
                  <div className="text-gray-600 text-xs">Training</div>
                </div>
                <div className="text-center">
                  <div className="font-bold text-green-600">6%</div>
                  <div className="text-gray-600 text-xs">Experience</div>
                </div>
                <div className="text-center">
                  <div className="font-bold text-pink-600">4%</div>
                  <div className="text-gray-600 text-xs">Medical Lectures</div>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {sections.map((section) => {
              const Icon = section.icon;
              const isExpanded = expandedSections.has(section.key);
              
              return (
                <div
                  key={section.key}
                  className={`${section.color} border-2 rounded-lg overflow-hidden transition-all`}
                >
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSection(section.key)}
                    className="w-full p-4 flex items-center justify-between hover:bg-opacity-80 transition-colors"
                  >
                    <div className="flex items-center gap-4 flex-1">
                      <div className={`${section.iconColor} bg-white rounded-lg p-2`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 text-left">
                        <div className="flex items-center gap-3">
                          <h3 className="font-bold text-gray-900 text-lg">{section.title}</h3>
                          <span className="text-xs font-semibold text-gray-600 bg-white px-2 py-1 rounded">
                            {section.weight}% weight
                          </span>
                        </div>
                        <div className="mt-2 flex items-center gap-4">
                          <div className="flex items-center gap-2">
                            <span className="text-2xl font-bold text-gray-900">{section.weightedPoints.toFixed(2)}</span>
                            <span className="text-sm text-gray-600">/ {section.weight}</span>
                          </div>
                          <div className="h-2 bg-white rounded-full flex-1 max-w-[200px]">
                            <div
                              className={`h-full ${section.barColor} rounded-full transition-all`}
                              style={{ width: `${Math.min(section.percentage, 100)}%` }}
                            />
                          </div>
                          <span className="text-sm font-semibold text-gray-700">{section.percentage.toFixed(1)}%</span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1">{section.summary}</p>
                      </div>
                    </div>
                    <div className="ml-4">
                      {isExpanded ? (
                        <ChevronUp className="w-5 h-5 text-gray-600" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-gray-600" />
                      )}
                    </div>
                  </button>

                  {/* Expandable Details */}
                  {isExpanded && (
                    <div className="border-t border-gray-300 bg-white p-4">
                      {section.details}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="sticky bottom-0 bg-gray-50 px-6 py-4 rounded-b-xl border-t border-gray-200">
          <button
            onClick={onClose}
            className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )}
