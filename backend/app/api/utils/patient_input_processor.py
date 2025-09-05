"""
Patient Input Processing Utilities

Shared utilities for processing patient input across different API endpoints.
"""

import logging
from typing import List, Optional
from fastapi import UploadFile

logger = logging.getLogger(__name__)

async def build_patient_input(
    symptoms: str,
    diagnosis: str,
    medical_history: Optional[str] = None,
    medications: Optional[str] = None,
    surgical_history: Optional[str] = None,
    files: Optional[List[UploadFile]] = []
) -> str:
    """
    Build a comprehensive patient input string from individual components and files.
    
    Args:
        symptoms: Patient symptoms
        diagnosis: Patient diagnosis
        medical_history: Medical history (optional)
        medications: Current medications (optional)
        surgical_history: Surgical history (optional)
        files: List of uploaded files (optional)
        
    Returns:
        Combined patient input string
    """
    # Start with symptoms and diagnosis
    patient_input = f"Symptoms: {symptoms}\n\nDiagnosis: {diagnosis}"
    
    # Add optional medical information
    if medical_history:
        patient_input += f"\n\nMedical History: {medical_history}"
    if medications:
        patient_input += f"\n\nCurrent Medications: {medications}"
    if surgical_history:
        patient_input += f"\n\nSurgical History: {surgical_history}"
    
    # Process uploaded files (if any)
    if files:
        patient_input += "\n\nAdditional Information from Files:"
        for file in files:
            if file.content_type == "application/pdf":
                try:
                    # Extract text from PDF files
                    import PyPDF2
                    import io
                    
                    # Read PDF content
                    pdf_content = await file.read()
                    logger.info(f"PDF file size: {len(pdf_content)} bytes")
                    
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
                    logger.info(f"PDF has {len(pdf_reader.pages)} pages")
                    
                    # Extract text from all pages
                    text_content = ""
                    for i, page in enumerate(pdf_reader.pages):
                        page_text = page.extract_text()
                        logger.info(f"Page {i+1} extracted {len(page_text)} characters")
                        text_content += page_text + " "
                    
                    patient_input += f"\n\nFile {file.filename}: {text_content.strip()}"
                    logger.info(f"Successfully processed PDF file: {file.filename}, total text: {len(text_content)} characters")
                except Exception as e:
                    logger.warning(f"Could not process PDF file {file.filename}: {e}")
                    # Fallback to just noting the file was uploaded
                    patient_input += f"\n- {file.filename} (PDF uploaded but could not be processed)"
    
    return patient_input

def log_endpoint_call(endpoint_name: str, symptoms: str, diagnosis: str):
    """
    Log the start of an endpoint call with basic information.
    
    Args:
        endpoint_name: Name of the endpoint being called
        symptoms: Patient symptoms
        diagnosis: Patient diagnosis
    """
    logger.info(f"🔍 DEBUG: {endpoint_name} endpoint called")
    logger.info(f"🔍 DEBUG: Symptoms: {symptoms}")
    logger.info(f"🔍 DEBUG: Diagnosis: {diagnosis}")

def log_response_info(endpoint_name: str, response_data, treatment_options_key: str = "treatment_options"):
    """
    Log response information for an endpoint.
    
    Args:
        endpoint_name: Name of the endpoint
        response_data: Response data to log (can be dict or Pydantic model)
        treatment_options_key: Key to look for treatment options in response
    """
    try:
        logger.info(f"🔍 DEBUG: {endpoint_name} endpoint returning response")
        
        # Convert Pydantic model to dict if needed
        if hasattr(response_data, 'model_dump'):
            # Pydantic v2
            response_dict = response_data.model_dump()
        elif hasattr(response_data, 'dict'):
            # Pydantic v1
            response_dict = response_data.dict()
        elif hasattr(response_data, '__dict__'):
            # Regular object with __dict__
            response_dict = vars(response_data)
        else:
            # Already a dict or other iterable
            response_dict = response_data
        
        # Ensure we have a dictionary to work with
        if not isinstance(response_dict, dict):
            logger.warning(f"🔍 DEBUG: response_dict is not a dict, type: {type(response_dict)}")
            logger.warning(f"🔍 DEBUG: response_dict content: {response_dict}")
            return
        
        # Handle different response structures
        if "patient_profile" in response_dict:
            # Specialist recommendations response structure
            patient_profile = response_dict["patient_profile"]
            logger.info(f"🔍 DEBUG: Response patient_profile keys: {list(patient_profile.keys())}")
            if treatment_options_key in patient_profile:
                logger.info(f"🔍 DEBUG: Response includes {len(patient_profile[treatment_options_key])} treatment options")
            else:
                logger.warning(f"🔍 DEBUG: No {treatment_options_key} in response")
        else:
            # Medical analysis response structure
            logger.info(f"🔍 DEBUG: Analysis results keys: {list(response_dict.keys())}")
            if treatment_options_key in response_dict:
                logger.info(f"🔍 DEBUG: Found {len(response_dict[treatment_options_key])} treatment options")
            else:
                logger.info(f"🔍 DEBUG: No {treatment_options_key} found")
    except Exception as e:
        logger.error(f"🔍 DEBUG: Error in log_response_info: {e}")
        logger.error(f"🔍 DEBUG: response_data type: {type(response_data)}")
        logger.error(f"🔍 DEBUG: response_data: {response_data}")
        raise
