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
            You are a medical specialist ranking expert. Your task is to return doctor names with their corresponding Pinecone links and titles based on the information from Pinecone.
            Specifically, if you see any of the names from the npi_providers list in the Pinecone data (very slight variation in formatting is fine, such as middle initial, capitalization, nicknames, etc.), you should add that doctor's name to the list you return along with the link and title from the Pinecone record.
            STRICT RULES:
            1. The list you return must only include names from the npi_providers list.
            2. Do not add any names that do not appear in the Pinecone data.
            3. For each doctor, include the link and title from the Pinecone record where they appear (either as author or featured).
            
            NPI Providers (NPI: Name):
            {npi_providers}
            
            Specialist Information from Pinecone:
            {pinecone_data}
            
            
                        
            Return a JSON object with the fields below and do not include any other text in your response:
            1. "providers": An array of objects, each containing "name" (doctor name in "FIRST LAST" format, all caps), "link" (the URL from the Pinecone record), and "title" (the title from the Pinecone record), ranked in order of relevance (most relevant first)
            2. "explanation": A 2-sentence explanation of your results.
            
            Example:
            {{
                "providers": [
                    {{"name": "ALBERT SMITH", "link": "https://example.com/video1", "title": "Advanced Treatment for Cluster Headaches"}},
                    {{"name": "JANE DOE", "link": "https://example.com/video2", "title": "Migraine Management Strategies"}},
                    {{"name": "MICHAEL JOHNSON", "link": "https://example.com/video3", "title": "Neurological Assessment Techniques"}}
                ],
                "explanation": "I saw Albert Smith's name in the Pinecone data (he gave a lecture on cluster headaches), so I ranked him first."
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
            logger.info(f"=== SINGLE-STAGE RANKING STARTED ===")
            logger.info(f"🔍 RANKING SERVICE: Total providers received: {len(npi_providers)}")
            logger.info(f"🔍 RANKING SERVICE: Max providers to rank: {max_providers}")
            logger.info(f"🔍 RANKING SERVICE: Pinecone records: {len(pinecone_data)}")
            
            # Take only the first max_providers for ranking
            providers_to_rank = npi_providers[:max_providers]
            logger.info(f"🔍 RANKING SERVICE: Actually ranking {len(providers_to_rank)} providers (limited by max_providers)")
            
            if len(npi_providers) > max_providers:
                logger.warning(f"⚠️ RANKING SERVICE: Provider list truncated from {len(npi_providers)} to {max_providers}")
            else:
                logger.info(f"✅ RANKING SERVICE: Processing all {len(providers_to_rank)} providers (no truncation needed)")
            
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
            
            logger.info(f"=== SINGLE-STAGE RANKING COMPLETED ===")
            logger.info(f"Successfully ranked {len(ranking_result['ranking'])} providers")
            logger.info(f"Top 10 ranked NPIs: {ranking_result['ranking'][:10]}")
            logger.info(f"Ranking explanation: {ranking_result['explanation']}")
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
        """Format Pinecone data for LLM input - author, featuring, and link fields."""
        formatted = []
        for i, record in enumerate(pinecone_data, 1):
            author = record.get('author', 'Unknown author')
            featuring = record.get('featuring', 'Unknown specialist')
            link = record.get('link', 'No link available')
            formatted.append(f"{i}. Author: {author}, Featuring: {featuring}, Link: {link}")
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
                    
                    # Extract doctor names, links, and titles
                    doctor_names = []
                    doctor_links = {}
                    logger.info(f"Processing {len(providers_data)} provider entries from LLM response")
                    for i, provider_entry in enumerate(providers_data):
                        if isinstance(provider_entry, dict) and 'name' in provider_entry:
                            name = provider_entry['name']
                            link = provider_entry.get('link', '')
                            title = provider_entry.get('title', 'Medical Content')
                            doctor_names.append(name)
                            doctor_links[name] = {
                                'link': link,
                                'title': title
                            }
                        elif isinstance(provider_entry, str):
                            # Fallback for old format (just names)
                            doctor_names.append(provider_entry)
                    
                    logger.info(f"Extracted {len(doctor_names)} doctor names with {len(doctor_links)} links")
                    
                    # Convert doctor names back to NPI numbers
                    npi_ranking = self._convert_names_to_npis(doctor_names, providers)
                    logger.info(f"Converted to {len(npi_ranking)} NPI numbers")
                    
                    logger.info(f"Returning {len(doctor_links)} doctor links")
                    return {
                        'ranking': npi_ranking,
                        'explanation': result['explanation'],
                        'provider_links': doctor_links  # Include links for UI display
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
                logger.info(f"Matched '{doctor_name_clean}' to NPI {name_to_npi[doctor_name_clean]}")
            else:
                logger.warning(f"Could not find NPI for doctor name: '{doctor_name_clean}'")
        
        return npi_ranking