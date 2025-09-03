"""
Patient Input Processing Utilities

Shared utilities for processing patient input across different API endpoints.
"""

import logging
from typing import List, Optional
from fastapi import UploadFile

logger = logging.getLogger(__name__)

def build_patient_input(
    symptoms: str,
    diagnosis: str,
    medical_history: Optional[str] = None,
    medications: Optional[str] = None,
    surgical_history: Optional[str] = None,
    files: List[UploadFile] = []
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
                    # For now, just note that files were uploaded
                    # In a full implementation, you'd extract text from PDFs
                    patient_input += f"\n- {file.filename} (PDF uploaded)"
                except Exception as e:
                    logger.warning(f"Could not process file {file.filename}: {e}")
    
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
    logger.info(f"🔍 DEBUG: {endpoint_name} endpoint returning response")
    
    # Convert Pydantic model to dict if needed
    if hasattr(response_data, 'dict'):
        response_dict = response_data.dict()
    elif hasattr(response_data, 'model_dump'):
        response_dict = response_data.model_dump()
    else:
        response_dict = response_data
    
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
