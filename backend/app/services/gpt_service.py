import os
import openai
from typing import List, Optional, Tuple
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text

# Load environment variables
load_dotenv()

class GPTService:
    """Service for using GPT to analyze medical diagnoses and determine subspecialties."""
    
    def __init__(self, db: Session = None):
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.db = db
        
        # Available subspecialties for GPT to choose from
        self.available_specialties = [
            "Family Medicine",
            "Internal Medicine", 
            "Neurological Surgery",
            "Nuclear Medicine",
            "Obstetrics & Gynecology",
            "Ophthalmology",
            "Orthopaedic Surgery",
            "Otolaryngology",
            "Pediatric Otolaryngology",
            "Pediatrics",
            "Allergy & Immunology",
            "Anesthesiology",
            "Anatomic Pathology",
            "Clinical Pathology",
            "Emergency Medicine",
            "Colon & Rectal Surgery",
            "General Practice",
            "Thoracic Surgery",
            "Hospitalist",
            "Clinical Pharmacology",
            "Pain Medicine",
            "Interventional Pain Medicine"
        ]
    
    def set_db(self, db: Session):
        """Set the database session for ICD-10 lookups."""
        self.db = db
    
    def lookup_icd10_description(self, code: str) -> Optional[str]:
        """
        Look up the description for an ICD-10 code from the database.
        
        Args:
            code: The ICD-10 code to look up
            
        Returns:
            The description for the code, or None if not found
        """
        if not self.db:
            print("Warning: No database session available for ICD-10 lookup")
            return None
            
        try:
            # Try the original code first
            result = self.db.execute(
                text("SELECT description FROM icd10_codes WHERE code = :code"),
                {"code": code}
            )
            row = result.fetchone()
            if row:
                return row[0]
            
            # If not found, try without the dot (GPT often returns codes with dots like "C71.9")
            code_without_dot = code.replace('.', '')
            if code_without_dot != code:
                result = self.db.execute(
                    text("SELECT description FROM icd10_codes WHERE code = :code"),
                    {"code": code_without_dot}
                )
                row = result.fetchone()
                if row:
                    print(f"Found description for normalized code '{code_without_dot}' (original: '{code}')")
                    return row[0]
            
            return None
        except Exception as e:
            print(f"Error looking up ICD-10 description: {e}")
            return None

    def determine_specialty(self, diagnosis_text: str) -> Optional[str]:
        """
        Use GPT to determine the most relevant medical specialty based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant medical specialty as a string, or None if failed
        """
        try:
            prompt = f"""
            Diagnosis: {diagnosis_text}
            Available: {', '.join(self.available_specialties)}
            
            Return ONLY the specialty name. No explanations.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Medical expert. Respond with ONE specialty name only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1
            )
            
            # Extract the specialty from GPT's response
            specialty = response.choices[0].message.content.strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            specialty = specialty.replace('"', '').replace("'", "").strip()
            
            # Validate that the returned specialty is in our list
            if specialty in self.available_specialties:
                return specialty
            else:
                print(f"Warning: GPT returned '{specialty}' which is not in our specialty list")
                # Try to find a close match
                for available in self.available_specialties:
                    if specialty.lower() in available.lower() or available.lower() in specialty.lower():
                        return available
                
                # If no close match, return the first specialty as fallback
                print(f"Using fallback specialty: {self.available_specialties[0]}")
                return self.available_specialties[0]
                
        except Exception as e:
            print(f"Error in GPT service: {e}")
            return None

    def predict_icd10_code(self, diagnosis_text: str) -> Optional[str]:
        """
        Use GPT to predict the most accurate ICD-10 code based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant ICD-10 code as a string, or None if failed
        """
        try:
            prompt = f"""
            Diagnosis: {diagnosis_text}
            
            Return ONLY the ICD-10 code.
            Example: I21.9
            
            No other text.
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Medical coding expert. Return ICD-10 code only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=20,
                temperature=0.1
            )
            
            # Extract the ICD-10 code from GPT's response
            icd_code = response.choices[0].message.content.strip()
            
            # Clean up the response (remove quotes, extra punctuation, etc.)
            icd_code = icd_code.replace('"', '').replace("'", "").strip()
            
            # Basic validation that it looks like an ICD-10 code (letter followed by numbers)
            if len(icd_code) >= 3 and icd_code[0].isalpha() and any(c.isdigit() for c in icd_code):
                return icd_code
            else:
                print(f"Warning: GPT returned '{icd_code}' which doesn't look like a valid ICD-10 code")
                return None
                
        except Exception as e:
            print(f"Error in GPT ICD-10 prediction: {e}")
            return None
