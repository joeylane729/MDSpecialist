#!/usr/bin/env python3
"""Scrape Healthgrades reviews for neuro specialists using Selenium"""

import os
import sys
import csv
import json
import time
import re
import subprocess
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# Try to use webdriver-manager for automatic ChromeDriver management
try:
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WEBDRIVER_MANAGER = True
except ImportError:
    USE_WEBDRIVER_MANAGER = False
    print("⚠️  webdriver-manager not installed. Install with: pip install webdriver-manager")

# Add parent directory to path to import from data/healthgrades
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configuration
BASE_DIR = Path(__file__).parent.parent
VERIFICATION_CSV = BASE_DIR / "neuro_specialists_verification_results.csv"
ALL_MATCHES_CSV = BASE_DIR / "healthgrades_neurosurgeon_all_matches.csv"
SCRAPED_PAGES_DIR = BASE_DIR / "scraped_pages_healthgrades"
REVIEWS_OUTPUT_DIR = BASE_DIR / "reviews_scraper" / "reviews_pages"
MAPPING_CSV = BASE_DIR / "reviews_scraper" / "npi_reviews_mapping.csv"

# Create output directories
REVIEWS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_match_id_from_filename(filename):
    """Extract match_id from filename like 'hg_000001_KIMBERLY_PAGE.md' -> 'hg_000001'"""
    if not filename or filename == "None" or "None" in filename:
        return None
    match = re.match(r'^(hg_\d+)', filename)
    return match.group(1) if match else None

