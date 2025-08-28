#!/usr/bin/env python3
"""
Test search for Theodore Schwartz MD with NPI number and medical school info.
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

def search_theodore_schwartz_with_npi():
    """Search for Theodore Schwartz MD with NPI number and medical school."""
    
    print("🔍 Searching for: Theodore Schwartz MD NPI 1811916455 medical school")
    print("=" * 80)
    
    # Load environment variables
    load_env()
    
    # Get API credentials
    api_key = os.getenv('GOOGLE_SEARCH_API_KEY') or os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
    search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID') or os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
    
    if not api_key or not search_engine_id:
        print("❌ Error: Missing API credentials")
        return
    
    # Search query with NPI
    query = "Theodore Schwartz MD NPI 1811916455 medical school"
    
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': query,
            'num': 10  # Get 10 results
        }
        
        print(f"📡 Making request for: '{query}'")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"✅ Search successful!")
            print(f"🔢 Total results found: {data.get('searchInformation', {}).get('totalResults', 'Unknown')}")
            print(f"⏱️  Search time: {data.get('searchInformation', {}).get('searchTime', 'Unknown')}s")
            
            items = data.get('items', [])
            print(f"📋 Results returned: {len(items)}")
            
            if items:
                print("\n" + "=" * 80)
                print("📝 DETAILED RESULTS WITH ALL METADATA:")
                print("=" * 80)
                
                for i, item in enumerate(items, 1):
                    print(f"\n🔸 RESULT #{i}")
                    print("-" * 60)
                    
                    # Basic info
                    print(f"📰 Title: {item.get('title', 'No title')}")
                    print(f"🔗 Link: {item.get('link', 'No link')}")
                    print(f"📄 Snippet: {item.get('snippet', 'No snippet')}")
                    
                    # Display URL
                    if 'displayLink' in item:
                        print(f"🌐 Display Link: {item['displayLink']}")
                    
                    # HTML title and snippet
                    if 'htmlTitle' in item:
                        print(f"🏷️  HTML Title: {item['htmlTitle']}")
                    
                    if 'htmlSnippet' in item:
                        print(f"📝 HTML Snippet: {item['htmlSnippet']}")
                    
                    # Cache ID
                    if 'cacheId' in item:
                        print(f"💾 Cache ID: {item['cacheId']}")
                    
                    # Formatted URL
                    if 'formattedUrl' in item:
                        print(f"🔧 Formatted URL: {item['formattedUrl']}")
                    
                    # HTML formatted URL
                    if 'htmlFormattedUrl' in item:
                        print(f"🔧 HTML Formatted URL: {item['htmlFormattedUrl']}")
                    
                    # Page map (if available)
                    if 'pagemap' in item:
                        pagemap = item['pagemap']
                        print(f"🗺️  Page Map Keys: {list(pagemap.keys())}")
                        
                        # Common pagemap fields
                        if 'metatags' in pagemap:
                            metatags = pagemap['metatags'][0] if pagemap['metatags'] else {}
                            print(f"🏷️  Meta Description: {metatags.get('description', 'None')}")
                            print(f"🏷️  Meta Keywords: {metatags.get('keywords', 'None')}")
                            print(f"🏷️  Meta Author: {metatags.get('author', 'None')}")
                        
                        if 'cse_image' in pagemap:
                            images = pagemap['cse_image']
                            print(f"🖼️  Images: {len(images)} found")
                            for idx, img in enumerate(images[:2]):  # Show first 2 images
                                print(f"   📷 Image {idx+1}: {img.get('src', 'No src')}")
                        
                        if 'person' in pagemap:
                            persons = pagemap['person']
                            print(f"👤 Persons: {len(persons)} found")
                            for idx, person in enumerate(persons):
                                print(f"   Person {idx+1}: {person}")
                        
                        # Look for any mentions of medical school or education
                        for key, values in pagemap.items():
                            if isinstance(values, list):
                                for value in values:
                                    if isinstance(value, dict):
                                        for subkey, subvalue in value.items():
                                            if any(term in str(subvalue).lower() for term in ['medical school', 'education', 'university', 'college', 'harvard', 'johns hopkins', 'yale']):
                                                print(f"🎓 Education Info ({key}.{subkey}): {subvalue}")
                    
                    # File format (if it's a file)
                    if 'fileFormat' in item:
                        print(f"📁 File Format: {item['fileFormat']}")
                    
                    # MIME type
                    if 'mime' in item:
                        print(f"📄 MIME Type: {item['mime']}")
                    
                    # Labels (if any)
                    if 'labels' in item:
                        print(f"🏷️  Labels: {item['labels']}")
                    
                    print("-" * 60)
                
                # Overall search metadata
                print(f"\n📊 SEARCH METADATA:")
                print("-" * 40)
                search_info = data.get('searchInformation', {})
                for key, value in search_info.items():
                    print(f"{key}: {value}")
                
                if 'queries' in data:
                    print(f"\n🔍 QUERY INFO:")
                    print("-" * 30)
                    queries = data['queries']
                    for query_type, query_list in queries.items():
                        print(f"{query_type}: {query_list}")
                        
            else:
                print("❌ No results found")
                
        else:
            print(f"❌ Search failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    search_theodore_schwartz_with_npi()
