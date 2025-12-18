"""
Pre-authorization Letter Generation Service

This service generates pre-authorization letters for insurance companies
using GPT, incorporating doctor qualifications and patient diagnosis information.
"""

import logging
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

logger = logging.getLogger(__name__)

class PreAuthLetterService:
    """Service for generating pre-authorization letters."""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.3)  # Using gpt-4o for letter generation quality
    
    async def generate_preauth_letter(
        self,
        provider_info: Dict[str, Any],
        patient_diagnosis: str,
        patient_symptoms: Optional[str] = None,
        specificity_relevance: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a pre-authorization letter for insurance approval.
        
        Args:
            provider_info: Dictionary containing provider information including:
                - name: Provider name
                - npi: NPI number
                - specialty: Provider specialty
                - publications: List of publications (from providerContent.pubmed_articles)
                - clinical_volume: Clinical volume data from CMS
                - education: Educational history (medical school, residency, fellowship)
                - years_experience: Years of experience
            patient_diagnosis: Patient's diagnosis
            patient_symptoms: Optional patient symptoms
            specificity_relevance: Optional specificity/relevance data from scoreData
            
        Returns:
            Generated pre-authorization letter as a string
        """
        try:
            # Extract provider information
            provider_name = provider_info.get('name', 'Provider')
            provider_npi = provider_info.get('npi', 'N/A')
            provider_specialty = provider_info.get('specialty', 'Specialist')
            
            # Build publications summary
            publications = provider_info.get('publications', [])
            publications_summary = ""
            if publications and len(publications) > 0:
                pub_count = len(publications)
                publications_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has authored or co-authored {pub_count} peer-reviewed research article(s) in medical journals, demonstrating expertise in the field."
                if pub_count > 0:
                    # Include a few recent/relevant publications
                    recent_pubs = publications[:3]  # Take first 3
                    pub_titles = [pub.get('title', '') for pub in recent_pubs if isinstance(pub, dict)]
                    if pub_titles:
                        publications_summary += f" Recent publications include research on topics relevant to the patient's condition."
            else:
                publications_summary = "The provider maintains active involvement in the medical community."
            
            # Build clinical volume summary
            clinical_volume = provider_info.get('clinical_volume', {})
            clinical_volume_summary = ""
            if clinical_volume:
                tot_srvcs = clinical_volume.get('raw', 0) or clinical_volume.get('tot_srvcs', 0)
                if tot_srvcs and tot_srvcs > 0:
                    clinical_volume_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has performed {int(tot_srvcs):,} relevant procedures according to CMS data, demonstrating substantial clinical experience and expertise in managing cases similar to this patient's condition."
                else:
                    clinical_volume_summary = "The provider has relevant clinical experience in managing similar cases."
            else:
                clinical_volume_summary = "The provider has relevant clinical experience in managing similar cases."
            
            # Build education summary
            education = provider_info.get('education', {})
            education_summary = ""
            education_parts = []
            if education:
                if education.get('medicalSchool'):
                    education_parts.append(f"medical school at {education['medicalSchool']}")
                if education.get('residency'):
                    education_parts.append(f"residency training at {education['residency']}")
                if education.get('fellowship'):
                    education_parts.append(f"fellowship training at {education['fellowship']}")
            
            if education_parts:
                education_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} completed {' and '.join(education_parts)}."
            else:
                education_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has completed comprehensive medical training and board certification in {provider_specialty}."
            
            # Build years of experience summary
            years_experience = provider_info.get('years_experience') or provider_info.get('yearsExperience')
            experience_summary = ""
            if years_experience:
                experience_summary = f"With over {years_experience} years of clinical experience, Dr. {provider_name.split()[0] if provider_name else 'Provider'} brings extensive expertise to the management of this patient's condition."
            else:
                experience_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has extensive clinical experience in {provider_specialty}."
            
            # Build specificity/relevance summary
            specificity_summary = ""
            if specificity_relevance:
                score = specificity_relevance.get('score', 0)
                if score:
                    specificity_summary = f"Based on comprehensive analysis, this provider demonstrates a high level of relevance (score: {score:.2f}/10) to the patient's specific condition, with expertise directly aligned with the required treatment."
                else:
                    specificity_summary = "This provider's expertise is directly relevant to the patient's specific condition and treatment needs."
            else:
                specificity_summary = "This provider's expertise is directly relevant to the patient's specific condition and treatment needs."
            
            # Build the prompt
            prompt = PromptTemplate(
                input_variables=[
                    "provider_name",
                    "provider_npi",
                    "provider_specialty",
                    "publications_summary",
                    "clinical_volume_summary",
                    "education_summary",
                    "experience_summary",
                    "specificity_summary",
                    "patient_diagnosis",
                    "patient_symptoms"
                ],
                template="""
Write a formal pre-authorization letter to an insurance company justifying medical necessity for a specialist consultation.

Provider Information:
- Name: {provider_name}
- NPI: {provider_npi}
- Specialty: {provider_specialty}

Provider Qualifications:
{publications_summary}

{clinical_volume_summary}

{education_summary}

{experience_summary}

{specificity_summary}

Patient Information:
- Diagnosis: {patient_diagnosis}
{f"Symptoms: {patient_symptoms}" if patient_symptoms else ""}

Instructions:
Write a formal business letter (400-600 words) with:
- Subject line for pre-authorization request
- Medical necessity justification
- Provider qualifications and relevance to patient's condition
- Request for approval with contact placeholders
"""
            )
            
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "provider_name": provider_name,
                "provider_npi": provider_npi,
                "provider_specialty": provider_specialty,
                "publications_summary": publications_summary,
                "clinical_volume_summary": clinical_volume_summary,
                "education_summary": education_summary,
                "experience_summary": experience_summary,
                "specificity_summary": specificity_summary,
                "patient_diagnosis": patient_diagnosis,
                "patient_symptoms": patient_symptoms or ""
            })
            
            # Extract the letter content
            letter = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            logger.info(f"✅ Generated pre-authorization letter for provider {provider_npi}")
            return letter
            
        except Exception as e:
            logger.error(f"❌ Error generating pre-authorization letter: {str(e)}")
            raise

