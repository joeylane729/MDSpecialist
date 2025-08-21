import os
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up OpenAI client
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def test_gpt_simple():
    """Test basic GPT API functionality"""
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a helpful medical assistant."},
                {"role": "user", "content": "Hello! Can you help me understand what a cardiologist does?"}
            ],
            max_tokens=150
        )
        
        print("✅ GPT API Test Successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ GPT API Test Failed: {e}")
        return False

def test_gpt_matching():
    """Test GPT API for doctor matching scenario"""
    try:
        prompt = """
        Given this patient scenario, suggest the best medical specialty:
        
        Patient: 45-year-old with chest pain, shortness of breath, and family history of heart disease.
        
        Please suggest the most appropriate medical specialty and explain why in 2-3 sentences.
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a medical expert helping match patients to appropriate specialists."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200
        )
        
        print("\n✅ Doctor Matching Test Successful!")
        print(f"Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print(f"❌ Doctor Matching Test Failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing OpenAI GPT API...")
    print("=" * 50)
    
    # Test 1: Basic functionality
    print("\n1. Testing basic GPT API...")
    test_gpt_simple()
    
    # Test 2: Doctor matching scenario
    print("\n2. Testing doctor matching scenario...")
   # test_gpt_matching()
    
    #print("\n" + "=" * 50)
    print("🎯 GPT API testing complete!")