def get_url_from_all_matches(match_id):
    """Get URL from all_matches CSV using match_id"""
    if not match_id:
        return None
    
    try:
        with open(ALL_MATCHES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['match_id'] == match_id:
                    return row['url']
    except Exception as e:
        print(f"   ⚠️  Error reading all_matches CSV: {e}")
    
    return None

def extract_url_from_md_file(md_filepath):
    """Try to extract URL from markdown file by looking for healthgrades.com links"""
    try:
        with open(md_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for links to healthgrades.com/physician
        pattern = r'https://www\.healthgrades\.com/physician/[^\s\)]+'
        matches = re.findall(pattern, content)
        if matches:
            # Get the base URL (remove /comments if present)
            url = matches[0].split('/comments')[0]
            return url
    except Exception as e:
        print(f"   ⚠️  Error reading md file {md_filepath}: {e}")
    
    return None

def get_doctor_url(npi, filename):
    """Get URL for a doctor using filename lookup or md file extraction"""
    # First, try to get URL from all_matches CSV using match_id
    match_id = extract_match_id_from_filename(filename)
    if match_id:
        url = get_url_from_all_matches(match_id)
        if url:
            print(f"      ✓ Found URL from all_matches CSV: {url}")
            return url
    
    # Fallback: try to extract from md file
    if filename and filename != "None" and "None" not in filename:
        md_filepath = SCRAPED_PAGES_DIR / filename
        if md_filepath.exists():
            url = extract_url_from_md_file(md_filepath)
            if url:
                print(f"      ✓ Found URL from md file: {url}")
                return url
        else:
            print(f"      ⚠️  MD file not found: {md_filepath}")
    
    print(f"      ❌ Could not find URL for filename: {filename}")
    return None

def setup_selenium_driver():
    """Setup and return Selenium WebDriver"""
    chrome_options = Options()
    # Run in headless mode for production, remove for debugging
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Fix macOS security popup issue
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("detach", True)
    
    # User agent to avoid detection
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Try multiple strategies to get ChromeDriver working
    strategies = []
    
    # Strategy 1: Try webdriver-manager (if available)
    if USE_WEBDRIVER_MANAGER:
        try:
            print("   🔧 Attempting to use webdriver-manager...")
            driver_path = ChromeDriverManager().install()
            print(f"   ✓ ChromeDriver found at: {driver_path}")
            
            # On macOS, we need to fix permissions and remove quarantine
            import subprocess
            import os
            import stat
            if os.path.exists(driver_path):
                try:
                    # Make executable
                    os.chmod(driver_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    print("   ✓ Made ChromeDriver executable")
                    
                    # Remove all extended attributes (quarantine, etc.)
                    result = subprocess.run(['xattr', '-c', driver_path], 
                                          capture_output=True, check=False)
                    if result.returncode == 0:
                        print("   ✓ Removed all extended attributes")
                    else:
                        # Try individual removal
                        for attr in ['com.apple.quarantine', 'com.apple.metadata:kMDItemWhereFroms']:
                            subprocess.run(['xattr', '-d', attr, driver_path], 
                                          capture_output=True, check=False)
                        print("   ✓ Removed quarantine attributes")
                except Exception as e:
                    print(f"   ⚠️  Could not fix permissions: {e}")
            
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("   ✅ ChromeDriver initialized successfully")
            return driver
        except Exception as e:
            print(f"   ⚠️  webdriver-manager failed: {e}")
            strategies.append(("webdriver-manager", str(e)))
    
    # Strategy 2: Try system ChromeDriver in PATH
    try:
        print("   🔧 Attempting to use system ChromeDriver...")
        service = Service()  # Will use ChromeDriver from PATH
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("   ✅ ChromeDriver initialized successfully (system)")
        return driver
    except Exception as e:
        print(f"   ⚠️  System ChromeDriver failed: {e}")
        strategies.append(("system", str(e)))
    
    # Strategy 3: Try common ChromeDriver locations
    common_paths = [
        '/usr/local/bin/chromedriver',
        '/opt/homebrew/bin/chromedriver',
        '/usr/bin/chromedriver',
    ]
    
    for path in common_paths:
        import os
        if os.path.exists(path):
            try:
                print(f"   🔧 Attempting to use ChromeDriver at {path}...")
                # Remove quarantine if needed
                try:
                    subprocess.run(['xattr', '-d', 'com.apple.quarantine', path], 
                                  capture_output=True, check=False)
                except:
                    pass
                
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                print(f"   ✅ ChromeDriver initialized successfully ({path})")
                return driver
            except Exception as e:
                print(f"   ⚠️  ChromeDriver at {path} failed: {e}")
                strategies.append((path, str(e)))
    
    # All strategies failed
    print(f"\n❌ Error: Could not set up Chrome driver after trying {len(strategies)} strategies")
    print("\n💡 Solutions:")
    print("   1. Install webdriver-manager: pip install webdriver-manager")
    print("   2. Install ChromeDriver: brew install chromedriver")
    print("   3. Allow ChromeDriver in System Preferences > Security & Privacy")
    print("   4. Remove quarantine: xattr -d com.apple.quarantine /path/to/chromedriver")
    print("\n   Failed attempts:")
    for strategy, error in strategies:
        print(f"      - {strategy}: {error[:100]}")
    
    return None

def click_show_more_reviews(driver, max_clicks=1000):
    """Click 'Show more reviews' button until all reviews are loaded"""
    clicks = 0
    
    # Keep clicking until no more buttons found (removed click limit - will click as many times as needed)
    while True:
        try:
            # Try multiple selectors for the "Show more reviews" button
            selectors = [
                "//a[contains(text(), 'Show more reviews')]",
                "//button[contains(text(), 'Show more reviews')]",
                "//a[contains(@href, '/comments') and contains(text(), 'Show more')]",
                "//button[contains(@class, 'show-more')]",
                "//a[contains(@class, 'show-more-reviews')]",
            ]
            
            button_found = False
            for selector in selectors:
                try:
                    # Use find_elements (no wait!) - returns empty list immediately if not found
                    buttons = driver.find_elements(By.XPATH, selector)
                    
                    # Check if any are visible and clickable
                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            # Scroll to button
                            driver.execute_script("arguments[0].scrollIntoView(true);", button)
                            # Click using JavaScript to avoid interception
                            driver.execute_script("arguments[0].click();", button)
                            button_found = True
                            clicks += 1
                            print(f"      ✓ Clicked 'Show more reviews' ({clicks})")
                            # Wait for new reviews to appear
                            time.sleep(0.3)  # Brief wait for DOM update
                            break
                    
                    if button_found:
                        break
                        
                except Exception:
                    continue
            
            if not button_found:
                # No more "Show more" buttons found
                break
            
            # Safety check to prevent infinite loops
            if clicks >= max_clicks:
                print(f"      ⚠️  Reached max clicks ({max_clicks}), stopping")
                break
                
        except Exception as e:
            # No more buttons or error
            break
    
    if clicks > 0:
        print(f"      ✓ Expanded reviews with {clicks} clicks")
    else:
        print(f"      ℹ No 'Show more reviews' button found or already expanded")
    
    return clicks

def click_more_details_buttons(driver):
    """Click all 'More details' buttons to expand truncated review text"""
    print(f"      🔍 Looking for 'More details' buttons...")
    
    # Try multiple selectors for the "More details" button
    more_details_selectors = [
        "//button[contains(text(), 'More details')]",
        "//a[contains(text(), 'More details')]",
        "//span[contains(text(), 'More details')]/parent::button",
        "//span[contains(text(), 'More details')]/parent::a",
        "//button[contains(., 'More details')]",
        "//a[contains(., 'More details')]",
    ]
    
    clicks = 0
    max_attempts = 100  # Safety limit
    
    while clicks < max_attempts:
        button_clicked = False
        
        for selector in more_details_selectors:
            try:
                buttons = driver.find_elements(By.XPATH, selector)
                for button in buttons:
                    try:
                        if button.is_displayed() and button.is_enabled():
                            # Scroll to button to make it visible
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", button)
                            
                            # Click using JavaScript for more reliability
                            driver.execute_script("arguments[0].click();", button)
                            clicks += 1
                            button_clicked = True
                            break
                    except Exception as e:
                        continue
                
                if button_clicked:
                    break
            except:
                continue
        
        # If no button was clicked in this iteration, we're done
        if not button_clicked:
            break
    
    if clicks > 0:
        print(f"      ✓ Clicked {clicks} 'More details' buttons to expand reviews")
    else:
        print(f"      ℹ️  No 'More details' buttons found (reviews may already be expanded)")
    
    return clicks

def extract_rating_from_element(elem_soup):
    """Extract star rating from a review element"""
    rating = None
    
    # Strategy 1: Look for aria-label with rating text (e.g., "5 out of 5 stars")
    aria_labels = elem_soup.find_all(attrs={'aria-label': re.compile(r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star', re.I)})
    for label in aria_labels:
        match = re.search(r'(\d+)', label.get('aria-label', ''))
        if match:
            rating = int(match.group(1))
            if 1 <= rating <= 5:
                return rating
    
    # Strategy 2: Look for data-rating attribute
    data_rating = elem_soup.find(attrs={'data-rating': True})
    if data_rating:
        try:
            rating = int(data_rating.get('data-rating', 0))
            if 1 <= rating <= 5:
                return rating
        except:
            pass
    
    # Strategy 3: Count filled stars in SVG elements
    # Look for SVG stars - filled stars typically have a fill color or specific class
    star_elements = elem_soup.find_all(['svg', 'i', 'span'], class_=re.compile(r'star|rating', re.I))
    if star_elements:
        filled_count = 0
        for star in star_elements:
            # Check if star is filled (has fill color, or class indicating filled)
            classes = star.get('class', [])
            if isinstance(classes, str):
                classes = [classes]
            fill_attr = star.get('fill', '')
            style = star.get('style', '')
            
            # Check for filled indicators
            if (any('fill' in c.lower() or 'active' in c.lower() or 'full' in c.lower() for c in classes) or
                fill_attr and fill_attr not in ['none', 'transparent'] or
                'fill' in style.lower() and 'none' not in style.lower()):
                filled_count += 1
        
        if 1 <= filled_count <= 5:
            return filled_count
    
    # Strategy 4: Look for text patterns like "5.0" or "5 stars" near the review
    text = elem_soup.get_text()
    rating_patterns = [
        r'(\d+)\.?\d*\s*(?:out\s*of\s*)?\d*\s*star',
        r'rating[:\s]+(\d+)',
        r'(\d+)/5',
        r'(\d+)\s*star',
    ]
    for pattern in rating_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                rating = int(match.group(1))
                if 1 <= rating <= 5:
                    return rating
            except:
                pass
    
    return None

def extract_reviews_from_page(driver):
    """Extract review comments from the current page"""
    reviews = []
    
    try:
        # First, try to find review elements using Selenium (more reliable for dynamic content)
        print(f"      🔍 Searching for review elements...")
        
        # Try to find review elements directly with Selenium
        # Look for actual review items, not summary sections
        review_elements_selenium = []
        selectors = [
            # PRIMARY: Use the actual review container class from Healthgrades
            "//div[contains(@class, 'l-single-comment-container')]",
            # Fallback selectors
            "//div[contains(@class, 'review-item')]",
            "//div[contains(@class, 'review-card')]",
            "//div[contains(@class, 'review-content')]",
            "//article[contains(@class, 'review-item')]",
            "//div[contains(@class, 'comment-item')]",
            "//div[contains(@class, 'comment-content')]",
            "//div[contains(@data-testid, 'review-item')]",
            "//div[contains(@data-testid, 'review-card')]",
            "//div[contains(@data-testid, 'comment-item')]",
            # Last resort fallback
            "//div[contains(@class, 'review')]",
            "//article[contains(@class, 'review')]",
            "//div[contains(@class, 'comment')]",
        ]
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    print(f"      ✓ Found {len(elements)} elements with selector: {selector[:50]}...")
                    review_elements_selenium = elements
                    break
            except:
                continue
        
        # Get page source and parse with BeautifulSoup
        page_source = driver.page_source  # Store for rating extraction
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Healthgrades reviews page structure - try to find review containers
        # Reviews are typically in sections or divs with specific patterns
        review_containers = []
        
        # Store review elements with their HTML for rating extraction
        review_elements_with_html = []
        if review_elements_selenium:
            for elem in review_elements_selenium:
                try:
                    html = elem.get_attribute('outerHTML')
                    if html:
                        elem_soup = BeautifulSoup(html, 'html.parser')
                        review_containers.append(elem_soup)
                        review_elements_with_html.append(elem_soup)
                except:
                    continue
        
        # Also try multiple strategies to find reviews in full page
        strategies = [
            # Strategy 1: Look for common review container classes/ids
            lambda: soup.find_all(['div', 'article', 'section'], 
                                 class_=re.compile(r'review|comment|rating|feedback', re.I)),
            # Strategy 2: Look for data attributes
            lambda: soup.find_all(['div', 'article'], 
                                 attrs={'data-testid': re.compile(r'review|comment', re.I)}),
        ]
        
        for strategy in strategies:
            try:
                elements = strategy()
                if elements and not review_containers:
                    review_containers = [soup.new_tag('div')]  # Create container
                    for el in elements:
                        review_containers[0].append(el)
                    break
            except:
                continue
        
        # Extract reviews from page text directly (more reliable)
        # Get the full page text
        page_text = soup.get_text(separator='\n')
        seen_texts = set()
        
        # Initialize element_ratings dictionary (will be populated by rating extraction)
        element_ratings = {}
        
        # FIRST: Extract ratings from Selenium elements
        if review_elements_selenium:
            print(f"      🔍 Extracting ratings from {len(review_elements_selenium)} review elements...")
            for idx, elem in enumerate(review_elements_selenium):
                try:
                    rating = None
                    # Try multiple selectors for rating - prioritize aria-label with "Rated X out of 5"
                    rating_selectors = [
                        # PRIMARY: Look for aria-label="Rated X out of 5" (exact Healthgrades format)
                        (By.XPATH, ".//*[contains(@aria-label, 'Rated') and contains(@aria-label, 'out of 5')]"),
                        (By.XPATH, ".//*[contains(@aria-label, 'star')]"),
                        (By.XPATH, ".//*[@data-rating]"),
                        (By.XPATH, ".//*[contains(@class, 'star')]"),
                        (By.XPATH, ".//*[contains(@class, 'rating')]"),
                        (By.XPATH, ".//svg[contains(@class, 'star')]"),
                        (By.XPATH, ".//*[contains(@aria-label, 'rating')]"),
                        (By.XPATH, ".//*[contains(@title, 'star')]"),
                        (By.XPATH, ".//span[contains(@class, 'star')]"),
                        (By.XPATH, ".//div[contains(@class, 'star')]"),
                    ]
                    for by, selector in rating_selectors:
                        try:
                            rating_elems = elem.find_elements(by, selector)
                            for rating_elem in rating_elems:
                                # Try aria-label - prioritize "Rated X out of 5" format
                                aria_label = rating_elem.get_attribute('aria-label') or ''
                                if 'rated' in aria_label.lower() and 'out of 5' in aria_label.lower():
                                    # Extract from "Rated 5 out of 5"
                                    match = re.search(r'rated\s+(\d+)', aria_label, re.I)
                                    if match:
                                        rating = int(match.group(1))
                                        if 1 <= rating <= 5:
                                            break
                                elif 'star' in aria_label.lower() or 'rating' in aria_label.lower():
                                    match = re.search(r'(\d+)', aria_label)
                                    if match:
                                        rating = int(match.group(1))
                                        if 1 <= rating <= 5:
                                            break
                                
                                # Try title
                                title = rating_elem.get_attribute('title') or ''
                                if 'star' in title.lower() or 'rating' in title.lower():
                                    match = re.search(r'(\d+)', title)
                                    if match:
                                        rating = int(match.group(1))
                                        if 1 <= rating <= 5:
                                            break
                                
                                # Try data-rating
                                data_rating = rating_elem.get_attribute('data-rating')
                                if data_rating:
                                    try:
                                        rating = int(data_rating)
                                        if 1 <= rating <= 5:
                                            break
                                    except:
                                        pass
                                
                                # Try text content
                                elem_text = rating_elem.text
                                if elem_text:
                                    rating_match = re.search(r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star', elem_text, re.I)
                                    if rating_match:
                                        try:
                                            rating = int(rating_match.group(1))
                                            if 1 <= rating <= 5:
                                                break
                                        except:
                                            pass
                            if rating:
                                break
                        except:
                            continue
                    
                    # If still no rating, try parsing from element text directly
                    if not rating:
                        elem_text = elem.text[:300]
                        rating_patterns = [
                            r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star',
                            r'rating[:\s]+(\d+)',
                            r'(\d+)/5',
                        ]
                        for pattern in rating_patterns:
                            rating_match = re.search(pattern, elem_text, re.I)
                            if rating_match:
                                try:
                                    rating = int(rating_match.group(1))
                                    if 1 <= rating <= 5:
                                        break
                                except:
                                    pass
                    
                    if rating:
                        element_ratings[idx] = rating
                        print(f"      ✓ Found rating {rating} for element {idx+1}")
                    elif idx < 3:  # Debug first 3
                        print(f"      ⚠️  No rating for element {idx+1}, preview: {elem.text[:80]}")
                except Exception as e:
                    if idx < 3:
                        print(f"      ⚠️  Error extracting rating from element {idx+1}: {e}")
                    continue
            
            print(f"      📊 Extracted {len(element_ratings)} ratings from {len(review_elements_selenium)} elements")
        
        # Pattern to match dates: "Sep 10, 2025" or "January 12, 2024"
        # Month abbreviations: Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec
        date_pattern = re.compile(
            r'((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+)?'  # Optional author name with "–" before date
            r'(?:[A-Z][a-z]{2,3}\s+\d{1,2},\s+\d{4}|'  # "Sep 10, 2025" or "Jan 12, 2024"
            r'[A-Z][a-z]+\s+\d{1,2},\s+\d{4}))'  # "January 12, 2024"
        )
        
        # SECOND: Extract reviews directly from Selenium elements (with ratings already paired)
        # This ensures ratings match reviews perfectly since they come from the same element
        if review_elements_selenium and len(element_ratings) > 0:
            print(f"      🔍 Extracting reviews from {len(review_elements_selenium)} Selenium elements (with ratings)...")
            selenium_reviews_found = 0
            for idx, elem in enumerate(review_elements_selenium):
                try:
                    elem_text = elem.text
                    # Skip if this looks like a header/navigation element
                    if len(elem_text) < 50 or 'Your trust is our top concern' in elem_text:
                        if idx < 3:
                            print(f"      ⚠️  Skipping element {idx+1}: too short or header text")
                        continue
                    
                    # Try to extract review text, date, and author from element
                    # First, try to find the review comment section directly
                    review_comment_elem = None
                    review_text = None
                    try:
                        # Look for the actual comment div
                        review_comment_elem = elem.find_element(By.XPATH, ".//div[@data-qa-target='user-comment']")
                        if review_comment_elem:
                            review_text = review_comment_elem.text.strip()
                            elem_text = review_text  # Use this for date matching
                    except:
                        pass
                    
                    # Also try to find date in commenter-info
                    date_elem = None
                    date_str = None
                    author = None
                    try:
                        date_elem = elem.find_element(By.XPATH, ".//div[@data-qa-target='comment-date']")
                        if date_elem:
                            date_text = date_elem.text
                            # Extract date and author from date element text
                            date_match = date_pattern.search(date_text)
                            if date_match:
                                date_str = date_match.group(1).strip()
                                # Extract author if present
                                author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                                if author_match:
                                    author = author_match.group(1)
                                    date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                    except:
                        pass
                    
                    # Fallback: try to find date in element text
                    if not date_str:
                        date_match = date_pattern.search(elem_text)
                        if date_match:
                            date_str = date_match.group(1).strip()
                            # Extract author if present
                            author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                            if author_match:
                                author = author_match.group(1)
                                date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                    
                    # If we found review text from comment element, use it directly
                    if review_text and date_str:
                    
                        # Clean up review text (already extracted from comment element)
                        review_text = re.sub(r'(×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No|Reply\s+Flag)', '', review_text, flags=re.I)
                        review_text = re.sub(r'More\s+details', '', review_text, flags=re.I)
                        review_text = re.sub(r'\d+\s+other.*?found\s+this\s+helpful', '', review_text, flags=re.I)
                        review_text = re.sub(r'Helpful', '', review_text, flags=re.I)
                        review_text = re.sub(r'\s+', ' ', review_text)
                        review_text = review_text.strip()
                    elif date_match:
                        # Fallback: extract from element text if comment element not found
                        date_str = date_match.group(1).strip()
                        
                        # Extract author if present
                        author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                        if author_match:
                            author = author_match.group(1)
                            date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                        
                        # Extract review text (everything before the date)
                        review_text_raw = elem_text[:date_match.start()].strip()
                        
                        # Clean up review text
                        review_text = review_text_raw
                        review_text = re.sub(r'(×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No|Reply\s+Flag)', '', review_text, flags=re.I)
                        review_text = re.sub(r'More\s+details', '', review_text, flags=re.I)
                        review_text = re.sub(r'\d+\s+other.*?found\s+this\s+helpful', '', review_text, flags=re.I)
                        review_text = re.sub(r'Helpful', '', review_text, flags=re.I)
                        review_text = re.sub(r'\s+', ' ', review_text)
                        review_text = review_text.strip()
                    else:
                        if idx < 3:
                            print(f"      ⚠️  No date found in element {idx+1}, preview: {elem_text[:100]}")
                        continue
                    
                    if review_text and date_str:
                        
                        # Validate review
                        text_lower = review_text.lower()
                        review_indicators = ['doctor', 'dr.', 'patient', 'visit', 'appointment', 
                                             'treatment', 'care', 'experience', 'recommend', 
                                             'good', 'bad', 'office', 'staff', 'time', 'surgery', 
                                             'procedure', 'helped', 'would recommend', 'worst', 'best', 
                                             'veterinarian', 'dismissive', 'rude', 'arrogant', 'terrible',
                                             'seizures', 'neurologist', 'hospital', 'uncle', 'nice', 'fast']
                        
                        if (30 < len(review_text) < 5000 and 
                            review_text not in seen_texts and
                            any(indicator in text_lower for indicator in review_indicators)):
                            # Get rating from element_ratings (paired by index!)
                            rating = element_ratings.get(idx)
                            
                            reviews.append({
                                'text': review_text,
                                'date': date_str,
                                'author': author,
                                'rating': rating
                            })
                            seen_texts.add(review_text)
                            selenium_reviews_found += 1
                            if rating:
                                print(f"      ✓ Extracted review {len(reviews)} with rating {rating}")
                            else:
                                print(f"      ✓ Extracted review {len(reviews)} (no rating)")
                except Exception as e:
                    if idx < 3:
                        print(f"      ⚠️  Error extracting review from element {idx+1}: {e}")
                    continue
            
            print(f"      📊 Extracted {selenium_reviews_found} reviews from Selenium elements")
        
        # FALLBACK: Extract from text blocks ONLY if Selenium extraction didn't work or found very few
        if len(reviews) == 0:
            print(f"      ⚠️  No reviews from Selenium elements, falling back to text extraction...")
            use_text_extraction = True
        elif len(reviews) < 3:
            print(f"      ⚠️  Only {len(reviews)} reviews from Selenium, supplementing with text extraction...")
            use_text_extraction = True
        else:
            print(f"      ✅ Successfully extracted {len(reviews)} reviews from Selenium (skipping text extraction)")
            use_text_extraction = False
        
        if use_text_extraction:
            review_blocks = re.split(r'Reply\s+Flag', page_text, flags=re.I)
            
            for block in review_blocks:
                block = block.strip()
                if len(block) < 30:
                    continue
                
                # Find all dates in this block
                date_matches = list(date_pattern.finditer(block))
                
                if not date_matches:
                    continue
                
                # Process each date in this block (there might be multiple reviews in one block)
                for i, date_match in enumerate(date_matches):
                    date_str = date_match.group(1).strip()
                    
                    # Extract author if present in date string (format: "Author Name – Sep 10, 2025")
                    author = None
                    author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                    if author_match:
                        author = author_match.group(1)
                        # Extract just the date part
                        date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                    
                    # Find the start of this review text (everything before this date, but after previous date if exists)
                    if i > 0:
                        # Start from the end of previous date match
                        start_pos = date_matches[i-1].end()
                    else:
                        # For first date in block, start from beginning of block
                        start_pos = 0
                    
                    # Extract review text between start_pos and date_match.start()
                    review_text_raw = block[start_pos:date_match.start()].strip()
                    
                    # Clean up review text - remove UI elements
                    review_text = review_text_raw
                    review_text = re.sub(r'(×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No)', '', review_text, flags=re.I)
                    review_text = re.sub(r'More\s+details', '', review_text, flags=re.I)
                    review_text = re.sub(r'\d+\s+other.*?found\s+this\s+helpful', '', review_text, flags=re.I)
                    review_text = re.sub(r'Helpful', '', review_text, flags=re.I)
                    review_text = re.sub(r'\s+', ' ', review_text)  # Normalize whitespace
                    review_text = review_text.strip()
                    
                    # Filter out navigation and summary content
                    text_lower = review_text.lower()
                    nav_keywords = ['find a doctor', 'menu', 'search', 'sign in', 'healthgrades']
                    if any(kw in text_lower for kw in nav_keywords) and len(review_text) > 500:
                        continue
                    
                    # Exclude summary/statistics
                    exclude_patterns = [
                        r'likelihood to recommend',
                        r'\d+\s+ratings?\s*,\s*\d+\s+with',
                        r'leave a review',
                        r'how was your experience',
                    ]
                    if any(re.search(pattern, review_text, re.I) for pattern in exclude_patterns):
                        continue
                    
                    # Must have review-like content
                    review_indicators = ['doctor', 'dr.', 'patient', 'visit', 'appointment', 
                                         'treatment', 'care', 'experience', 'recommend', 
                                         'good', 'bad', 'office', 'staff', 'time', 'surgery', 
                                         'procedure', 'helped', 'would recommend', 'worst', 'best', 
                                         'veterinarian', 'dismissive', 'rude', 'arrogant', 'terrible',
                                         'seizures', 'neurologist', 'hospital', 'uncle', 'nice', 'fast']
                    
                    # Valid review: substantial length, contains review indicators, not duplicate
                    if (30 < len(review_text) < 5000 and 
                        review_text not in seen_texts and
                        any(indicator in text_lower for indicator in review_indicators)):
                        # Try to find rating for this review by matching to Selenium elements
                        rating = None
                        
                        # Strategy 1: Search HTML source near this review for rating patterns
                        # Look in a wider context around the review in the page source
                        try:
                            # Find the review text in the page source
                            review_start = page_source.find(review_text[:100])
                            if review_start > 0:
                                # Search 500 chars before and after the review for rating patterns
                                search_start = max(0, review_start - 500)
                                search_end = min(len(page_source), review_start + len(review_text) + 500)
                                context_html = page_source[search_start:search_end]
                                
                                # Look for rating in HTML attributes
                                rating_patterns_html = [
                                    r'aria-label=["\']([^"\']*?(\d+)\s*(?:out\s*of\s*)?\d*\s*star[^"\']*?)["\']',
                                    r'data-rating=["\'](\d+)["\']',
                                    r'title=["\']([^"\']*?(\d+)\s*(?:out\s*of\s*)?\d*\s*star[^"\']*?)["\']',
                                ]
                                for pattern in rating_patterns_html:
                                    match = re.search(pattern, context_html, re.I)
                                    if match:
                                        # Extract number from match
                                        num_match = re.search(r'(\d+)', match.group(0))
                                        if num_match:
                                            try:
                                                rating = int(num_match.group(1))
                                                if 1 <= rating <= 5:
                                                    print(f"      ✓ Found rating {rating} in HTML near review: {review_text[:50]}...")
                                                    break
                                            except:
                                                pass
                        except:
                            pass
                        
                        # Strategy 2: Match review text to Selenium elements by content overlap
                        if not rating and review_elements_selenium and element_ratings:
                            review_snippet = review_text[:150].strip().lower()
                            for elem_idx, elem in enumerate(review_elements_selenium):
                                try:
                                    elem_text = elem.text.lower()
                                    if review_snippet and len(review_snippet) > 50:
                                        if review_snippet[:100] in elem_text and elem_idx in element_ratings:
                                            rating = element_ratings[elem_idx]
                                            print(f"      ✓ Matched rating {rating} to review (element {elem_idx+1})")
                                            break
                                except:
                                    continue
                        
                        # Strategy 3: Try text pattern matching in the block
                        if not rating:
                            rating_match = re.search(r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star', block[start_pos:date_match.start()], re.I)
                            if rating_match:
                                try:
                                    rating = int(rating_match.group(1))
                                    if not (1 <= rating <= 5):
                                        rating = None
                                except:
                                    pass
                        
                        reviews.append({
                            'text': review_text,
                            'date': date_str,
                            'author': author,
                            'rating': rating
                        })
                        seen_texts.add(review_text)
        
        # If still no reviews found, try alternative extraction from containers
                date_str = date_match.group(1).strip()
                
                # Extract author if present in date string (format: "Author Name – Sep 10, 2025")
                author = None
                author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                if author_match:
                    author = author_match.group(1)
                    # Extract just the date part
                    date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                
                # Find the start of this review text (everything before this date, but after previous date if exists)
                if i > 0:
                    # Start from the end of previous date match
                    start_pos = date_matches[i-1].end()
                else:
                    # For first date in block, start from beginning of block
                    start_pos = 0
                
                # Extract review text between start_pos and date_match.start()
                review_text_raw = block[start_pos:date_match.start()].strip()
                
                # Clean up review text - remove UI elements
                review_text = review_text_raw
                review_text = re.sub(r'(×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No)', '', review_text, flags=re.I)
                review_text = re.sub(r'More\s+details', '', review_text, flags=re.I)
                review_text = re.sub(r'\d+\s+other.*?found\s+this\s+helpful', '', review_text, flags=re.I)
                review_text = re.sub(r'Helpful', '', review_text, flags=re.I)
                review_text = re.sub(r'\s+', ' ', review_text)  # Normalize whitespace
                review_text = review_text.strip()
                
                # Filter out navigation and summary content
                text_lower = review_text.lower()
                nav_keywords = ['find a doctor', 'menu', 'search', 'sign in', 'healthgrades']
                if any(kw in text_lower for kw in nav_keywords) and len(review_text) > 500:
                    continue
                
                # Exclude summary/statistics
                exclude_patterns = [
                    r'likelihood to recommend',
                    r'\d+\s+ratings?\s*,\s*\d+\s+with',
                    r'leave a review',
                    r'how was your experience',
                ]
                if any(re.search(pattern, review_text, re.I) for pattern in exclude_patterns):
                    continue
                
                # Must have review-like content
                review_indicators = ['doctor', 'dr.', 'patient', 'visit', 'appointment', 
                                     'treatment', 'care', 'experience', 'recommend', 
                                     'good', 'bad', 'office', 'staff', 'time', 'surgery', 
                                     'procedure', 'helped', 'would recommend', 'worst', 'best', 
                                     'veterinarian', 'dismissive', 'rude', 'arrogant', 'terrible',
                                     'seizures', 'neurologist', 'hospital', 'uncle', 'nice', 'fast']
                
                # Valid review: substantial length, contains review indicators, not duplicate
                if (30 < len(review_text) < 5000 and 
                    review_text not in seen_texts and
                    any(indicator in text_lower for indicator in review_indicators)):
                    # Try to find rating for this review by matching to Selenium elements
                    rating = None
                    
                    # Strategy 1: Search HTML source near this review for rating patterns
                    # Look in a wider context around the review in the page source
                    try:
                        # Find the review text in the page source
                        review_start = page_source.find(review_text[:100])
                        if review_start > 0:
                            # Search 500 chars before and after the review for rating patterns
                            search_start = max(0, review_start - 500)
                            search_end = min(len(page_source), review_start + len(review_text) + 500)
                            context_html = page_source[search_start:search_end]
                            
                            # Look for rating in HTML attributes
                            rating_patterns_html = [
                                r'aria-label=["\']([^"\']*?(\d+)\s*(?:out\s*of\s*)?\d*\s*star[^"\']*?)["\']',
                                r'data-rating=["\'](\d+)["\']',
                                r'title=["\']([^"\']*?(\d+)\s*(?:out\s*of\s*)?\d*\s*star[^"\']*?)["\']',
                            ]
                            for pattern in rating_patterns_html:
                                match = re.search(pattern, context_html, re.I)
                                if match:
                                    # Extract number from match
                                    num_match = re.search(r'(\d+)', match.group(0))
                                    if num_match:
                                        try:
                                            rating = int(num_match.group(1))
                                            if 1 <= rating <= 5:
                                                print(f"      ✓ Found rating {rating} in HTML near review: {review_text[:50]}...")
                                                break
                                        except:
                                            pass
                    except:
                        pass
                    
                    # Strategy 2: Match review text to Selenium elements by content overlap
                    if not rating and review_elements_selenium and element_ratings:
                        review_snippet = review_text[:150].strip().lower()
                        for elem_idx, elem in enumerate(review_elements_selenium):
                            try:
                                elem_text = elem.text.lower()
                                if review_snippet and len(review_snippet) > 50:
                                    if review_snippet[:100] in elem_text and elem_idx in element_ratings:
                                        rating = element_ratings[elem_idx]
                                        print(f"      ✓ Matched rating {rating} to review (element {elem_idx+1})")
                                        break
                            except:
                                continue
                    
                    # Strategy 2: Try to match to BeautifulSoup elements
                    if not rating:
                        for elem_soup in review_elements_with_html:
                            elem_text = elem_soup.get_text()
                            if review_text[:100] in elem_text or elem_text[:100] in review_text:
                                rating = extract_rating_from_element(elem_soup)
                                if rating:
                                    break
                    
                    # Strategy 3: Try text pattern matching in the block
                    if not rating:
                        rating_match = re.search(r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star', block[start_pos:date_match.start()], re.I)
                        if rating_match:
                            try:
                                rating = int(rating_match.group(1))
                                if not (1 <= rating <= 5):
                                    rating = None
                            except:
                                pass
                    
                    reviews.append({
                        'text': review_text,
                        'date': date_str,
                        'author': author,
                        'rating': rating
                    })
                    seen_texts.add(review_text)
        
        # If still no reviews found, try alternative extraction from containers
        if not reviews and review_containers:
            for container in review_containers:
                full_text = container.get_text(separator='\n', strip=True)
                # Use same extraction logic as above - find dates and extract reviews
                container_date_pattern = re.compile(
                    r'((?:[A-Z][a-z]+\s+[A-Z][a-z]+\s+–\s+)?'
                    r'(?:[A-Z][a-z]{2,3}\s+\d{1,2},\s+\d{4}|'
                    r'[A-Z][a-z]+\s+\d{1,2},\s+\d{4}))'
                )
                date_matches = list(container_date_pattern.finditer(full_text))
                
                for i, date_match in enumerate(date_matches):
                    date_str = date_match.group(1).strip()
                    author = None
                    author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                    if author_match:
                        author = author_match.group(1)
                        date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                    
                    start_pos = date_matches[i-1].end() if i > 0 else 0
                    review_text_raw = full_text[start_pos:date_match.start()].strip()
                    
                    review_text = review_text_raw
                    review_text = re.sub(r'(Reply\s+Flag|×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No|More\s+details|Helpful|\d+\s+other.*?found\s+this\s+helpful)', '', review_text, flags=re.I)
                    review_text = re.sub(r'\s+', ' ', review_text).strip()
                    
                    text_lower = review_text.lower()
                    review_indicators = ['doctor', 'dr.', 'patient', 'visit', 'appointment', 
                                         'treatment', 'care', 'experience', 'recommend', 
                                         'good', 'bad', 'office', 'staff', 'time', 'surgery', 
                                         'procedure', 'helped', 'would recommend', 'worst', 'best', 
                                         'veterinarian', 'dismissive', 'rude', 'arrogant', 'terrible']
                    
                    if (50 < len(review_text) < 5000 and 
                        review_text not in seen_texts and
                        any(indicator in text_lower for indicator in review_indicators)):
                        # Try to extract rating from container
                        rating = extract_rating_from_element(container)
                        if not rating:
                            # Try text pattern matching
                            rating_match = re.search(r'(\d+)\s*(?:out\s*of\s*)?\d*\s*star', full_text[start_pos:date_match.start()], re.I)
                            if rating_match:
                                try:
                                    rating = int(rating_match.group(1))
                                    if not (1 <= rating <= 5):
                                        rating = None
                                except:
                                    rating = None
                        
                        reviews.append({
                            'text': review_text,
                            'date': date_str,
                            'author': author,
                            'rating': rating
                        })
                        seen_texts.add(review_text)
        
        print(f"      ✓ Extracted {len(reviews)} reviews")
        
    except Exception as e:
        print(f"      ⚠️  Error extracting reviews: {e}")
        import traceback
        traceback.print_exc()
    
    return reviews

def scrape_doctor_reviews(driver, npi, first_name, last_name, url, skip_existing=True):
    """Scrape reviews for a single doctor using provided driver"""
    print(f"\n   📋 Processing: {first_name} {last_name} (NPI: {npi})")
    print(f"      URL: {url}")
    
    # Check if already scraped
    safe_name = f"{npi}_{first_name}_{last_name}".replace(' ', '_')
    md_filename = f"reviews_{safe_name}.md"
    md_filepath = REVIEWS_OUTPUT_DIR / md_filename
    
    if skip_existing and md_filepath.exists():
        print(f"      ⏭️  Already exists, skipping...")
        # Try to load existing reviews JSON
        try:
            with open(md_filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                # Try to extract reviews from existing file
                reviews = []
                # Simple extraction - look for review sections
                review_pattern = r'### Review \d+\n\n(?:.*?\n\n)?(.*?)\n\n---'
                matches = re.findall(review_pattern, content, re.DOTALL)
                for match in matches:
                    text = match.strip()
                    if len(text) > 20:
                        reviews.append({'text': text})
                return md_filename, reviews, md_filepath
        except:
            pass
        return md_filename, [], md_filepath
    
    # Navigate to main profile page first (reviews are on the main page)
    # We'll click "Show more reviews" from there instead of going directly to /comments
    profile_url = url.rstrip('/')
    
    # Validate URL before proceeding
    if not profile_url or not profile_url.startswith('http'):
        print(f"      ❌ Invalid URL: {profile_url}")
        return None, None, None
    
    print(f"      🔗 Profile URL: {profile_url}")
    
    try:
        print(f"      🌐 Navigating to profile page...")
        # Navigate to the main profile page (not /comments directly)
        driver.get(profile_url)
        
        # Wait for navigation to complete
        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        
        # Check the actual URL we're on
        current_url = driver.current_url
        print(f"      ✓ Navigated to: {current_url}")
        
        # Check if we were redirected to homepage
        if (current_url == 'https://www.healthgrades.com/' or 
            current_url == 'https://www.healthgrades.com' or
            current_url.endswith('healthgrades.com/') or
            current_url.endswith('healthgrades.com')):
            print(f"      ❌ ERROR: Redirected to HOMEPAGE!")
            print(f"      Expected: {profile_url}")
            print(f"      Got: {current_url}")
            print(f"      This might indicate:")
            print(f"        1. The URL format is incorrect")
            print(f"        2. Healthgrades is blocking automated access")
            print(f"        3. The page requires authentication")
            return None, None, None
        
        # Verify we're on the correct page - if redirected, try again
        if current_url != profile_url and '/physician/' not in current_url:
            print(f"      ⚠️  Redirected! Expected: {profile_url}")
            print(f"      🔄 Retrying navigation...")
            # Try navigating again
            driver.get(profile_url)
            time.sleep(5)
            current_url = driver.current_url
            print(f"      ✓ After retry, current URL: {current_url}")
            
            # Check again if redirected to homepage
            if (current_url == 'https://www.healthgrades.com/' or 
                current_url == 'https://www.healthgrades.com'):
                print(f"      ❌ Still redirected to homepage after retry!")
                return None, None, None
        
        if '/physician/' not in current_url:
            print(f"      ❌ ERROR: Not on physician profile page! Current URL: {current_url}")
            print(f"      Expected URL: {profile_url}")
            return None, None, None
        
        # Wait for page to fully load (React-based page)
        print(f"      ⏳ Waiting for page content to load...")
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Close popups and modals that might be blocking the page
        print(f"      🚫 Closing popups and modals...")
        
        popups_closed = False
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # First, try pressing Escape key to close any modals (quickest method)
                try:
                    body = driver.find_element(By.TAG_NAME, 'body')
                    body.send_keys(Keys.ESCAPE)
                except:
                    pass
                
                # Close the "Get your personalized doctor match score" popup
                # Try multiple selectors for the close button
                close_selectors = [
                    "//button[@aria-label='Close']",
                    "//button[contains(@class, 'close')]",
                    "//button[contains(@class, 'modal-close')]",
                    "//*[contains(@class, 'close') and contains(@class, 'button')]",
                    "//div[contains(@class, 'modal')]//button[contains(@aria-label, 'Close')]",
                    "//div[contains(@class, 'modal')]//*[contains(@class, 'close')]",
                    "//button[contains(text(), '×')]",
                    "//*[@role='button' and contains(@aria-label, 'close')]",
                    "//div[contains(@class, 'modal')]//button[.//*[contains(@class, 'close')]]",
                ]
                
                for selector in close_selectors:
                    try:
                        close_buttons = driver.find_elements(By.XPATH, selector)
                        for btn in close_buttons:
                            try:
                                if btn.is_displayed() and btn.is_enabled():
                                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                                    driver.execute_script("arguments[0].click();", btn)
                                    print(f"      ✓ Closed popup (attempt {attempt + 1})")
                                    popups_closed = True
                                    break
                            except:
                                continue
                        if popups_closed:
                            break
                    except:
                        continue
                
                # Handle cookie consent banner - click Accept or Decline
                cookie_selectors = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Decline')]",
                    "//button[contains(@class, 'accept')]",
                    "//button[contains(@class, 'cookie')]",
                    "//div[contains(@class, 'cookie')]//button[contains(text(), 'Accept')]",
                    "//div[contains(@class, 'cookie')]//button[contains(text(), 'Decline')]",
                ]
                
                for selector in cookie_selectors:
                    try:
                        cookie_buttons = driver.find_elements(By.XPATH, selector)
                        for btn in cookie_buttons:
                            try:
                                if btn.is_displayed() and btn.is_enabled():
                                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                                    driver.execute_script("arguments[0].click();", btn)
                                    print(f"      ✓ Handled cookie consent")
                                    break
                            except:
                                continue
                    except:
                        continue
                
                # Check if any modals are still visible
                try:
                    modals = driver.find_elements(By.XPATH, "//div[contains(@class, 'modal') and contains(@style, 'display: block')]")
                    if not modals or all(not m.is_displayed() for m in modals):
                        popups_closed = True
                        break
                except:
                    pass
                
                if popups_closed:
                    break
                    
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(f"      ⚠️  Error closing popups (attempt {attempt + 1}/{max_attempts}): {e}")
                else:
                    print(f"      ⚠️  Could not close all popups (continuing anyway): {e}")
        
        # Final check - try Escape one more time
        try:
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except:
            pass
        
        print(f"      ✓ Popup handling complete")
        
        # Scroll down to find reviews section
        print(f"      📜 Scrolling to reviews section...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);") 
        
        # Wait for reviews section to appear
        print(f"      ⏳ Waiting for reviews section to load...")
        try:
            # Try to find review elements or review container
            wait = WebDriverWait(driver, 15)
            # Look for common review indicators
            review_indicators = [
                (By.XPATH, "//h2[contains(text(), 'Reviews')]"),
                (By.XPATH, "//h3[contains(text(), 'Reviews')]"),
                (By.XPATH, "//div[contains(@class, 'review')]"),
                (By.XPATH, "//div[contains(@class, 'comment')]"),
                (By.XPATH, "//section[contains(@class, 'review')]"),
            ]
            found = False
            for by, selector in review_indicators:
                try:
                    wait.until(EC.presence_of_element_located((by, selector)))
                    found = True
                    print(f"      ✓ Found reviews section")
                    break
                except:
                    continue
            if not found:
                print(f"      ⚠️  Reviews section not found, continuing anyway...")
        except Exception as e:
            print(f"      ⚠️  Error waiting for reviews: {e}")
        
        # Verify popups are closed before trying to click "Show more reviews"
        print(f"      🔍 Verifying popups are closed...")
        try:
            # Check if any blocking modals are still visible
            blocking_modals = driver.find_elements(By.XPATH, 
                "//div[contains(@class, 'modal') and @style and contains(@style, 'block')] | " +
                "//div[contains(@class, 'overlay') and @style and contains(@style, 'block')] | " +
                "//div[contains(@class, 'popup') and @style and contains(@style, 'block')]")
            
            visible_modals = [m for m in blocking_modals if m.is_displayed()]
            if visible_modals:
                print(f"      ⚠️  Still {len(visible_modals)} visible modals, trying to close again...")
                # Try Escape again
                driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        except:
            pass
        
        # Click "Show more reviews" button/link until all reviews loaded
        print(f"      🔽 Expanding reviews by clicking 'Show more reviews'...")
        click_show_more_reviews(driver)  # Will click as many times as needed
        
        # Scroll thoroughly to trigger lazy loading of all reviews
        print(f"      📜 Scrolling to load all reviews...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 5
        
        while scroll_attempts < max_scroll_attempts:
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for page height to stabilize (state-based)
            try:
                WebDriverWait(driver, 0.5).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") != last_height or True
                )
            except:
                pass
            
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # No new content loaded, try scrolling up a bit and back down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            last_height = new_height
            scroll_attempts += 1
        
        # Final scroll to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Click all "More details" buttons to expand truncated reviews
        click_more_details_buttons(driver)
        
        # Extract reviews first (while page is loaded)
        reviews = extract_reviews_from_page(driver)
        
        # Get page source and save as markdown
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Convert to markdown format
        md_content = f"# Reviews for Dr. {first_name} {last_name} (NPI: {npi})\n\n"
        md_content += f"**Profile URL:** {profile_url}\n\n"
        md_content += f"**Scraped:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md_content += f"**Total Reviews Found:** {len(reviews)}\n\n"
        md_content += "---\n\n"
        
        # Add extracted reviews section
        if reviews:
            md_content += "## Extracted Reviews\n\n"
            for i, review in enumerate(reviews, 1):
                md_content += f"### Review {i}\n\n"
                if review.get('rating'):
                    md_content += f"**Rating:** {review['rating']} out of 5 stars\n\n"
                if review.get('author'):
                    md_content += f"**Author:** {review['author']}\n\n"
                if review.get('date'):
                    md_content += f"**Date:** {review['date']}\n\n"
                md_content += f"{review['text']}\n\n"
                md_content += "---\n\n"
        else:
            md_content += "## Extracted Reviews\n\n"
            md_content += "*No reviews could be extracted from the page.*\n\n"
            md_content += "---\n\n"
        
        # Add raw HTML content for reference (truncated if too large)
        md_content += "## Raw HTML Content (Reference)\n\n"
        md_content += "*Note: HTML is truncated if larger than 100KB*\n\n"
        md_content += "```html\n"
        # Limit HTML size to ~100KB
        html_preview = page_source[:100000] if len(page_source) > 100000 else page_source
        if len(page_source) > 100000:
            html_preview += "\n\n... (truncated) ..."
        md_content += html_preview
        md_content += "\n```\n"
        
        # Save markdown file (filename already set above)
        
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"      ✅ Saved: {md_filename}")
        
        return md_filename, reviews, md_filepath
        
    except Exception as e:
        print(f"      ❌ Error scraping reviews: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def main(limit=None):
    print("🏥 Starting Healthgrades Reviews Scraper")
    if limit:
        print(f"🧪 TEST MODE: Limiting to {limit} doctors")
    print("=" * 60)
    
    # Read verification results CSV
    doctors = []
    try:
        with open(VERIFICATION_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Apply limit early if specified (for testing) to avoid processing all doctors
            if limit:
                print(f"🧪 Limiting to first {limit} doctors (skipping URL lookup for others)")
            
            for row in reader:
                # Early exit if we've hit our limit
                if limit and len(doctors) >= limit:
                    break
                
                npi = row['npi']
                first_name = row['first_name']
                last_name = row['last_name']
                filename = row['filenames']
                
                # Skip if no filename or "None"
                if not filename or filename == "None" or "None" in filename:
                    continue
                
                # Get URL for this doctor
                print(f"   🔍 Looking up URL for {first_name} {last_name} (NPI: {npi}, filename: {filename})")
                url = get_doctor_url(npi, filename)
                if not url:
                    print(f"   ⚠️  Skipping {first_name} {last_name} (NPI: {npi}): No URL found")
                    continue
                
                print(f"   ✅ Found URL: {url}")
                
                doctors.append({
                    'npi': npi,
                    'first_name': first_name,
                    'last_name': last_name,
                    'filename': filename,
                    'url': url
                })
    except Exception as e:
        print(f"❌ Error reading verification CSV: {e}")
        return
    
    print(f"📊 Found {len(doctors)} doctors with valid URLs")
    
    # Setup single browser session for all doctors (MAJOR OPTIMIZATION)
    print(f"🌐 Setting up browser session...")
    driver = setup_selenium_driver()
    if not driver:
        print("❌ Failed to setup browser. Exiting.")
        return
    
    print(f"✅ Browser ready - reusing session for all {len(doctors)} doctors")
    
    try:
        # Process each doctor using shared browser session
        results = []
        for i, doctor in enumerate(doctors, 1):
            print(f"\n[{i}/{len(doctors)}]")
            
            md_filename, reviews_json, md_filepath = scrape_doctor_reviews(
                driver,  # Pass shared driver
                doctor['npi'],
                doctor['first_name'],
                doctor['last_name'],
                doctor['url']
            )
            
            if md_filename and reviews_json:
                # Create one row per review
                for review_idx, review in enumerate(reviews_json, 1):
                    results.append({
                        'npi': doctor['npi'],
                        'first_name': doctor['first_name'],
                        'last_name': doctor['last_name'],
                        'reviews_md_file': md_filename,
                        'review_index': review_idx,
                        'review_text': review.get('text', ''),
                        'review_author': review.get('author', ''),
                        'review_date': review.get('date', ''),
                        'review_rating': review.get('rating', '')
                    })
            elif md_filename:
                # Doctor processed but no reviews found - still create one row
                results.append({
                    'npi': doctor['npi'],
                    'first_name': doctor['first_name'],
                    'last_name': doctor['last_name'],
                    'reviews_md_file': md_filename,
                    'review_index': 0,
                    'review_text': '',
                    'review_author': '',
                    'review_date': ''
                })
            
            # Be nice to the server - add delay between requests
            if i < len(doctors):
                delay = 3
                print(f"      ⏳ Waiting {delay} seconds before next request...")
                time.sleep(delay)
    
    finally:
        # Always quit the browser when done
        print(f"\n🔚 Closing browser session...")
        driver.quit()
        print(f"✅ Browser closed")
    
    # Save results to CSV
    if results:
        print(f"\n💾 Saving results to {MAPPING_CSV}")
        with open(MAPPING_CSV, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['npi', 'first_name', 'last_name', 'reviews_md_file', 'review_index', 'review_text', 'review_author', 'review_date', 'review_rating']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        total_reviews = sum(1 for r in results if r['review_index'] > 0)
        print(f"✅ Saved {len(results)} review rows ({total_reviews} reviews from {len(set(r['npi'] for r in results))} doctors)")
        print(f"   📁 Reviews saved in: {REVIEWS_OUTPUT_DIR}")
        print(f"   📄 Mapping saved in: {MAPPING_CSV}")
    else:
        print("❌ No results to save")

if __name__ == "__main__":
    import sys
    # Allow limit to be passed as command line argument
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print(f"⚠️  Invalid limit argument: {sys.argv[1]}. Using default (no limit).")
    
    # Run for all doctors if no limit specified
    main(limit=limit)

