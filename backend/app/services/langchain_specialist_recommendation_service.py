"""
LangChain Specialist Recommendation Service
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.pinecone_service import PineconeService
from ..services.langchain_retrieval_strategies import LangChainRetrievalStrategies
from ..services.medical_analysis_service import MedicalAnalysisService
from ..services.langchain_ranking_service import LangChainRankingService

from ..models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

logger = logging.getLogger(__name__)

class LangChainSpecialistRecommendationService:
    """LangChain-powered specialist recommendation service."""
    
    def __init__(self, db=None):
        self._pinecone_service = None
        self._retrieval_strategies = None
        self._db = db  # Store db session for retrieval strategies
        self.medical_analysis = MedicalAnalysisService(db)
        self.ranking_service = LangChainRankingService(db)

        logger.info("LangChainSpecialistRecommendationService initialized successfully")
    
    @property
    def pinecone_service(self):
        """Lazy initialization of PineconeService to avoid startup failures."""
        if self._pinecone_service is None:
            self._pinecone_service = PineconeService()
        return self._pinecone_service
    
    @property
    def retrieval_strategies(self):
        """Lazy initialization of LangChainRetrievalStrategies."""
        if self._retrieval_strategies is None:
            # Pass database session to retrieval strategies for Postgres queries (no Pinecone needed)
            self._retrieval_strategies = LangChainRetrievalStrategies(pinecone_service=None, db=self._db)
        return self._retrieval_strategies
    
    def set_db(self, db):
        """Set database session for services that need it."""
        self._db = db
        self.medical_analysis.set_db(db)
        # Reset retrieval strategies to use new db session
        self._retrieval_strategies = None
    
    async def get_specialist_recommendations(
        self,
        patient_input: str,
        state: Optional[str] = None,
        cpt_codes: Optional[List[Dict[str, str]]] = None
    ) -> RecommendationResponse:
        """Get specialist recommendations using LangChain.
        
        Args:
            patient_input: Patient input string
            state: Optional state filter for CMS API
            cpt_codes: Optional pre-generated CPT codes to reuse (avoids duplicate GPT calls)
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Comprehensive medical analysis and patient processing
            logger.info("🔍 Step 1: Performing comprehensive medical analysis with LangChain...")
            medical_analysis_results = await self.medical_analysis.comprehensive_analysis(patient_input)
            
            # Add provided CPT codes to medical analysis results if available
            if cpt_codes and len(cpt_codes) > 0:
                medical_analysis_results["cpt_codes"] = cpt_codes
                logger.info(f"✅ Added {len(cpt_codes)} provided CPT codes to medical analysis results")
            
            # Step 1.5: Query CMS API with CPT codes (use provided codes or none)
            logger.info("🔍 Step 1.5: Querying CMS API with CPT codes...")
            if state:
                logger.info(f"🔍 Step 1.5: State filter will be applied: {state}")
            cms_results = {}
            if cpt_codes and len(cpt_codes) > 0:
                logger.info(f"♻️  Using provided CPT codes ({len(cpt_codes)} codes) for CMS API query")
                cms_results = await self.medical_analysis.query_cms_api(
                    cpt_codes,
                    state=state
                )
                logger.info(f"✅ CMS API query complete: {cms_results.get('total_results', 0)} results found")
            else:
                logger.warning("⚠️  No CPT codes provided for CMS API query")
                cms_results = {
                    "url": None,
                    "results": [],
                    "total_results": 0,
                    "error": "No CPT codes provided"
                }
            
            # Step 2: LLM-powered retrieval of specialist information
            logger.info("🔍 Step 2: Retrieving specialist information with LangChain...")
            logger.debug(f"🔍 Retrieval strategies type: {type(self.retrieval_strategies)}")
            logger.debug(f"🔍 Medical analysis results type: {type(medical_analysis_results)}")
            logger.debug(f"🔍 Medical analysis results keys: {list(medical_analysis_results.keys()) if isinstance(medical_analysis_results, dict) else 'Not a dict'}")
            
            retrieval_result = await self.retrieval_strategies.retrieve_specialist_information(
                medical_analysis_results=medical_analysis_results,
                top_k=200  # Use same value as NPI ranking
            )
            
            # Extract treatment results and search query from the retrieval result
            treatment_specialist_information = retrieval_result.get("treatment_results", {})
            search_query = retrieval_result.get("search_query", "")
            
            # Debug logging to see what we actually got
            logger.debug(f"🔍 Treatment specialist information type: {type(treatment_specialist_information)}")
            logger.debug(f"🔍 Treatment specialist information keys: {list(treatment_specialist_information.keys()) if isinstance(treatment_specialist_information, dict) else 'Not a dict'}")
            logger.debug(f"🔍 Search query: {search_query[:100] if search_query else 'None'}...")
            
            # Step 3: Convert treatment-specific specialist information to recommendations
            logger.info("🔍 Step 3: Converting treatment-specific specialist information to recommendations...")
            recommendations = []
            
            # Ensure treatment_specialist_information is a dict with treatment groups
            if not isinstance(treatment_specialist_information, dict):
                logger.error(f"❌ ERROR: treatment_specialist_information is not a dict, it's {type(treatment_specialist_information)}")
                raise ValueError(f"treatment_specialist_information must be a dict, got {type(treatment_specialist_information)}")
            
            # Convert each treatment's specialist information to recommendations
            for treatment_id, treatment_data in treatment_specialist_information.items():
                treatment_name = treatment_data.get("name", f"Treatment {treatment_id}")
                specialist_information = treatment_data.get("results", [])
                
                logger.info(f"📋 Processing {len(specialist_information)} specialists for treatment: {treatment_name}")
                
                # Convert specialist information to recommendations for this treatment
                for i, info in enumerate(specialist_information):
                    # Extract specialist name from featuring field
                    featuring = info.get('featuring', '')
                    specialist_name = featuring.split(',')[0].strip() if featuring else f"Specialist {i+1}"
                    
                    # Calculate scores that stay positive (0.9 down to 0.1)
                    max_score = 0.9
                    min_score = 0.1
                    total_items = len(specialist_information)
                    if total_items > 1:
                        score = max_score - (i * (max_score - min_score) / (total_items - 1))
                    else:
                        score = max_score
                    
                    recommendation = SpecialistRecommendation(
                        specialist_id=info.get('id', info.get('_id', f"specialist_{i}")),
                        name=specialist_name,
                        specialty=info.get('specialty', 'Medical Specialist'),
                        relevance_score=score,
                        confidence_score=score,
                        reasoning=f"Found in medical content for {treatment_name}: {info.get('title', 'Medical video')}",
                        metadata={
                            **info,
                            "treatment_id": treatment_id,
                            "treatment_name": treatment_name
                        }
                    )
                    recommendations.append(recommendation)
            
            # Step 4: Generate response
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Calculate total candidates across all treatments
            total_candidates = sum(len(treatment_data.get("results", [])) for treatment_data in treatment_specialist_information.values())
            
            response = RecommendationResponse(
                patient_profile=medical_analysis_results,
                recommendations=recommendations,
                total_candidates_found=total_candidates,
                processing_time_ms=int(processing_time),
                retrieval_strategies_used=["langchain_vector_search"],
                timestamp=datetime.now(),
                shared_specialist_information=treatment_specialist_information,
                search_query=search_query,
                cms_data=cms_results  # Add CMS API results to response
            )
            
            # Debug logging for treatment options
            logger.debug(f"🔍 Response patient_profile keys: {list(medical_analysis_results.keys())}")
            if "treatment_options" in medical_analysis_results:
                logger.info(f"📋 Response includes {len(medical_analysis_results['treatment_options'])} treatment options")
                for i, option in enumerate(medical_analysis_results['treatment_options']):
                    logger.info(f"   {i+1}. {option.get('name', 'Unnamed')}")
            else:
                logger.warning("⚠️  No treatment_options in response patient_profile")
            
            logger.info(f"✅ Generated {len(recommendations)} recommendations in {processing_time:.2f}ms using LangChain")
            return response
            
        except Exception as e:
            logger.error(f"Error generating LangChain recommendations: {str(e)}")
            raise
    
    async def rank_npi_providers_with_pinecone(
        self,
        npi_providers: List[Dict[str, Any]],
        patient_input: str,
        shared_specialist_information: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Rank NPI providers based on Pinecone specialist information.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            patient_input: Patient description for medical analysis
            shared_specialist_information: Optional pre-fetched specialist information to ensure consistency
            
        Returns:
            List of NPI numbers in ranked order (most relevant first)
        """
        try:
            logger.info(f"🎯 Starting NPI ranking with {len(npi_providers)} providers")
            
            # Step 1: Get medical analysis
            logger.info("🔍 Step 1: Performing medical analysis for NPI ranking...")
            # Note: For NPI ranking, we could also accept pre-generated CPT codes, but typically
            # this is called separately so we generate fresh CPT codes here
            medical_analysis_results = await self.medical_analysis.comprehensive_analysis(patient_input)
            
            # Step 2: Use shared Pinecone specialist information (required)
            if not shared_specialist_information:
                raise ValueError("shared_specialist_information is required for NPI ranking. No fallback Pinecone calls allowed.")
            
            logger.info(f"🔍 Step 2: Using shared specialist records")
            logger.info(f"📋 Treatment groups: {list(shared_specialist_information.keys()) if isinstance(shared_specialist_information, dict) else 'Not grouped'}")
            
            # Step 3: Use treatment-specific ranking service to rank NPI providers
            # Note: CMS results are not available in this context (called from NPI ranking endpoint)
            # Clinical volume bonus will only be applied when ranking from specialist recommendations endpoint
            top_cms_npis = None
            logger.info("🔍 Step 3: Ranking NPI providers based on treatment-specific Pinecone data...")
            ranking_result = await self.ranking_service.rank_npi_providers_by_treatment(
                npi_providers=npi_providers,
                treatment_pinecone_data=shared_specialist_information,
                patient_profile=medical_analysis_results,
                top_cms_npis=top_cms_npis
            )
            
            treatment_rankings = ranking_result['treatment_rankings']
            total_treatments = ranking_result['total_treatments']
            
            logger.info(f"✅ Successfully ranked NPI providers for {total_treatments} treatments")
            for treatment_id, treatment_data in treatment_rankings.items():
                logger.info(f"   📋 {treatment_data['name']}: {len(treatment_data['ranked_providers'])} providers")
            
            return {
                'treatment_rankings': treatment_rankings,
                'total_treatments': total_treatments
            }
            
        except Exception as e:
            logger.error(f"Error ranking NPI providers: {str(e)}")
            raise
    

