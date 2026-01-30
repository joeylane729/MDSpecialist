"""
Medical Analysis Endpoint

This endpoint provides medical analysis including diagnosis prediction, ICD-10 coding,
and treatment options without specialist retrieval.
"""

from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...services.medical_analysis_service import MedicalAnalysisService, parse_search_query
from ..utils.patient_input_processor import extract_pdf_content
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/medical-analysis")
async def get_medical_analysis(
    diagnosis: str = Form(...),
    anatomical_location: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),  # Optional: "openai" or "gemini"
    files: List[UploadFile] = File([]),
    custom_diagnoses_prompt: Optional[str] = Form(None),  # Optional custom prompt for diagnosis/treatment generation
    custom_search_query_prompt: Optional[str] = Form(None),  # Optional custom prompt for search query generation
    custom_icd10_prompt: Optional[str] = Form(None),  # Optional custom prompt for ICD-10 code generation
    db: Session = Depends(get_db)
):
    """
    Get medical analysis including diagnosis prediction, ICD-10 coding, and treatment options.
    
    This endpoint provides comprehensive medical analysis without specialist retrieval.
    """
    try:
        # Extract PDF content from uploaded files
        pdf_content = await extract_pdf_content(files)
        
        # Initialize service and perform analysis
        medical_analysis_service = MedicalAnalysisService(db, llm_provider=llm_provider)
        analysis_results = await medical_analysis_service.comprehensive_analysis(
            diagnosis=diagnosis,
            anatomical_location=anatomical_location or "",
            medical_history="",
            medications="",
            surgical_history="",
            pdf_content=pdf_content,
            custom_diagnoses_prompt=custom_diagnoses_prompt,
            custom_search_query_prompt=custom_search_query_prompt,
            custom_icd10_prompt=custom_icd10_prompt
        )
        
        # Add the provider to the response so frontend knows which was used
        analysis_results["llm_provider"] = llm_provider or "openai"
        
        # Wrap response in expected structure for frontend
        return {
            "status": "success",
            "patient_profile": analysis_results,
            "message": "Medical analysis completed successfully"
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        logger.error(f"Error in medical analysis endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Medical analysis failed: {str(e)}"
        )


@router.post("/medical-analysis/search-query")
async def generate_search_query(
    user_diagnosis: str = Form(...),
    anatomical_location: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),  # Optional: "openai" or "gemini"
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    db: Session = Depends(get_db)
):
    """
    Generate search query based on user diagnosis and anatomical location.

    This endpoint is called separately after the initial medical analysis to regenerate the search query.
    """
    try:
        medical_analysis_service = MedicalAnalysisService(db, llm_provider=llm_provider)
        search_query, search_query_prompt_text = await medical_analysis_service.generate_search_query(
            user_diagnosis=user_diagnosis,
            anatomical_location=anatomical_location or "",
            custom_prompt=custom_prompt
        )
        
        return {
            "search_query": search_query,
            "search_query_prompt_text": search_query_prompt_text,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating search query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating search query: {str(e)}"
        )


@router.post("/medical-analysis/icd10-code")
async def regenerate_icd10_code(
    diagnosis: str = Form(...),
    anatomical_location: Optional[str] = Form(None),
    pdf_content: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),  # Optional: "openai" or "gemini"
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    db: Session = Depends(get_db)
):
    """
    Regenerate ICD-10 code based on diagnosis and anatomical location.
    
    This endpoint is called separately to regenerate the ICD-10 code with a custom prompt.
    """
    try:
        # Initialize service and generate ICD-10 codes
        medical_analysis_service = MedicalAnalysisService(db, llm_provider=llm_provider)
        icd10_codes, icd10_relevancy_scores, icd10_llm_descriptions, icd10_prompt_text = await medical_analysis_service.predict_icd10_code(
            diagnosis=diagnosis,
            anatomical_location=anatomical_location or "",
            pdf_content=pdf_content or "",
            custom_prompt=custom_prompt
        )
        
        # Use first code as primary for backward compatibility
        primary_icd10 = icd10_codes[0] if icd10_codes else None
        
        # Look up descriptions for all codes if we have codes
        icd10_description = None
        icd10_descriptions = {}
        if icd10_codes and db:
            icd10_descriptions = medical_analysis_service.lookup_icd10_descriptions(icd10_codes)
            if primary_icd10:
                icd10_description = icd10_descriptions.get(primary_icd10)
        
        return {
            "predicted_icd10": primary_icd10,  # Primary code for backward compatibility
            "predicted_icd10_codes": icd10_codes,  # All codes
            "icd10_relevancy_scores": icd10_relevancy_scores,  # Code -> relevancy score mapping (0-100)
            "icd10_llm_descriptions": icd10_llm_descriptions,  # Code -> LLM description mappings
            "icd10_description": icd10_description,  # Primary description for backward compatibility
            "icd10_descriptions": icd10_descriptions,  # All code -> database description mappings
            "icd10_prompt_text": icd10_prompt_text,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating ICD-10 code: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating ICD-10 code: {str(e)}"
        )


