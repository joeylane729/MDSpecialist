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
            
            # Build publications summary
            publications = provider_info.get('publications', [])
            logger.info(f"📚 [PreAuth] Processing publications: {len(publications)} found")
            publications_summary = ""
            if publications and len(publications) > 0:
                pub_count = len(publications)
                logger.info(f"📚 [PreAuth] Building publications summary for {pub_count} articles")
                publications_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has authored or co-authored {pub_count} peer-reviewed research article(s) in medical journals, demonstrating expertise in the field."
                if pub_count > 0:
                    # Include a few recent/relevant publications
                    recent_pubs = publications[:3]  # Take first 3
                    pub_titles = [pub.get('title', '') for pub in recent_pubs if isinstance(pub, dict)]
                    if pub_titles:
                        publications_summary += f" Recent publications include research on topics relevant to the patient's condition."
                        logger.info(f"📚 [PreAuth] Added recent publications note")
            else:
                publications_summary = "The provider maintains active involvement in the medical community."
                logger.info("📚 [PreAuth] No publications found, using default summary")
            
            # Build clinical volume summary
            clinical_volume = provider_info.get('clinical_volume', {})
            logger.info(f"🏥 [PreAuth] Processing clinical volume data: {bool(clinical_volume)}")
            clinical_volume_summary = ""
            if clinical_volume:
                tot_srvcs = clinical_volume.get('raw', 0) or clinical_volume.get('tot_srvcs', 0)
                logger.info(f"🏥 [PreAuth] Total services (Tot_Srvcs): {tot_srvcs}")
                if tot_srvcs and tot_srvcs > 0:
                    clinical_volume_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has performed {int(tot_srvcs):,} relevant procedures according to CMS data, demonstrating substantial clinical experience and expertise in managing cases similar to this patient's condition."
                    logger.info(f"🏥 [PreAuth] Built clinical volume summary with {int(tot_srvcs):,} procedures")
                else:
                    clinical_volume_summary = "The provider has relevant clinical experience in managing similar cases."
                    logger.info("🏥 [PreAuth] No Tot_Srvcs found, using default summary")
            else:
                clinical_volume_summary = "The provider has relevant clinical experience in managing similar cases."
                logger.info("🏥 [PreAuth] No clinical volume data provided, using default summary")
            
            # Build education summary
            education = provider_info.get('education', {})
            logger.info(f"🎓 [PreAuth] Processing education data: {bool(education)}")
            education_summary = ""
            education_parts = []
            if education:
                if education.get('medicalSchool'):
                    education_parts.append(f"medical school at {education['medicalSchool']}")
                    logger.info(f"🎓 [PreAuth] Medical school: {education['medicalSchool']}")
                if education.get('residency'):
                    education_parts.append(f"residency training at {education['residency']}")
                    logger.info(f"🎓 [PreAuth] Residency: {education['residency']}")
                if education.get('fellowship'):
                    education_parts.append(f"fellowship training at {education['fellowship']}")
                    logger.info(f"🎓 [PreAuth] Fellowship: {education['fellowship']}")
            
            if education_parts:
                education_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} completed {' and '.join(education_parts)}."
                logger.info(f"🎓 [PreAuth] Built education summary with {len(education_parts)} components")
            else:
                education_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has completed comprehensive medical training and board certification in {provider_specialty}."
                logger.info("🎓 [PreAuth] No education details found, using default summary")
            
            # Build years of experience summary
            years_experience = provider_info.get('years_experience') or provider_info.get('yearsExperience')
            logger.info(f"⏱️ [PreAuth] Years of experience: {years_experience or 'N/A'}")
            experience_summary = ""
            if years_experience:
                experience_summary = f"With over {years_experience} years of clinical experience, Dr. {provider_name.split()[0] if provider_name else 'Provider'} brings extensive expertise to the management of this patient's condition."
                logger.info(f"⏱️ [PreAuth] Built experience summary with {years_experience} years")
            else:
                experience_summary = f"Dr. {provider_name.split()[0] if provider_name else 'Provider'} has extensive clinical experience in {provider_specialty}."
                logger.info("⏱️ [PreAuth] No years of experience found, using default summary")
            
            # Build specificity/relevance summary
            logger.info(f"🎯 [PreAuth] Processing specificity/relevance data: {bool(specificity_relevance)}")
            specificity_summary = ""
            if specificity_relevance:
                score = specificity_relevance.get('score', 0)
                logger.info(f"🎯 [PreAuth] Specificity score: {score}")
                if score:
                    specificity_summary = f"Based on comprehensive analysis, this provider demonstrates a high level of relevance (score: {score:.2f}/10) to the patient's specific condition, with expertise directly aligned with the required treatment."
                    logger.info(f"🎯 [PreAuth] Built specificity summary with score {score:.2f}")
                else:
                    specificity_summary = "This provider's expertise is directly relevant to the patient's specific condition and treatment needs."
                    logger.info("🎯 [PreAuth] No score found in specificity_relevance, using default summary")
            else:
                specificity_summary = "This provider's expertise is directly relevant to the patient's specific condition and treatment needs."
                logger.info("🎯 [PreAuth] No specificity_relevance data provided, using default summary")
            
            # Build patient symptoms line (handle conditionally outside template)
            patient_symptoms_line = f"- Symptoms: {patient_symptoms}" if patient_symptoms else ""
            
            # Build the prompt
            logger.info("📝 [PreAuth] Building GPT prompt template")
            logger.info(f"👤 [PreAuth] User: {user_first_name} {user_last_name}")
            logger.info(f"🏢 [PreAuth] Insurance: {insurance_company_name} ({insurance_company_email})")
            
            # Prepare prompt variables
            prompt_vars = {
                "provider_name": provider_name,
                "provider_npi": provider_npi,
                "provider_specialty": provider_specialty,
                "publications_summary": publications_summary,
                "clinical_volume_summary": clinical_volume_summary,
                "education_summary": education_summary,
                "experience_summary": experience_summary,
                "specificity_summary": specificity_summary,
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
{publications_summary}

{clinical_volume_summary}

{education_summary}

{experience_summary}

{specificity_summary}

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
- Subject line for pre-authorization request (include patient name: {user_first_name} {user_last_name})
- Professional greeting addressed to {insurance_company_name}
- Medical necessity justification
- Provider qualifications and relevance to patient's condition
- Request for approval
- Professional closing signed by {user_first_name} {user_last_name}

Format as an email body only - no letterhead, addresses, or signature placeholders. Start with the subject line, then the email body. Use the actual names provided instead of placeholders.
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
            
            # Log summary lengths
            logger.info(f"📊 [PreAuth] Summary lengths - Publications: {len(publications_summary)}, Clinical Volume: {len(clinical_volume_summary)}, Education: {len(education_summary)}, Experience: {len(experience_summary)}, Specificity: {len(specificity_summary)}")
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

