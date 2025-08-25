import os
import openai
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GPTService:
    """Service for using GPT to analyze medical diagnoses and determine subspecialties."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
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
    
    def determine_specialty(self, diagnosis_text: str) -> Optional[str]:
        """
        Use GPT to determine the most relevant medical specialty based on diagnosis text.
        
        Args:
            diagnosis_text: The patient's diagnosis description
            
        Returns:
            The most relevant medical specialty as a string, or None if failed
        """
        try:
            # Create the prompt for GPT
            prompt = f"""
            You are a medical expert. Given the patient's diagnosis description below, 
            determine the most appropriate medical specialty from the provided list.
            
            Patient Diagnosis: {diagnosis_text}
            
            Available Specialties: {', '.join(self.available_specialties)}
            
            Instructions: 
            - Analyze the diagnosis description carefully
            - Choose the SINGLE most relevant specialty from the list above
            - Respond with ONLY the specialty name (one word or phrase)
            - Do not include any explanations, justifications, or additional text
            - If no specialty clearly matches, choose the closest one
            
            Response (specialty name only):
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a medical expert specializing in patient-specialist matching. Always respond with exactly one specialty name from the provided list."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.1  # Low temperature for consistent, focused responses
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
