"""
Medical School Service

Service for finding medical school information for doctors via web scraping.
"""

import requests
import re
import time
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .medical_school_ranking_service import MedicalSchoolRankingService


class MedicalSchoolService:
    """Service for finding medical school information for doctors."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ranking_service = MedicalSchoolRankingService(db)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.driver = None
        self._browser_initialized = False
    
    def find_medical_school(self, first_name: str, last_name: str, city: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Search for a doctor and find their medical school.
            
        Returns:
            Dict with school_name and rank if found, None if no match
        """
        # Search for doctor using web scraping
        medical_school = self._scrape_doctor_medical_school(first_name, last_name, city, state)
        
        if not medical_school:
            return None
        
        # Return what we found online (no database lookup for now)
        if isinstance(medical_school, dict):
            return {
                'school_name': medical_school.get('description', ''),
                'title': medical_school.get('title', ''),
                'url': medical_school.get('url', ''),
                'rank': None  # No ranking info since we're not looking up in database
            }
        else:
            # Backward compatibility for string results
            return {
                'school_name': medical_school,
                'title': '',
                'url': '',
                'rank': None
            }
    
    def initialize_browser(self):
        """Initialize the browser once for reuse across multiple searches."""
        if not self._browser_initialized:
            print("🌐 Initializing browser for medical school searches...")
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # Don't add --headless so browser is visible
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self._browser_initialized = True
            print("✅ Browser initialized and ready!")
    
    def close_browser(self):
        """Close the browser when done with all searches."""
        if self.driver and self._browser_initialized:
            print("🔒 Closing browser...")
            self.driver.quit()
            self.driver = None
            self._browser_initialized = False
            print("✅ Browser closed!")
    
    def _scrape_doctor_medical_school(self, first_name: str, last_name: str, city: str, state: str) -> Optional[str]:
        """Scrape medical school from web search using Selenium with visible browser."""
        try:
            # Ensure browser is initialized
            if not self._browser_initialized:
                self.initialize_browser()
            
            # Search for doctor using Google
            query = f"US News {first_name} {last_name} received medical degree {city} {state}"
            search_url = f"https://www.google.com/search?q={query}"
            
            print(f"🔍 Searching for {first_name} {last_name}")
            print(f"   Query: {query}")
            print(f"   URL: {search_url}")
            print()
            
            # Navigate to search
            self.driver.get(search_url)
            
            # Wait for results to load
            time.sleep(3)
            
            # Check if we hit a captcha or human verification
            page_source = self.driver.page_source
            if "unusual traffic" in page_source.lower() or "captcha" in page_source.lower() or "verify you are human" in page_source.lower():
                print("   🤖 Google detected automated traffic - please solve the captcha manually")
                print("   ⏳ Waiting for you to complete human verification...")
                print("   Press ENTER in this terminal when you've completed the verification:")
                input()
                print("   ✅ Continuing with scraping...")
                time.sleep(2)
            
            # Get page source and look for JSON data
            page_source = self.driver.page_source
            
            # Print what we found for debugging
            print(f"📊 Search results analysis:")
            print(f"   Page title: {self.driver.title}")
            print(f"   HTML content length: {len(page_source)} characters")
            
            # Dynamic extraction of US News result - no hardcoded patterns
            import re
            import json
            
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Method 1: Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'description' in data:
                        if 'medical degree' in data['description'].lower() or 'graduated' in data['description'].lower():
                            print(f"   🎓 Found JSON-LD description: {data['description']}")
                            return {
                                'title': data.get('name', ''),
                                'url': data.get('url', ''),
                                'description': data['description']
                            }
                except:
                    continue
            
            # Method 2: Find US News link and extract complete description from its container
            us_news_links = soup.find_all('a', href=lambda x: x and 'health.usnews.com' in x)
            print(f"   🔍 Found {len(us_news_links)} US News links")
            
            for link in us_news_links:
                # Get the complete search result container
                result_div = link.find_parent(['div'], class_=lambda x: x and any(cls in x for cls in ['g', 'tF2Cxc', 'yuRUbf']))
                
                if result_div:
                    # Extract URL
                    url = link.get('href', '')
                    
                    # Extract title
                    title_elem = link.find('h3') or link.find('span')
                    title = title_elem.get_text().strip() if title_elem else ''
                    
                    # Initialize description variable
                    description = None
                    
                    # Get all text from the result container
                    full_text = result_div.get_text()
                    
                    # Also try to get text from specific elements that might contain descriptions
                    description_elements = result_div.find_all(['p', 'span', 'div'], string=lambda text: text and len(text.strip()) > 20)
                    
                    print(f"   🔍 Full text length: {len(full_text)}")
                    print(f"   🔍 Found {len(description_elements)} potential description elements")
                    
                    # If the container text is too short, try getting text from the entire page
                    if len(full_text) < 200:
                        print(f"   🔍 Container text too short, trying page source...")
                        # Look in the raw page source for medical degree info
                        if 'medical degree' in page_source.lower() or 'graduated' in page_source.lower():
                            # Use regex to find the sentence containing medical degree info
                            # Look for complete sentences that end with proper punctuation
                            match = re.search(r'[^.]*received (?:his|her) medical degree from[^.]*(?:and has been in practice|\.)', page_source, re.IGNORECASE)
                            if not match:
                                match = re.search(r'[^.]*graduated from[^.]*medical school[^.]*(?:and has been in practice|\.)', page_source, re.IGNORECASE)
                            if match:
                                description = match.group(0).strip()
                                # Clean up the description
                                description = re.sub(r'<[^>]+>', ' ', description)  # Remove HTML tags
                                description = re.sub(r'&nbsp;', ' ', description)  # Replace nbsp with space
                                description = re.sub(r'\d+\s+\d+\s+\d+[a-z]*\s*', '', description)  # Remove CSS noise like "9 2 2 2z"
                                description = re.sub(r'[^\w\s.,!?]', ' ', description)  # Remove special characters
                                description = re.sub(r'\s+', ' ', description)  # Normalize whitespace
                                description = description.strip()
                                print(f"   ✅ Found description in page source: {description[:100]}...")
                    
                    # Look for medical education info in the full text first
                    if not description and ('medical degree' in full_text.lower() or 'graduated' in full_text.lower()):
                        # Try to extract the sentence containing medical degree info
                        sentences = re.split(r'[.!?]+', full_text)
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if (('medical degree' in sentence.lower() or 'graduated' in sentence.lower()) and 
                                ('school' in sentence.lower() or 'university' in sentence.lower() or 'college' in sentence.lower())):
                                description = sentence
                                print(f"   ✅ Found description in full text: {sentence[:100]}...")
                                break
                    
                    # If not found in full text, check individual elements
                    if not description:
                        for elem in description_elements:
                            text = elem.get_text().strip()
                            if (('medical degree' in text.lower() or 'graduated' in text.lower()) and 
                                ('school' in text.lower() or 'university' in text.lower() or 'college' in text.lower())):
                                description = text
                                print(f"   ✅ Found description in element: {text[:100]}...")
                                break
                    
                    if description:
                        # Clean up the description
                        description = re.sub(r'\s+', ' ', description)
                        description = re.sub(r'[^\w\s.,!?]', ' ', description)
                        description = description.strip()
                        
                        print(f"   🎓 Found US News result:")
                        print(f"   Title: {title}")
                        print(f"   URL: {url}")
                        print(f"   Description: {description}")
                        
                        return {
                            'title': title,
                            'url': url,
                            'description': description
                        }
            
            print(f"   ❌ No US News description found")
            return None
            
        except Exception as e:
            print(f"   ❌ Error during scraping: {str(e)}")
            return None
        finally:
            # Don't close browser here - it will be reused for other doctors
            pass