@router.post("/medical-analysis/cpt-codes")
async def generate_cpt_codes(
    search_query: str = Form(...),
    anatomical_location: Optional[str] = Form(None),
    llm_provider: Optional[str] = Form(None),  # Optional: "openai" or "gemini"
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    icd10_code: Optional[str] = Form(None),  # Optional ICD-10 code(s) - comma-separated for multiple codes
    db: Session = Depends(get_db)
):
    """
    Generate and categorize CPT codes based on search query in a single GPT call.
    Also queries database for CPT codes mapped to ICD-10 code if provided.
    Runs both queries in parallel.
    
    This endpoint is called separately after the initial medical analysis to generate CPT codes.
    It requires the search_query from the previous step.
    """
    try:
        # Initialize service and generate CPT codes (both GPT and database)
        medical_analysis_service = MedicalAnalysisService(db, llm_provider=llm_provider)
        # Parse comma-separated ICD-10 codes if provided
        icd10_codes_list = None
        if icd10_code:
            icd10_codes_list = [code.strip() for code in icd10_code.split(',') if code.strip()]
        
        gpt_cpt_codes, cpt_prompt_text, cpt_categorization_prompt_text, db_cpt_codes, cpt_db_descriptions = await medical_analysis_service.generate_cpt_codes_from_analysis(
            search_query=search_query,
            anatomical_location=anatomical_location or "",
            custom_prompt=custom_prompt,
            icd10_code=icd10_codes_list  # Pass as list
        )
        
        return {
            "cpt_codes": gpt_cpt_codes,  # GPT-generated CPT codes (merged from two-step flow)
            "cpt_prompt_text": cpt_prompt_text,  # Step 1: generation prompt
            "cpt_categorization_prompt_text": cpt_categorization_prompt_text,  # Step 2: categorization prompt
            "db_cpt_codes": db_cpt_codes,  # Database-mapped CPT codes from ICD-10
            "cpt_db_descriptions": cpt_db_descriptions,  # code -> long_desc from cpt_consolidated for GPT codes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating CPT codes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating CPT codes: {str(e)}"
        )


@router.get("/medical-analysis/cpt-codes-by-icd10/{icd10_code}")
async def get_cpt_codes_by_icd10(
    icd10_code: str,
    db: Session = Depends(get_db)
):
    """
    Query database to get CPT codes mapped to an ICD-10 code.
    Excludes codes starting with "98" or "99".
    
    Args:
        icd10_code: ICD-10 code (e.g., "D35.2") or comma-separated codes (e.g., "D35.2,D35.1")
        
    Returns:
        Dictionary with list of CPT codes and their descriptions
    """
    try:
        medical_analysis_service = MedicalAnalysisService(db)
        # Support comma-separated codes for multiple ICD-10 codes
        icd10_codes_list = [code.strip() for code in icd10_code.split(',') if code.strip()]
        cpt_codes = medical_analysis_service.get_cpt_codes_from_icd10(icd10_codes_list)
        
        return {
            "icd10_code": icd10_code,  # Original input
            "icd10_codes": icd10_codes_list,  # Parsed list
            "cpt_codes": cpt_codes,
            "count": len(cpt_codes)
        }
        
    except Exception as e:
        logger.error(f"Error querying CPT codes for ICD-10 {icd10_code}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error querying CPT codes: {str(e)}"
        )


@router.post("/medical-analysis/categorize-cpt-codes")
async def categorize_cpt_codes(
    cpt_codes_json: str = Form(...),  # JSON array of CPT codes
    treatment_options_json: str = Form(...),  # JSON array of treatment options for context
    custom_prompt: Optional[str] = Form(None),  # Optional custom prompt to override default
    search_query: Optional[str] = Form(None),  # Optional search query to extract diagnosis terms
    db: Session = Depends(get_db)
):
    """
    Categorize CPT codes using GPT.
    
    Args:
        cpt_codes_json: JSON array of CPT codes with code and description
        treatment_options_json: JSON array of treatment options with categories (for context)
        custom_prompt: Optional custom prompt to override default
        search_query: Optional search query string (e.g., "diagnosis1 OR diagnosis2") to extract diagnosis terms
        
    Returns:
        Dictionary with categorized CPT codes and prompt text
    """
    try:
        # Parse JSON inputs
        try:
            cpt_codes = json.loads(cpt_codes_json)
            treatment_options = json.loads(treatment_options_json)
            if not isinstance(cpt_codes, list) or not isinstance(treatment_options, list):
                raise ValueError("Both inputs must be JSON arrays")
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON: {str(e)}"
            )
        
        # Parse search query into diagnostic/anatomic; use diagnostic terms for categorization
        diagnosis_terms = None
        if search_query:
            diagnostic_terms, _ = parse_search_query(search_query)
            diagnosis_terms = diagnostic_terms if diagnostic_terms else None
        
        # Initialize service and categorize
        medical_analysis_service = MedicalAnalysisService(db)
        categorized_codes, prompt_text = await medical_analysis_service.categorize_cpt_codes(
            cpt_codes=cpt_codes,
            treatment_options=treatment_options,
            custom_prompt=custom_prompt,
            diagnosis_terms=diagnosis_terms
        )
        
        return {
            "categorized_cpt_codes": categorized_codes,
            "count": len(categorized_codes),
            "categorization_prompt_text": prompt_text
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error categorizing CPT codes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error categorizing CPT codes: {str(e)}"
        )
