"""
LangChain-powered ranking service for combining NPI providers with Pinecone data.

This service takes a list of NPI providers and Pinecone specialist information,
then uses LangChain to rank the NPI providers based on relevance to the Pinecone data.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from ..models.specialist_recommendation import SpecialistRecommendation

logger = logging.getLogger(__name__)

class LangChainRankingService:
    """Service for ranking NPI providers based on Pinecone specialist information."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-5-mini", temperature=0.1, request_timeout=300)
        
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
                    
                    return {
                        'ranking': npi_ranking,
                        'explanation': result['explanation'],
                        'provider_links': doctor_links  # Include both Vumedi and PubMed content for UI display
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
                    'provider_links': {}
                }
            
            # If no NPIs found, return original order
            logger.warning("Could not parse ranking response, returning original order")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Could not parse ranking response - showing providers in original order.',
                'provider_links': {}
            }
            
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Error parsing ranking response - showing providers in original order.',
                'provider_links': {}
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
    
    def _calculate_doctor_scores(
        self,
        npi_providers: List[Dict[str, Any]],
        pinecone_data: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate scores for ALL doctors based on Pinecone appearances.
        
        Args:
            npi_providers: List of all NPI provider dictionaries
            pinecone_data: List of Pinecone records (Vumedi + PubMed)
            
        Returns:
            Dict mapping doctor names to their scores and content
        """
        doctor_scores = {}
        
        # Initialize all doctors with zero scores
        for provider in npi_providers:
            doctor_name = provider.get('name', '')
            npi = provider.get('npi', '')
            if doctor_name and npi:
                doctor_scores[doctor_name] = {
                    'npi': npi,
                    'vumedi_count': 0,
                    'pubmed_count': 0,
                    'total_score': 0,
                    'vumedi_content': [],
                    'pubmed_articles': []
                }
        
        # Count appearances in Pinecone data
        for record in pinecone_data:
            source = record.get('_source', 'unknown')
            
            if source == 'vumedi':
                # Check "featuring" field for Vumedi videos
                featuring = record.get('featuring', '')
                for doctor_name in doctor_scores.keys():
                    if self._simple_name_match(doctor_name, featuring):
                        doctor_scores[doctor_name]['vumedi_count'] += 1
                        doctor_scores[doctor_name]['vumedi_content'].append({
                            'link': record.get('link', ''),
                            'title': record.get('title', 'Medical Content')
                        })
                        
            elif source == 'pubmed':
                # Check "authors" field for PubMed articles
                authors = record.get('authors', '')
                for doctor_name in doctor_scores.keys():
                    if self._simple_name_match(doctor_name, authors):
                        doctor_scores[doctor_name]['pubmed_count'] += 1
                        doctor_scores[doctor_name]['pubmed_articles'].append({
                            'pmid': record.get('_id', ''),
                            'title': record.get('title', 'Research Article')
                        })
        
        # Calculate total scores
        for doctor_name in doctor_scores.keys():
            doctor_scores[doctor_name]['total_score'] = (
                doctor_scores[doctor_name]['vumedi_count'] + 
                doctor_scores[doctor_name]['pubmed_count']
            )
        
        return doctor_scores
    
    def _simple_name_match(self, doctor_name: str, record_name: str) -> bool:
        """
        Simple fuzzy name matching - checks if names match with common variations.
        
        Args:
            doctor_name: Doctor's name from NPI (e.g., "JOHN SMITH")
            record_name: Name from Pinecone record (e.g., "John A. Smith" or "Smith, John")
            
        Returns:
            True if names match, False otherwise
        """
        # Normalize both names: uppercase, remove punctuation
        import re
        doctor_clean = re.sub(r'[^\w\s]', '', doctor_name.upper())
        record_clean = re.sub(r'[^\w\s]', '', record_name.upper())
        
        # Split into parts
        doctor_parts = set(doctor_clean.split())
        record_parts = set(record_clean.split())
        
        # Match if first and last name are both present
        # (ignoring middle names/initials for simplicity)
        if len(doctor_parts) >= 2 and len(record_parts) >= 2:
            # Check if at least 2 parts match (first and last name)
            matches = len(doctor_parts.intersection(record_parts))
            return matches >= 2
        
        return False

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
                pinecone_data = treatment_data.get("results", [])
                
                logger.info(f"🔍 Ranking providers for treatment: {treatment_name}")
                logger.info(f"📊 Pinecone data for {treatment_name}: {len(pinecone_data)} records")
                
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
                
                # Calculate scores for ALL doctors
                logger.info(f"🔢 Calculating scores for all {len(npi_providers)} doctors...")
                doctor_scores = self._calculate_doctor_scores(npi_providers, pinecone_data)
                
                # Create provider scores dict for response
                provider_scores = {}
                for doctor_name, score_data in doctor_scores.items():
                    provider_scores[doctor_name] = {
                        'npi': score_data['npi'],
                        'total_score': score_data['total_score'],
                        'vumedi_count': score_data['vumedi_count'],
                        'pubmed_count': score_data['pubmed_count']
                    }
                
                # Sort doctors by score (descending), then alphabetically by name
                sorted_doctors = sorted(
                    doctor_scores.items(),
                    key=lambda x: (-x[1]['total_score'], x[0])
                )
                
                # Extract ranked NPIs
                ranked_npis = [score_data['npi'] for _, score_data in sorted_doctors]
                
                # Create provider links (only for doctors with content)
                provider_links = {}
                for doctor_name, score_data in sorted_doctors:
                    if score_data['total_score'] > 0:
                        provider_links[doctor_name] = {
                            'vumedi_content': score_data['vumedi_content'],
                            'pubmed_articles': score_data['pubmed_articles']
                        }
                
                # Generate explanation
                doctors_with_content = sum(1 for _, data in sorted_doctors if data['total_score'] > 0)
                total_vumedi = sum(data['vumedi_count'] for _, data in sorted_doctors)
                total_pubmed = sum(data['pubmed_count'] for _, data in sorted_doctors)
                
                explanation = (
                    f"Ranked {len(ranked_npis)} providers by publication and video count. "
                    f"{doctors_with_content} providers found with {total_vumedi} Vumedi videos and {total_pubmed} PubMed articles related to {treatment_name}. "
                    f"Providers with more content are ranked higher."
                )
                
                # Store the results for this treatment
                treatment_rankings[treatment_id] = {
                    "name": treatment_name,
                    "ranked_providers": ranked_npis,
                    "explanation": explanation,
                    "provider_links": provider_links,
                    "provider_scores": provider_scores
                }
                
                logger.info(f"✅ Completed ranking for {treatment_name}: {doctors_with_content} with content, {len(ranked_npis) - doctors_with_content} with zero scores")
            
            logger.info(f"✅ === TREATMENT-SPECIFIC RANKING COMPLETED ===")
            logger.info(f"📊 Total treatments ranked: {len(treatment_rankings)}")
            
            return {
                "treatment_rankings": treatment_rankings,
                "total_treatments": len(treatment_rankings)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in treatment-specific ranking: {str(e)}")
            raise