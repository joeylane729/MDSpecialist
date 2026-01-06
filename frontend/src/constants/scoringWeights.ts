/**
 * Scoring weights for provider ranking.
 * These values must match the backend constants in RankingService.
 * Total must sum to 100.
 */
export const SCORING_WEIGHTS = {
  CLINICAL_VOLUME: 40.5,  // Clinical Volume weight
  PUBMED: 40.5,            // PubMed Articles weight
  TRAINING: 10.0,          // Training (Med school + Residency + Certification) weight
  EXPERIENCE: 6.0,          // Experience weight
  VUMEDI: 3.0,             // Medical Lectures (Vumedi) weight
} as const;

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

