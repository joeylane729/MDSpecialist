#!/usr/bin/env python3
"""
Simple test script for searching doctor education information using Google Custom Search API.
"""

import os
import requests
import json
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DoctorEducationSearcher:
    def __init__(self):
        # Load API credentials from environment
        self.api_key = os.getenv('GOOGLE_CUSTOM_SEARCH_API_KEY')
        self.search_engine_id = os.getenv('GOOGLE_CUSTOM_SEARCH_ENGINE_ID')
        
        if not self.api_key or not self.search_engine_id:
            raise ValueError("Google Custom Search API credentials not found in environment variables")
        
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    def search_doctor_education(self, first_name: str, last_name: str, city: str, state: str) -> Dict[str, Any]:
        """
        Search for doctor's medical school, residency, and fellowship information.
        """
        print(f"🔍 Searching for Dr. {first_name} {last_name} in {city}, {state}")
        print("=" * 60)
        
        results = {
            'doctor_name': f"{first_name} {last_name}",
            'location': f"{city}, {state}",
            'medical_school': None,
            'residency': None,
            'fellowship': None
        }
        
        # Search for medical school
        print("\n1️⃣ MEDICAL SCHOOL SEARCH")
        print("-" * 30)
        med_school_results = self._search_medical_school(first_name, last_name, city, state)
        results['medical_school'] = med_school_results
        self._print_search_results("Medical School", med_school_results)
        
        # Search for residency
        print("\n2️⃣ RESIDENCY SEARCH")
        print("-" * 30)
        residency_results = self._search_residency(first_name, last_name, city, state)
        results['residency'] = residency_results
        self._print_search_results("Residency", residency_results)
        
        # Search for fellowship
        print("\n3️⃣ FELLOWSHIP SEARCH")
        print("-" * 30)
        fellowship_results = self._search_fellowship(first_name, last_name, city, state)
        results['fellowship'] = fellowship_results
        self._print_search_results("Fellowship", fellowship_results)
        
        return results
    
    def _search_medical_school(self, first_name: str, last_name: str, city: str, state: str) -> Dict[str, Any]:
        """Search for medical school information."""
        query = f'where did {first_name} {last_name} {city} {state} graduate from medical school'
        return self._execute_search(query, "Medical School")
    
    def _search_residency(self, first_name: str, last_name: str, city: str, state: str) -> Dict[str, Any]:
        """Search for residency information."""
        query = f'{first_name} {last_name} {city} {state} residency program site:health.usnews.com OR site:healthgrades.com'
        return self._execute_search(query, "Residency")
    
    def _search_fellowship(self, first_name: str, last_name: str, city: str, state: str) -> Dict[str, Any]:
        """Search for fellowship information."""
        query = f'{first_name} {last_name} {city} {state} fellowship program site:health.usnews.com OR site:healthgrades.com'
        return self._execute_search(query, "Fellowship")
    
    def _execute_search(self, query: str, search_type: str) -> Dict[str, Any]:
        """Execute a Google Custom Search API request."""
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': 5  # Get top 5 results
        }
        
        try:
            print(f"   Query: {query}")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'query': query,
                'total_results': data.get('searchInformation', {}).get('totalResults', '0'),
                'search_time': data.get('searchInformation', {}).get('searchTime', '0'),
                'items': data.get('items', [])
            }
            
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error: {str(e)}")
            return {
                'query': query,
                'error': str(e),
                'items': []
            }
    
    def _print_search_results(self, search_type: str, results: Dict[str, Any]):
        """Print formatted search results."""
        if 'error' in results:
            print(f"   ❌ {search_type} search failed: {results['error']}")
            return
        
        print(f"   📊 Found {results['total_results']} total results")
        print(f"   ⏱️  Search time: {results['search_time']} seconds")
        print(f"   📄 Top {len(results['items'])} results:")
        
        for i, item in enumerate(results['items'], 1):
            print(f"\n   Result {i}:")
            print(f"   Title: {item.get('title', 'N/A')}")
            print(f"   URL: {item.get('link', 'N/A')}")
            print(f"   Snippet: {item.get('snippet', 'N/A')[:200]}...")
            if 'pagemap' in item and 'metatags' in item['pagemap']:
                meta = item['pagemap']['metatags'][0]
                if 'og:description' in meta:
                    print(f"   Description: {meta['og:description'][:200]}...")

def main():
    """Main function to test the doctor education searcher."""
    try:
        # Initialize searcher
        searcher = DoctorEducationSearcher()
        
        # Test with a sample doctor
        print("🏥 Doctor Education Search Test")
        print("=" * 60)
        
        # You can change these values to test with different doctors
        first_name = "Theodore"
        last_name = "Schwartz"
        city = "New York"
        state = "NY"
        
        # Perform searches
        results = searcher.search_doctor_education(first_name, last_name, city, state)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📋 SUMMARY")
        print("=" * 60)
        print(f"Doctor: {results['doctor_name']}")
        print(f"Location: {results['location']}")
        print(f"Medical School Results: {len(results['medical_school'].get('items', []))} found")
        print(f"Residency Results: {len(results['residency'].get('items', []))} found")
        print(f"Fellowship Results: {len(results['fellowship'].get('items', []))} found")
        
        # Save results to JSON file for inspection
        output_file = f"doctor_search_results_{first_name}_{last_name}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Full results saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("Make sure your Google Custom Search API credentials are set in your environment variables.")

if __name__ == "__main__":
    main()
