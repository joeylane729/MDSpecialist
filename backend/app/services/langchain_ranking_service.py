"""
LangChain-powered ranking service for combining NPI providers with Pinecone data.

This service takes a list of NPI providers and Pinecone specialist information,
then uses LangChain to rank the NPI providers based on relevance to the Pinecone data.
"""

import logging
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from ..models.specialist_recommendation import SpecialistRecommendation

logger = logging.getLogger(__name__)

class LangChainRankingService:
    """Service for ranking NPI providers based on Pinecone specialist information."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        # Prompt for ranking NPI providers based on Pinecone data
        self.ranking_prompt = PromptTemplate(
            input_variables=["npi_providers", "pinecone_data", "patient_profile"],
            template="""
            You are a medical specialist ranking expert. Your task is to return doctor names based on the information from Pinecone.
            Specifically, if you see any of the names from the npi_providers list in the Pinecone data (very slight variation in formatting is fine, such as middle initial, capitalization, nicknames, etc.), you should add that doctor's name to the list you return.
            STRICT RULES:
            1. The list you return must only include names from the npi_providers list.
            2. Do not add any names that do not appear in the Pinecone data.
            
            NPI Providers (NPI: Name):
            {npi_providers}
            
            Specialist Information from Pinecone:
            {pinecone_data}
            
            
                        
            Return a JSON object with two fields and do not include any other text in your response:
            1. "providers": An array of the doctor names you identified in ranked order (most relevant first) - format as "FIRST LAST" in all caps
            2. "explanation": An explanation of why you chose each specialist.
            
            Example:
            {{
                "providers": ["ALBERT SMITH", "JANE DOE", "MICHAEL JOHNSON"],
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
        max_providers: int = 1000
    ) -> Dict[str, Any]:
        """
        Rank NPI providers based on Pinecone specialist information.
        
        Args:
            npi_providers: List of NPI provider dictionaries
            pinecone_data: List of specialist information from Pinecone
            patient_profile: Patient profile with symptoms, diagnosis, etc.
            max_providers: Maximum number of providers to rank (default: 1000)
            
        Returns:
            Dictionary with 'ranking' (list of NPI numbers) and 'explanation' (string)
        """
        try:
            logger.info(f"=== SINGLE-STAGE RANKING STARTED ===")
            logger.info(f"Total providers: {len(npi_providers)}")
            logger.info(f"Max providers to rank: {max_providers}")
            logger.info(f"Pinecone records: {len(pinecone_data)}")
            
            # Take only the first max_providers for ranking
            providers_to_rank = npi_providers[:max_providers]
            logger.info(f"Ranking first {len(providers_to_rank)} providers")
            
            pinecone_formatted = self._format_pinecone_data(pinecone_data)
            patient_formatted = self._format_patient_profile(patient_profile)
            npi_formatted = self._format_npi_providers(providers_to_rank)
            
            logger.info(f"Calling LLM for ranking...")
            logger.info(f"=== DEBUG: NPI Providers being sent to LLM ===")
            logger.info(f"Formatted NPI providers: {npi_formatted}")
            logger.info(f"=== DEBUG: Pinecone Data being sent to LLM ===")
            logger.info(f"Formatted Pinecone data: {pinecone_formatted}")
            logger.info(f"=== DEBUG: Patient Profile being sent to LLM ===")
            logger.info(f"Formatted patient profile: {patient_formatted}")
            
            response = await self.ranking_chain.arun(
                npi_providers=npi_formatted,
                pinecone_data=pinecone_formatted,
                patient_profile=patient_formatted
            )
            
            # Debug: Log the raw LLM response
            logger.info(f"Raw LLM ranking response: '{response}'")
            
            ranking_result = self._parse_ranking_response(response, providers_to_rank)
            
            logger.info(f"=== SINGLE-STAGE RANKING COMPLETED ===")
            logger.info(f"Successfully ranked {len(ranking_result['ranking'])} providers")
            logger.info(f"Top 10 ranked NPIs: {ranking_result['ranking'][:10]}")
            logger.info(f"Ranking explanation: {ranking_result['explanation']}")
            return ranking_result
            
        except Exception as e:
            logger.error(f"Error in single-stage ranking: {e}")
            # Fallback: return original order (first max_providers)
            fallback_ranking = [provider.get('npi', '') for provider in npi_providers[:max_providers] if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Ranking failed - showing providers in original order.'
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
        """Format Pinecone data for LLM input - only author and featuring fields."""
        formatted = []
        for i, record in enumerate(pinecone_data, 1):
            author = record.get('author', 'Unknown author')
            featuring = record.get('featuring', 'Unknown specialist')
            formatted.append(f"{i}. Author: {author}, Featuring: {featuring}")
        return "\n".join(formatted)
    
    def _format_patient_profile(self, patient_profile: Dict[str, Any]) -> str:
        """Format patient profile for LLM input."""
        symptoms = patient_profile.get('symptoms', [])
        specialties = patient_profile.get('specialties_needed', [])
        urgency = patient_profile.get('urgency_level', 'medium')
        
        return f"""
        Symptoms: {', '.join(symptoms) if symptoms else 'Not specified'}
        Specialties Needed: {', '.join(specialties) if specialties else 'Not specified'}
        Urgency: {urgency}
        """
    
    def _parse_ranking_response(self, response: str, providers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse LLM response to extract ranked NPI numbers and explanation."""
        try:
            import json
            import re
            
            # Clean the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove ```
            cleaned_response = cleaned_response.strip()
            
            # Try to parse as JSON first
            try:
                result = json.loads(cleaned_response)
                if isinstance(result, dict) and 'providers' in result and 'explanation' in result:
                    # New format with 'providers' field - now contains doctor names
                    doctor_names = result['providers']
                    logger.info(f"Parsed {len(doctor_names)} doctor names from LLM response")
                    
                    # Convert doctor names back to NPI numbers
                    npi_ranking = self._convert_names_to_npis(doctor_names, providers)
                    logger.info(f"Converted to {len(npi_ranking)} NPI numbers")
                    
                    return {
                        'ranking': npi_ranking,
                        'explanation': result['explanation']
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
                    'explanation': 'Ranking completed successfully.'
                }
            
            # If no NPIs found, return original order
            logger.warning("Could not parse ranking response, returning original order")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Could not parse ranking response - showing providers in original order.'
            }
            
        except Exception as e:
            logger.error(f"Error parsing ranking response: {e}")
            fallback_ranking = [provider.get('npi', '') for provider in providers if provider.get('npi')]
            return {
                'ranking': fallback_ranking,
                'explanation': 'Error parsing ranking response - showing providers in original order.'
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