/**
 * Scoring weights for provider ranking.
 * These values must match the backend constants in RankingService.
 * Total must sum to 100.
 */
export const SCORING_WEIGHTS = {
  CLINICAL_VOLUME: 10.0,  // Clinical Volume weight
  PUBMED: 70.0,            // PubMed Articles weight
  TRAINING: 10.0,          // Training (Med school + Residency + Certification) weight
  EXPERIENCE: 5.0,          // Experience weight
  VUMEDI: 5.0,             // Medical Lectures (Vumedi) weight
} as const;

/**
 * CPT code relevancy threshold (0-100 scale).
 * Codes with relevancy_score >= this value are considered "relevant".
 * Must match backend constant CPT_RELEVANCY_THRESHOLD in medical_analysis_service.py.
 */
export const CPT_RELEVANCY_THRESHOLD = 10;

/**
 * ICD-10 code relevancy threshold (0-100 scale).
 * Codes with relevancy_score >= this value are considered "relevant".
 * Only relevant ICD codes are passed to the CPT step.
 * Must match backend constant ICD10_RELEVANCY_THRESHOLD in medical_analysis_service.py.
 */
export const ICD10_RELEVANCY_THRESHOLD = 50;

// Validate weights sum to 100
const WEIGHT_TOTAL = 
  SCORING_WEIGHTS.CLINICAL_VOLUME +
  SCORING_WEIGHTS.PUBMED +
  SCORING_WEIGHTS.TRAINING +
  SCORING_WEIGHTS.EXPERIENCE +
  SCORING_WEIGHTS.VUMEDI;

if (Math.abs(WEIGHT_TOTAL - 100.0) > 0.01) {
  console.error(
    `Scoring weights must sum to 100, but sum to ${WEIGHT_TOTAL}. ` +
    `Please update constants/scoringWeights.ts`
  );
}

