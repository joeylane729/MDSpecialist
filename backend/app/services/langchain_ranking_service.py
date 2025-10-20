"""
LangChain-powered ranking service for combining NPI providers with Pinecone data.

This service takes a list of NPI providers and Pinecone specialist information,
then uses LangChain to rank the NPI providers based on relevance to the Pinecone data.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from ..models.specialist_recommendation import SpecialistRecommendation
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class LangChainRankingService:
    """Service for ranking NPI providers based on Pinecone specialist information."""
    
    def __init__(self, db: Session = None):
        self.llm = ChatOpenAI(model="gpt-5-mini", temperature=0.1, request_timeout=300)
        self.db = db
        
        # Prompt for ranking NPI providers based on Pinecone data
        self.ranking_prompt = PromptTemplate(
            input_variables=["npi_providers", "pinecone_data", "patient_profile"],
            template="""
            You are a medical specialist ranking expert. Your task is to return doctor names with their corresponding Vumedi links/titles and PubMed articles based on the information from Pinecone.
            The Pinecone data contains two types of content:
            1. VUMEDI: Medical education videos with doctor names in "featuring" field, links, and titles
            2. PUBMED: Research articles with author names, PMIDs, and titles
            
            STRICT RULES:
            1. The list you return must only include names from the npi_providers list.
            2. Do not add any names that do not appear in the Pinecone data.
            3. For each doctor, include:
               - Vumedi content: link and title from Vumedi records where they appear
               - PubMed content: PMID and title from PubMed records where they appear as authors
            4. Match names with slight variations (middle initial, capitalization, nicknames, etc.)
            
            NPI Providers (NPI: Name):
            {npi_providers}
            
            Specialist Information from Pinecone:
            {pinecone_data}
            
            Return a JSON object with the fields below and do not include any other text in your response:
            1. "providers": An array of objects, each containing:
               - "name" (doctor name in "FIRST LAST" format, all caps)
               - "vumedi_content": Array of objects with "link" and "title" from Vumedi records
               - "pubmed_articles": Array of objects with "pmid" and "title" from PubMed records
               - Ranked in order of relevance (most relevant first)
            2. "explanation": A 2-sentence explanation of your results.
            
            Example:
            {{
                "providers": [
                    {{
                        "name": "ALBERT SMITH", 
                        "vumedi_content": [
                            {{"link": "https://example.com/video1", "title": "Advanced Treatment for Cluster Headaches"}}
                        ],
                        "pubmed_articles": [
                            {{"pmid": "12345678", "title": "Novel Approaches to Cluster Headache Management"}}
                        ]
                    }},
                    {{
                        "name": "JANE DOE", 
                        "vumedi_content": [
                            {{"link": "https://example.com/video2", "title": "Migraine Management Strategies"}}
                        ],
                        "pubmed_articles": []
                    }}
                ],
                "explanation": "I found Albert Smith in both Vumedi videos and PubMed articles about cluster headaches, so I ranked him first."
            }}
            
           
            """
        )
        
        self.ranking_chain = LLMChain(llm=self.llm, prompt=self.ranking_prompt)
    
    def _get_medical_school_score(self, npi: str) -> int:
        """Get medical school ranking score for an NPI provider."""
        if not self.db:
            logger.warning("No database session available for medical school lookup")
            return 0
            
        try:
            # Query to get the best medical school ranking for this NPI
            query = text("""
                SELECT msr.rank 
                FROM npi_medical_school_mapping_results nmr
                JOIN medical_school_rankings msr ON nmr."Medical_School_ID" = msr.id
                WHERE nmr."NPI" = :npi
                ORDER BY msr.rank ASC
                LIMIT 1
            """)
            
            result = self.db.execute(query, {"npi": npi})
            row = result.fetchone()
            
            if row:
                rank = row[0]
                logger.debug(f"Medical school rank for NPI {npi}: {rank}")
                
                # Convert rank to points: 1-25 = 3 points, 26-50 = 2 points, 51-75 = 1 point
                if rank <= 25:
                    return 3
                elif rank <= 50:
                    return 2
                elif rank <= 75:
                    return 1
                else:
                    return 0
            else:
                logger.debug(f"No medical school data found for NPI {npi}")
                return 0
                
        except Exception as e:
            logger.error(f"Error looking up medical school for NPI {npi}: {e}")
            return 0
    
    async def rank_npi_providers(
        self, 
        npi_providers: List[Dict[str, Any]], 
        pinecone_data: List[Dict[str, Any]], 
        patient_profile: Dict[str, Any],
        max_providers: int = 10000
    ) -> Dict[str, Any]:
        """
        Rank NPI providers based on Pinecone specialist information.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            pinecone_data: List of specialist information from Pinecone
            patient_profile: Patient profile with symptoms, diagnosis, etc.
            max_providers: Maximum number of providers to rank (default: 10000)
            
        Returns:
            Dictionary with 'ranking' (list of NPI numbers) and 'explanation' (string)
        """
        try:
            logger.info(f"🎯 === SINGLE-STAGE RANKING STARTED ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📊 Max providers to rank: {max_providers}")
            logger.info(f"📊 Pinecone records: {len(pinecone_data)}")
            
            # Take only the first max_providers for ranking
            providers_to_rank = npi_providers[:max_providers]
            logger.info(f"🔍 Actually ranking {len(providers_to_rank)} providers (limited by max_providers)")
            
            if len(npi_providers) > max_providers:
                logger.warning(f"⚠️  Provider list truncated from {len(npi_providers)} to {max_providers}")
            else:
                logger.info(f"✅ Processing all {len(providers_to_rank)} providers (no truncation needed)")
            
            # Format data and log sizes
            logger.info("📊 Formatting data for LLM...")
            format_start = time.time()
            
            pinecone_formatted = self._format_pinecone_data(pinecone_data)
            patient_formatted = self._format_patient_profile(patient_profile)
            npi_formatted = self._format_npi_providers(providers_to_rank)
            
            format_end = time.time()
            logger.info(f"📊 Data formatting completed in {format_end - format_start:.2f} seconds")
            
            # Log data sizes
            pinecone_size = len(pinecone_formatted)
            patient_size = len(patient_formatted)
            npi_size = len(npi_formatted)
            total_size = pinecone_size + patient_size + npi_size
            
            logger.info(f"📊 Data sizes:")
            logger.info(f"  - Pinecone data: {pinecone_size:,} characters")
            logger.info(f"  - Patient profile: {patient_size:,} characters")
            logger.info(f"  - NPI providers: {npi_size:,} characters")
            logger.info(f"  - Total prompt size: {total_size:,} characters")
            logger.info(f"  - Estimated tokens: ~{total_size // 4:,} tokens (rough estimate)")
            
            logger.info(f"Calling LLM for ranking...")
            logger.info(f"📊 Sending to LLM: {len(providers_to_rank)} providers, {len(pinecone_data)} Pinecone records")
            
            # Track usage before the call
            start_time = time.time()
            logger.info(f"🚀 Starting GPT ranking call at {start_time}")
            
            # Call LLM without timeout wrapper to see actual performance
            logger.info("🚀 Making LLM call without timeout...")
            llm_start_time = time.time()
            
            response = await self.ranking_chain.arun(
                npi_providers=npi_formatted,
                pinecone_data=pinecone_formatted,
                patient_profile=patient_formatted
            )
            
            llm_end_time = time.time()
            llm_duration = llm_end_time - llm_start_time
            logger.info(f"✅ LLM call completed in {llm_duration:.2f} seconds")
            
            # Log response details
            response_size = len(response) if response else 0
            logger.info(f"📊 LLM Response details:")
            logger.info(f"  - Response size: {response_size:,} characters")
            logger.info(f"  - Response preview: {response[:200] if response else 'None'}...")
            
            # Log completion and attempt to get usage info
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"✅ GPT ranking call completed in {duration:.2f} seconds")
            
            # Try to get usage information from the LLM response
            try:
                # Check if the response has usage information
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    logger.info(f"💰 GPT Usage - Tokens: {usage.total_tokens}, Input: {usage.input_tokens}, Output: {usage.output_tokens}")
                elif hasattr(response, 'usage'):
                    usage = response.usage
                    logger.info(f"💰 GPT Usage - Tokens: {usage.total_tokens}, Input: {usage.prompt_tokens}, Output: {usage.completion_tokens}")
                else:
                    logger.info(f"💰 GPT Usage - No usage metadata available in response")
            except Exception as e:
                logger.warning(f"Could not extract usage information: {e}")
            
            # Also try to get usage from the LLM object itself
            try:
                if hasattr(self.llm, 'get_num_tokens'):
                    input_tokens = self.llm.get_num_tokens(npi_formatted + pinecone_formatted + patient_formatted)
                    logger.info(f"📊 Estimated input tokens: {input_tokens}")
            except Exception as e:
                logger.warning(f"Could not estimate input tokens: {e}")
            
            # Log full GPT response for debugging
            logger.info(f"=== GPT RANKING RESPONSE ===")
            logger.info(f"Response length: {len(response)} characters")
            logger.info(f"Full response: {response}")
            logger.info(f"=== END GPT RESPONSE ===")
            
            # Parse the response
            logger.info("🔍 Parsing LLM response...")
            parse_start = time.time()
            ranking_result = self._parse_ranking_response(response, providers_to_rank)
            parse_end = time.time()
            logger.info(f"🔍 Response parsing completed in {parse_end - parse_start:.2f} seconds")
            
            logger.info(f"✅ === SINGLE-STAGE RANKING COMPLETED ===")
            logger.info(f"✅ Successfully ranked {len(ranking_result['ranking'])} providers")
            logger.info(f"🏆 Top 10 ranked NPIs: {ranking_result['ranking'][:10]}")
            logger.info(f"📝 Ranking explanation: {ranking_result['explanation']}")
            return ranking_result
            
        except Exception as e:
            logger.error(f"❌ Error in single-stage ranking: {str(e)}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            # Fallback: return original order (first max_providers)
            fallback_ranking = [provider.get('npi', '') for provider in npi_providers[:max_providers] if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Ranking failed - showing providers in original order.',
                'provider_links': {}
            }
    
    def _format_npi_providers(self, providers: List[Dict[str, Any]]) -> str:
        """Format NPI providers for LLM input."""
        formatted = []
        for provider in providers:
            npi = provider.get('npi', '')
            name = provider.get('name', '')  # Use the 'name' field from NPI endpoint
            formatted.append(f"{npi}: {name}")
        return "\n".join(formatted)
    
    def _format_pinecone_data(self, pinecone_data: List[Dict[str, Any]]) -> str:
        """Format Pinecone data for LLM input - handles both Vumedi and PubMed data."""
        formatted = []
        vumedi_count = 0
        pubmed_count = 0
        
        for i, record in enumerate(pinecone_data, 1):
            source = record.get('_source', 'unknown')
            
            if source == 'vumedi':
                vumedi_count += 1
                author = record.get('author', 'Unknown author')
                featuring = record.get('featuring', 'Unknown specialist')
                link = record.get('link', 'No link available')
                title = record.get('title', 'No title available')
                formatted.append(f"{i}. [VUMEDI] Author: {author}, Featuring: {featuring}, Link: {link}, Title: {title}")
                
            elif source == 'pubmed':
                pubmed_count += 1
                authors = record.get('authors', 'Unknown authors')
                # Get PMID from _id field (stored by retrieval service)
                pmid = record.get('_id', 'No PMID available')
                title = record.get('title', 'No title available')
                
                # Debug: Log available fields for first few PubMed records
                if pubmed_count <= 3:
                    logger.info(f"🔍 PubMed record fields: {list(record.keys())}")
                    logger.info(f"🔍 PMID value (from '_id' field): {pmid}")
                
                formatted.append(f"{i}. [PUBMED] Authors: {authors}, PMID: {pmid}, Title: {title}")
                
            else:
                # Fallback for records without source tag (assume Vumedi for backward compatibility)
                author = record.get('author', 'Unknown author')
                featuring = record.get('featuring', 'Unknown specialist')
                link = record.get('link', 'No link available')
                title = record.get('title', 'No title available')
                formatted.append(f"{i}. [VUMEDI] Author: {author}, Featuring: {featuring}, Link: {link}, Title: {title}")
        
        logger.info(f"📊 Formatted Pinecone data: {vumedi_count} Vumedi records, {pubmed_count} PubMed records")
        return "\n".join(formatted)
    
    def _format_patient_profile(self, patient_profile: Dict[str, Any]) -> str:
        """Format patient profile for LLM input."""
        symptoms = patient_profile.get('symptoms', [])
        
        return f"""
        Symptoms: {', '.join(symptoms) if symptoms else 'Not specified'}

        """
    
    def _parse_ranking_response(self, response: str, providers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse LLM response to extract ranked NPI numbers and explanation."""
        try:
            import json
            import re
            
            # Clean the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            logger.info(f"DEBUG: Original response: {response[:200]}...")
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove ```
            cleaned_response = cleaned_response.strip()
            logger.info(f"Processing cleaned LLM response")
            
            # Try to parse as JSON first
            try:
                result = json.loads(cleaned_response)
                logger.info(f"Successfully parsed JSON response")
                if isinstance(result, dict) and 'providers' in result and 'explanation' in result:
                    # New format with 'providers' field - now contains doctor names with links
                    providers_data = result['providers']
                    logger.info(f"Parsed {len(providers_data)} provider entries from LLM response")
                    
                    # Extract doctor names, Vumedi content, and PubMed articles
                    doctor_names = []
                    doctor_links = {}
                    logger.info(f"Processing {len(providers_data)} provider entries from LLM response")
                    for i, provider_entry in enumerate(providers_data):
                        if isinstance(provider_entry, dict) and 'name' in provider_entry:
                            name = provider_entry['name']
                            
                            # Extract Vumedi content
                            vumedi_content = provider_entry.get('vumedi_content', [])
                            vumedi_links = []
                            for vumedi_item in vumedi_content:
                                if isinstance(vumedi_item, dict):
                                    vumedi_links.append({
                                        'link': vumedi_item.get('link', ''),
                                        'title': vumedi_item.get('title', 'Medical Content')
                                    })
                            
                            # Extract PubMed articles
                            pubmed_articles = provider_entry.get('pubmed_articles', [])
                            pubmed_links = []
                            for pubmed_item in pubmed_articles:
                                if isinstance(pubmed_item, dict):
                                    pubmed_links.append({
                                        'pmid': pubmed_item.get('pmid', pubmed_item.get('_id', '')),
                                        'title': pubmed_item.get('title', 'Research Article')
                                    })
                            
                            doctor_names.append(name)
                            doctor_links[name] = {
                                'vumedi_content': vumedi_links,
                                'pubmed_articles': pubmed_links
                            }
                            
                            logger.info(f"Doctor {name}: {len(vumedi_links)} Vumedi links, {len(pubmed_links)} PubMed articles")
                            
                        elif isinstance(provider_entry, str):
                            # Fallback for old format (just names)
                            doctor_names.append(provider_entry)
                            doctor_links[provider_entry] = {
                                'vumedi_content': [],
                                'pubmed_articles': []
                            }
                    
                    logger.info(f"Extracted {len(doctor_names)} doctor names with {len(doctor_links)} content entries")
                    
                    # Convert doctor names back to NPI numbers
                    npi_ranking = self._convert_names_to_npis(doctor_names, providers)
                    logger.info(f"Converted to {len(npi_ranking)} NPI numbers")
                    
                    # Count total content for logging
                    total_vumedi = sum(len(links['vumedi_content']) for links in doctor_links.values())
                    total_pubmed = sum(len(links['pubmed_articles']) for links in doctor_links.values())
                    logger.info(f"Returning {len(doctor_links)} doctor content entries: {total_vumedi} Vumedi links, {total_pubmed} PubMed articles")
                    
                    # Calculate scores and re-sort doctors by content count + medical school
                    logger.info("🎯 Calculating content scores and medical school scores...")
                    doctor_scores = {}
                    
                    for doctor_name, content in doctor_links.items():
                        vumedi_count = len(content['vumedi_content'])
                        pubmed_count = len(content['pubmed_articles'])
                        content_score = (vumedi_count + pubmed_count) * 4  # Each result counts as 4 points
                        
                        # Get medical school score for this doctor
                        # Find the NPI for this doctor name
                        doctor_npi = None
                        for provider in providers:
                            if provider.get('name', '').upper() == doctor_name:
                                doctor_npi = provider.get('npi', '')
                                break
                        
                        med_school_score = 0
                        if doctor_npi:
                            med_school_score = self._get_medical_school_score(doctor_npi)
                        
                        total_score = content_score + med_school_score
                        doctor_scores[doctor_name] = {
                            'npi': doctor_npi,
                            'score': total_score,
                            'content_score': content_score,
                            'vumedi_count': vumedi_count,
                            'pubmed_count': pubmed_count,
                            'med_school_score': med_school_score
                        }
                        logger.info(f"📊 {doctor_name}: {vumedi_count} Vumedi + {pubmed_count} PubMed (×4) + {med_school_score} Med School = {total_score} total")
                    
                    # Re-sort the NPI ranking based on content scores
                    if doctor_scores:
                        # Create a mapping from doctor names back to NPIs
                        name_to_npi = {}
                        for provider in providers:
                            provider_name = provider.get('name', '').upper()
                            if provider_name in doctor_scores:
                                name_to_npi[provider_name] = provider.get('npi', '')
                        
                        # Sort doctors by score (highest first)
                        sorted_doctors = sorted(doctor_scores.items(), key=lambda x: x[1]['score'], reverse=True)
                        logger.info(f"🏆 Top 5 doctors by total score (content + medical school):")
                        for i, (name, score_data) in enumerate(sorted_doctors[:5]):
                            logger.info(f"   {i+1}. {name}: {score_data['score']} total ({score_data['content_score']} content + {score_data['med_school_score']} med school)")
                        
                        # Rebuild NPI ranking in score order
                        re_sorted_npis = []
                        for doctor_name, score_data in sorted_doctors:
                            if doctor_name in name_to_npi and name_to_npi[doctor_name]:
                                re_sorted_npis.append(name_to_npi[doctor_name])
                        
                        # Update the ranking with the re-sorted NPIs
                        npi_ranking = re_sorted_npis
                        logger.info(f"✅ Re-sorted {len(npi_ranking)} NPIs by total score (content + medical school)")
                    else:
                        logger.warning("⚠️ No doctor scores calculated, keeping original GPT ranking")
                    
                    return {
                        'ranking': npi_ranking,
                        'explanation': result['explanation'],
                        'provider_links': doctor_links,  # Include both Vumedi and PubMed content for UI display
                        'provider_scores': doctor_scores  # Include scores for UI display
                    }
                else:
                    logger.warning("JSON response missing 'providers' or 'explanation' fields")
            except json.JSONDecodeError:
                pass
            
            # If JSON parsing fails, try to extract NPI numbers using regex
            npi_pattern = r'\b\d{10}\b'  # 10-digit NPI numbers
            found_npis = re.findall(npi_pattern, cleaned_response)
            
            if found_npis:
                return {
                    'ranking': found_npis,
                    'explanation': 'Ranking completed successfully.',
                    'provider_links': {},
                    'provider_scores': {}
                }
            
            # If no NPIs found, return original order
            logger.warning("Could not parse ranking response, returning original order")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Could not parse ranking response - showing providers in original order.',
                'provider_links': {},
                'provider_scores': {}
            }
            
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Error parsing ranking response - showing providers in original order.',
                'provider_links': {},
                'provider_scores': {}
            }
    
    def _convert_names_to_npis(self, doctor_names: List[str], providers: List[Dict[str, Any]]) -> List[str]:
        """Convert doctor names back to NPI numbers."""
        npi_ranking = []
        
        # Create a mapping from names to NPIs
        name_to_npi = {}
        for provider in providers:
            name = provider.get('name', '').strip().upper()
            npi = provider.get('npi', '')
            if name and npi:
                name_to_npi[name] = npi
        
        # Convert each doctor name to NPI
        for doctor_name in doctor_names:
            doctor_name_clean = doctor_name.strip().upper()
            if doctor_name_clean in name_to_npi:
                npi_ranking.append(name_to_npi[doctor_name_clean])
                logger.debug(f"✅ Matched '{doctor_name_clean}' to NPI {name_to_npi[doctor_name_clean]}")
            else:
                logger.warning(f"⚠️  Could not find NPI for doctor name: '{doctor_name_clean}'")
        
        return npi_ranking
    

    async def rank_npi_providers_by_treatment(
        self,
        npi_providers: List[Dict[str, Any]],
        treatment_pinecone_data: Dict[str, Any],
        patient_profile: Dict[str, Any],
        max_providers: int = 10000
    ) -> Dict[str, Any]:
        """
        Rank ALL NPI providers by score (publications + videos), then by GPT relevance within score groups.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            treatment_pinecone_data: Dictionary with treatment-specific Pinecone data
            patient_profile: Patient profile with symptoms, diagnosis, etc.
            max_providers: Maximum number of providers to rank per treatment (default: 10000)
            
        Returns:
            Dictionary with treatment-specific rankings showing ALL providers with scores
        """
        try:
            logger.info(f"🎯 === TREATMENT-SPECIFIC RANKING STARTED (SCORE-BASED) ===")
            logger.info(f"📊 Total providers received: {len(npi_providers)}")
            logger.info(f"📋 Treatments to rank: {len(treatment_pinecone_data)}")
            
            treatment_rankings = {}
            
            # Rank providers for each treatment option
            for treatment_id, treatment_data in treatment_pinecone_data.items():
                treatment_name = treatment_data.get("name", f"Treatment {treatment_id}")
                all_pinecone_data = treatment_data.get("results", [])
                
                # Filter to only verified results for ranking
                pinecone_data = [result for result in all_pinecone_data if result.get("_verified") == True]
                
                logger.info(f"🔍 Ranking providers for treatment: {treatment_name}")
                logger.info(f"📊 Total Pinecone data for {treatment_name}: {len(all_pinecone_data)} records")
                logger.info(f"✅ Using verified results for ranking: {len(pinecone_data)} records")
                
                if not pinecone_data:
                    # No Pinecone data - return all providers with zero scores
                    logger.warning(f"⚠️  No Pinecone data for treatment {treatment_name}, returning all providers with zero scores")
                    ranked_npis = [p.get('npi', '') for p in npi_providers if p.get('npi')]
                    treatment_rankings[treatment_id] = {
                        "name": treatment_name,
                        "ranked_providers": ranked_npis,
                        "explanation": f"No specialist information found for {treatment_name}. Showing all {len(ranked_npis)} providers with zero scores.",
                        "provider_links": {},
                        "provider_scores": {}
                    }
                    continue
                
                # Use GPT to rank providers with Pinecone matches
                ranking_result = await self.rank_npi_providers(
                    npi_providers=npi_providers,
                    pinecone_data=pinecone_data,
                    patient_profile=patient_profile,
                    max_providers=max_providers
                )
                
                # Get the ranked NPIs and scores from GPT (already calculated with new scoring system)
                matched_npis = ranking_result.get("ranking", [])
                provider_links = ranking_result.get("provider_links", {})
                provider_scores = ranking_result.get("provider_scores", {})  # Use scores from rank_npi_providers
                gpt_explanation = ranking_result.get("explanation", "")
                
                # Sort matched doctors by score (descending), then alphabetically
                matched_doctors_with_scores = [
                    (name, scores) for name, scores in provider_scores.items()
                ]
                matched_doctors_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
                
                # Reorder matched NPIs by score
                matched_npis_by_score = [scores['npi'] for _, scores in matched_doctors_with_scores]
                
                # Find providers that were NOT matched by GPT
                matched_npi_set = set(matched_npis_by_score)
                unmatched_npis = [
                    p.get('npi', '') 
                    for p in npi_providers 
                    if p.get('npi') and p.get('npi') not in matched_npi_set
                ]
                
                # Add scores for unmatched doctors (only medical school score since no content)
                for npi in unmatched_npis:
                    doctor_name = next((p.get('name') for p in npi_providers if p.get('npi') == npi), '')
                    if doctor_name and doctor_name not in provider_scores:
                        # Get medical school score even for unmatched doctors
                        med_school_score = self._get_medical_school_score(npi)
                        provider_scores[doctor_name] = {
                            'npi': npi,
                            'score': med_school_score,
                            'content_score': 0,
                            'vumedi_count': 0,
                            'pubmed_count': 0,
                            'med_school_score': med_school_score
                        }
                
                # Sort ALL providers (matched + unmatched) by their total scores
                all_providers_with_scores = [
                    (name, scores) for name, scores in provider_scores.items()
                ]
                all_providers_with_scores.sort(key=lambda x: (-x[1]['score'], x[0]))
                all_ranked_npis = [scores['npi'] for _, scores in all_providers_with_scores]
                
                # Update explanation
                doctors_with_content = len(matched_doctors_with_scores)
                total_vumedi = sum(scores['vumedi_count'] for _, scores in matched_doctors_with_scores)
                total_pubmed = sum(scores['pubmed_count'] for _, scores in matched_doctors_with_scores)
                total_content_score = sum(scores['content_score'] for _, scores in matched_doctors_with_scores)
                total_med_school_score = sum(scores['med_school_score'] for _, scores in matched_doctors_with_scores)
                
                explanation = (
                    f"Ranked {len(all_ranked_npis)} providers by content score (×4) and medical school ranking. "
                    f"{doctors_with_content} providers found with {total_vumedi} Vumedi videos and {total_pubmed} PubMed articles (×4 = {total_content_score} points) plus {total_med_school_score} medical school points related to {treatment_name}. "
                    f"Providers with higher total scores (content + medical school) are ranked higher."
                )
                
                # Store the results for this treatment
                treatment_rankings[treatment_id] = {
                    "name": treatment_name,
                    "ranked_providers": all_ranked_npis,
                    "explanation": explanation,
                    "provider_links": provider_links,
                    "provider_scores": provider_scores
                }
                
                logger.info(f"✅ Completed ranking for {treatment_name}: {doctors_with_content} with content, {len(unmatched_npis)} with zero scores")
            
            logger.info(f"✅ === TREATMENT-SPECIFIC RANKING COMPLETED ===")
            logger.info(f"📊 Total treatments ranked: {len(treatment_rankings)}")
            
            return {
                "treatment_rankings": treatment_rankings,
                "total_treatments": len(treatment_rankings)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in treatment-specific ranking: {str(e)}")
            raise