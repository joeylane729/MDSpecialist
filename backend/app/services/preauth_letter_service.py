"""
Pre-authorization Letter Generation Service

This service generates pre-authorization letters for insurance companies
using GPT, incorporating doctor qualifications and patient diagnosis information.
"""

import logging
from typing import Dict, Any, Optional, Tuple
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
        specificity_relevance: Optional[Dict[str, Any]] = None,
        user_first_name: str = "",
        user_last_name: str = "",
        insurance_company_name: str = "",
        insurance_company_email: str = "",
        custom_prompt: Optional[str] = None
    ) -> Tuple[str, str]:
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
            user_first_name: User's first name
            user_last_name: User's last name
            insurance_company_name: Insurance company name
            insurance_company_email: Insurance company email address
            
        Returns:
            Generated pre-authorization letter as a string
        """
        try:
            logger.info("🔧 [PreAuth] Starting letter generation process")
            
            # Extract provider information
            provider_name = provider_info.get('name', 'Provider')
            provider_npi = provider_info.get('npi', 'N/A')
            provider_specialty = provider_info.get('specialty', 'Specialist')
            logger.info(f"👤 [PreAuth] Provider: {provider_name} (NPI: {provider_npi}, Specialty: {provider_specialty})")
            
            # Build publications bullet point
            publications = provider_info.get('publications', [])
            logger.info(f"📚 [PreAuth] Processing publications: {len(publications)} found")
            publications_bullet = ""
            if publications and len(publications) > 0:
                pub_count = len(publications)
                logger.info(f"📚 [PreAuth] Building publications bullet for {pub_count} articles")
                publications_bullet = f"- Authored/co-authored {pub_count} peer-reviewed articles on {patient_diagnosis}"
                logger.info(f"📚 [PreAuth] Built publications summary with count and diagnosis")
            
            # Build clinical volume bullet point
            clinical_volume = provider_info.get('clinical_volume', {})
            logger.info(f"🏥 [PreAuth] Processing clinical volume data: {bool(clinical_volume)}")
            clinical_volume_bullet = ""
            if clinical_volume:
                tot_srvcs = clinical_volume.get('raw', 0) or clinical_volume.get('tot_srvcs', 0)
                logger.info(f"🏥 [PreAuth] Total services (Tot_Srvcs): {tot_srvcs}")
                if tot_srvcs and tot_srvcs > 0:
                    clinical_volume_bullet = f"- Performed {int(tot_srvcs):,} relevant procedures (CMS data)"
                    logger.info(f"🏥 [PreAuth] Built clinical volume bullet with {int(tot_srvcs):,} procedures")
            
            # Build education bullet points
            education = provider_info.get('education', {})
            logger.info(f"🎓 [PreAuth] Processing education data: {bool(education)}")
            education_bullets = []
            if education:
                if education.get('medicalSchool'):
                    education_bullets.append(f"- Medical school: {education['medicalSchool']}")
                    logger.info(f"🎓 [PreAuth] Medical school: {education['medicalSchool']}")
                if education.get('residency'):
                    education_bullets.append(f"- Residency: {education['residency']}")
                    logger.info(f"🎓 [PreAuth] Residency: {education['residency']}")
                if education.get('fellowship'):
                    education_bullets.append(f"- Fellowship: {education['fellowship']}")
                    logger.info(f"🎓 [PreAuth] Fellowship: {education['fellowship']}")
            
            education_summary = '\n'.join(education_bullets) if education_bullets else ""
            if education_bullets:
                logger.info(f"🎓 [PreAuth] Built {len(education_bullets)} education bullets")
            else:
                logger.info("🎓 [PreAuth] No education details found")
            
            # Build years of experience bullet point
            years_experience = provider_info.get('years_experience') or provider_info.get('yearsExperience')
            logger.info(f"⏱️ [PreAuth] Years of experience: {years_experience or 'N/A'}")
            experience_bullet = ""
            if years_experience:
                experience_bullet = f"- {years_experience} years of clinical experience"
                logger.info(f"⏱️ [PreAuth] Built experience bullet with {years_experience} years")
            
            # Log specificity/relevance data (not included in letter)
            logger.info(f"🎯 [PreAuth] Processing specificity/relevance data: {bool(specificity_relevance)}")
            if specificity_relevance:
                score = specificity_relevance.get('score', 0)
                logger.info(f"🎯 [PreAuth] Specificity score: {score} (not included in letter)")
            
            # Build patient symptoms line (handle conditionally outside template)
            patient_symptoms_line = f"- Symptoms: {patient_symptoms}" if patient_symptoms else ""
            
            # Assemble all provider qualification bullets
            provider_qualifications_bullets = []
            if publications_bullet:
                provider_qualifications_bullets.append(publications_bullet)
            if clinical_volume_bullet:
                provider_qualifications_bullets.append(clinical_volume_bullet)
            if education_summary:  # This is already joined bullets
                provider_qualifications_bullets.append(education_summary)
            if experience_bullet:
                provider_qualifications_bullets.append(experience_bullet)
            
            provider_qualifications = '\n'.join(provider_qualifications_bullets)
            logger.info(f"📋 [PreAuth] Assembled {len(provider_qualifications_bullets)} qualification bullets")
            
            # Use placeholders for optional fields if not provided
            user_first_name = user_first_name.strip() if user_first_name else "[Patient First Name]"
            user_last_name = user_last_name.strip() if user_last_name else "[Patient Last Name]"
            insurance_company_name = insurance_company_name.strip() if insurance_company_name else "[Insurance Company]"
            insurance_company_email = insurance_company_email.strip() if insurance_company_email else "[insurance@company.com]"
            
            # Build the prompt
            logger.info("📝 [PreAuth] Building GPT prompt template")
            logger.info(f"👤 [PreAuth] User: {user_first_name} {user_last_name}")
            logger.info(f"🏢 [PreAuth] Insurance: {insurance_company_name} ({insurance_company_email})")
            
            # Prepare prompt variables
            prompt_vars = {
                "provider_name": provider_name,
                "provider_npi": provider_npi,
                "provider_specialty": provider_specialty,
                "provider_qualifications": provider_qualifications,
                "patient_diagnosis": patient_diagnosis,
                "patient_symptoms_line": patient_symptoms_line,
                "user_first_name": user_first_name,
                "user_last_name": user_last_name,
                "insurance_company_name": insurance_company_name,
                "insurance_company_email": insurance_company_email
            }
            
            # Default template
            default_template = """
