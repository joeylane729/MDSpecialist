#!/usr/bin/env python3
"""
Test Google Custom Search API connection and keys.
"""

import os
import requests
import json
from pathlib import Path

# Load environment variables from .env file
def load_env():
    env_path = Path('.env')
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

def test_google_custom_search():
    """Test Google Custom Search API with the configured keys."""
    
    print("🔍 Testing Google Custom Search API")
    print("=" * 50)
    
    # Load environment variables
    load_env()
    
    # Get API credentials
    api_key = os.getenv('GOOGLE_SEARCH_API_KEY') or os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
    search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID') or os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
    
    print(f"🔑 API Key: {'✓ Found' if api_key else '✗ Missing'}")
    print(f"🔧 Search Engine ID: {'✓ Found' if search_engine_id else '✗ Missing'}")
    
    if not api_key:
        print("\n❌ Error: Google Search API key not found in environment variables.")
        print("Expected: GOOGLE_SEARCH_API_KEY or GOOGLE_CUSTOM_SEARCH_API_KEY")
        return False
    
    if not search_engine_id:
        print("\n❌ Error: Google Search Engine ID not found in environment variables.")
        print("Expected: GOOGLE_SEARCH_ENGINE_ID or GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
        return False
    
    # Test search query
    test_query = "Johns Hopkins medical school"
    
    try:
        print(f"\n🧪 Testing search query: '{test_query}'")
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': test_query,
            'num': 3  # Limit to 3 results for testing
        }
        
        print(f"📡 Making request to: {url}")
        response = requests.get(url, params=params)
        
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ API call successful!")
            print(f"🔢 Total results found: {data.get('searchInformation', {}).get('totalResults', 'Unknown')}")
            
            items = data.get('items', [])
            print(f"📋 Results returned: {len(items)}")
            
            if items:
                print("\n📝 Sample results:")
                for i, item in enumerate(items[:3], 1):
                    title = item.get('title', 'No title')
                    link = item.get('link', 'No link')
                    snippet = item.get('snippet', 'No snippet')
                    
                    print(f"\n  {i}. {title}")
                    print(f"     🔗 {link}")
                    print(f"     📄 {snippet[:100]}{'...' if len(snippet) > 100 else ''}")
            
            return True
            
        else:
            print(f"❌ API call failed with status {response.status_code}")
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                print(f"   Error: {error_message}")
                
                # Common error codes
                if response.status_code == 403:
                    print("   💡 This might be due to:")
                    print("      - Invalid API key")
                    print("      - API not enabled in Google Cloud Console")
                    print("      - Quota exceeded")
                elif response.status_code == 400:
                    print("   💡 This might be due to:")
                    print("      - Invalid search engine ID")
                    print("      - Malformed request")
                    
            except:
                print(f"   Raw response: {response.text[:200]}...")
            
            return False
            
    except Exception as e:
        print(f"❌ Error making API request: {e}")
        return False

def main():
    """Main function to test the Google Custom Search API."""
    
    print("🚀 Google Custom Search API Test")
    print("=" * 50)
    
    success = test_google_custom_search()
    
    if success:
        print("\n🎉 Google Custom Search API is working correctly!")
        print("💡 You can now use this API in your medical school service.")
    else:
        print("\n🔧 Please check your API configuration and try again.")

if __name__ == "__main__":
    main()