Write a professional pre-authorization email to an insurance company justifying medical necessity for a specialist consultation.

Provider Information:
- Name: {provider_name}
- NPI: {provider_npi}
- Specialty: {provider_specialty}

Provider Qualifications:
{provider_qualifications}

Patient Information:
- Diagnosis: {patient_diagnosis}
{patient_symptoms_line}

Sender Information:
- Name: {user_first_name} {user_last_name}

Recipient Information:
- Insurance Company: {insurance_company_name}
- Email: {insurance_company_email}

Instructions:
Write a professional email (400-600 words) with:
- Subject line for pre-authorization request
- Professional greeting addressed to insurance company
- Brief introduction stating the purpose
- Medical necessity justification for the patient's diagnosis
- Incorporate the provider's qualifications naturally into the letter to demonstrate expertise and suitability for treating this condition
- Request for pre-authorization approval
- Professional closing signed by the patient

"""
            
            # Use custom prompt if provided, otherwise use default
            if custom_prompt:
                logger.info("📝 [PreAuth] Using custom prompt provided by user")
                try:
                    # Try to format the custom prompt with variables
                    rendered_prompt = custom_prompt.format(**prompt_vars)
                except KeyError as e:
                    logger.warning(f"⚠️ [PreAuth] Custom prompt missing variable {e}, using as-is")
                    rendered_prompt = custom_prompt
                template_text = custom_prompt
            else:
                template_text = default_template
                rendered_prompt = default_template.format(**prompt_vars)
            
            # Create PromptTemplate
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
                    "patient_symptoms_line",
                    "user_first_name",
                    "user_last_name",
                    "insurance_company_name",
                    "insurance_company_email"
                ],
                template=template_text
            )
            
            # Log qualifications length
            logger.info(f"📊 [PreAuth] Provider qualifications length: {len(provider_qualifications)} characters")
            total_prompt_length = sum(len(str(v)) for v in prompt_vars.values())
            logger.info(f"📊 [PreAuth] Total prompt length: ~{total_prompt_length} characters")
            
            chain = prompt | self.llm
            
            logger.info("🤖 [PreAuth] Calling GPT-4o API to generate letter...")
            response = await chain.ainvoke(prompt_vars)
            logger.info("✅ [PreAuth] GPT API call completed")
            
            # Extract the letter content
            letter = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            letter_length = len(letter)
            logger.info(f"📄 [PreAuth] Generated letter length: {letter_length} characters")
            
            if letter_length < 100:
                logger.warning(f"⚠️ [PreAuth] Generated letter is unusually short ({letter_length} chars)")
            elif letter_length > 5000:
                logger.warning(f"⚠️ [PreAuth] Generated letter is unusually long ({letter_length} chars)")
            
            logger.info(f"✅ [PreAuth] Successfully generated pre-authorization letter for provider {provider_npi}")
            return letter, rendered_prompt
            
        except Exception as e:
            logger.error(f"❌ [PreAuth] Error generating pre-authorization letter: {str(e)}")
            logger.error(f"❌ [PreAuth] Error type: {type(e).__name__}")
            import traceback
            logger.error(f"❌ [PreAuth] Traceback: {traceback.format_exc()}")
            logger.error(f"❌ [PreAuth] Provider NPI: {provider_info.get('npi', 'N/A')}")
            logger.error(f"❌ [PreAuth] Patient diagnosis: {patient_diagnosis}")
            raise

