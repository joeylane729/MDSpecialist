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
from datetime import datetime
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
    """Extract URL from markdown file by looking in the reviews section only.
    First checks if there are any written reviews. If no written reviews, returns None immediately.
    If written reviews exist, extracts URLs that appear next to 'Post a Response'."""
    try:
        with open(md_filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # FIRST: Check if there are any written reviews
        # Look for patterns indicating written reviews exist
        written_review_patterns = [
            r'\d+\s+with\s+a\s+written\s+review',
            r'\d+\s+written\s+review',
            r'with\s+a\s+written\s+review',
            r'written\s+review',
        ]
        
        has_written_reviews = False
        for pattern in written_review_patterns:
            if re.search(pattern, content, re.I):
                has_written_reviews = True
                break
        
        # If no written reviews found, return None immediately (skip URL extraction)
        if not has_written_reviews:
            return None
        
        # SECOND: Extract URLs that appear next to "Post a Response" (only if written reviews exist)
        # Pattern 1: [×](URL#) Post a Response (most common format)
        pattern1 = r'\[×\]\(https://www\.healthgrades\.com/physician/dr-([a-z0-9-]+)#\)\s*Post\s+a\s+Response'
        matches1 = re.findall(pattern1, content, re.IGNORECASE)
        
        # Pattern 2: URL# followed by Post a Response on same line or nearby
        lines = content.split('\n')
        matches2 = []
        for i, line in enumerate(lines):
            if 'Post a Response' in line:
                # Check this line and adjacent lines for URLs with #
                context_lines = lines[max(0, i-2):min(len(lines), i+3)]
                context = '\n'.join(context_lines)
                url_matches = re.findall(r'https://www\.healthgrades\.com/physician/dr-([a-z0-9-]+)#', context, re.IGNORECASE)
                matches2.extend(url_matches)
        
        # Combine all matches and get unique base URLs
        all_slugs = list(set(matches1 + matches2))
        
        if all_slugs:
            # Count occurrences of each slug (most common is likely the correct one)
            slug_counts = {}
            for slug in all_slugs:
                slug_counts[slug] = slug_counts.get(slug, 0) + 1
            
            # Get the most common slug
            most_common_slug = max(slug_counts.items(), key=lambda x: x[1])[0]
            base_url = f"https://www.healthgrades.com/physician/dr-{most_common_slug}"
            return base_url
        
        # Written reviews exist but no URL found next to "Post a Response" - return None
        return None
            
    except Exception as e:
        print(f"   ⚠️  Error reading md file {md_filepath}: {e}")
    
    return None

def get_doctor_url(npi, filename):
    """Get URL for a doctor by extracting from markdown file"""
    # Extract URL directly from md file
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
    """Setup and return Selenium WebDriver - optimized with hardcoded path"""
    chrome_options = Options()
    # Run in headless mode for production, remove for debugging
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_experimental_option("detach", True)
    chrome_options.page_load_strategy = "eager"
    
    # User agent to avoid detection
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Hardcoded ChromeDriver path (adjust if needed)
    # For Apple Silicon Mac: /opt/homebrew/bin/chromedriver
    # For Intel Mac: /usr/local/bin/chromedriver
    chromedriver_path = "/opt/homebrew/bin/chromedriver"
    
    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print(f"   ✅ ChromeDriver initialized successfully ({chromedriver_path})")
    return driver

def click_show_more_reviews(driver, max_clicks=1000):
    """Click 'Show more reviews' button until all reviews are loaded - optimized with CSS selectors"""
    start_time = time.time()
    print(f"      ⏱️  [TIMING] Starting 'Show more reviews' expansion...")
    clicks = 0
    
    # Keep clicking until no more buttons found
    while clicks < max_clicks:
        try:
            # Find all links once using CSS selector (faster than XPath)
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[data-qa-target='show-more-comments']")
            
            # Filter to only visible, review-related buttons
            button = None
            for link in all_links:
                if not link.is_displayed() or not link.is_enabled():
                    continue
                
                # Verify it's review-related (not specialty/directory link)
                href = link.get_attribute('href') or ''
                if '/directory' in href or '/vascular-neurology' in href or '/search' in href:
                    continue
                
                button = link
                break
            
            if not button:
                # No more buttons found
                break
            
            # Store current URL before clicking
            current_url_before = driver.current_url
            initial_count = len(driver.find_elements(By.CSS_SELECTOR, "div.c-single-comment"))
            
            # Click using JavaScript
            driver.execute_script("arguments[0].click();", button)
            
            # Wait briefly for either: button disappears (all loaded) OR new reviews appear
            # This avoids waiting full timeout when reviews are already loaded
            try:
                WebDriverWait(driver, 1).until(
                    lambda d: (
                        len(d.find_elements(By.CSS_SELECTOR, "a[data-qa-target='show-more-comments']")) == 0
                        or len(d.find_elements(By.CSS_SELECTOR, "div.c-single-comment")) > initial_count
                    )
                )
            except:
                # If timeout, check page ready state (brief wait)
                try:
                    WebDriverWait(driver, 0.5).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except:
                    pass  # Continue anyway - don't wait unnecessarily
            
            # Check if URL changed (navigation occurred)
            current_url_after = driver.current_url
            if current_url_after != current_url_before:
                if '/directory' in current_url_after or '/vascular-neurology' in current_url_after:
                    print(f"      ⚠️  Click navigated to directory page, going back...")
                    driver.back()
                    WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
                    break
            
            clicks += 1
            print(f"      ✓ Clicked 'Show more reviews' ({clicks})")
            
        except Exception as e:
            break
    
    total_duration = time.time() - start_time
    if clicks > 0:
        print(f"      ✓ Expanded reviews with {clicks} clicks")
        print(f"      ⏱️  [TIMING] Total 'Show more reviews' expansion took {total_duration:.2f}s ({clicks} clicks, avg {total_duration/clicks:.2f}s per click)")
    else:
        print(f"      ℹ No 'Show more reviews' button found or already expanded")
        print(f"      ⏱️  [TIMING] 'Show more reviews' check took {total_duration:.2f}s")
    
    return clicks

def click_more_details_buttons(driver):
    """Click all 'More details' buttons to expand truncated review text - optimized with CSS selectors"""
    start_time = time.time()
    print(f"      🔍 Looking for 'More details' buttons...")
    
    # Find all "More details" buttons within review containers using CSS selector (faster)
    buttons = driver.find_elements(By.CSS_SELECTOR, "div.c-single-comment button, div.c-single-comment a")
    
    clicks = 0
    for button in buttons:
        try:
            # Check if button text contains "More details"
            button_text = (button.text or '').strip()
            if 'more details' not in button_text.lower():
                continue
            
            if not button.is_displayed() or not button.is_enabled():
                continue
            
            # Click using JavaScript
            driver.execute_script("arguments[0].click();", button)
            clicks += 1
            
            # Brief wait for content to update
            try:
                WebDriverWait(driver, 0.3).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except:
                pass
            
        except Exception:
            continue
    
    total_duration = time.time() - start_time
    if clicks > 0:
        print(f"      ✓ Clicked {clicks} 'More details' buttons to expand reviews")
        print(f"      ⏱️  [TIMING] 'More details' expansion took {total_duration:.2f}s ({clicks} clicks, avg {total_duration/clicks:.2f}s per click)")
    else:
        print(f"      ℹ️  No 'More details' buttons found (reviews may already be expanded)")
        print(f"      ⏱️  [TIMING] 'More details' check took {total_duration:.2f}s")
    
    return clicks

def extract_rating_from_element(review_elem):
    """Extract star rating from a review element using stable selectors"""
    # Strategy 1: aria-label with "out of 5" (most reliable)
    rating_elem = review_elem.select_one("[aria-label*='out of 5']")
    if rating_elem:
        aria_label = rating_elem.get('aria-label', '')
        match = re.search(r'(\d+)', aria_label)
        if match:
            rating = int(match.group(1))
            if 1 <= rating <= 5:
                return rating
    
    # Strategy 2: data-rating attribute
    rating_elem = review_elem.select_one("[data-rating]")
    if rating_elem:
        try:
            rating = int(rating_elem.get('data-rating', 0))
            if 1 <= rating <= 5:
                return rating
        except:
            pass
    
    return None

def extract_reviews_from_page(driver):
    """Extract review comments from the current page - optimized: parse once, use CSS selectors"""
    start_time = time.time()
    print(f"      ⏱️  [TIMING] Starting review extraction...")
    reviews = []
    
    try:
        # Parse HTML once per page (not multiple times)
        page_source = driver.page_source
        try:
            soup = BeautifulSoup(page_source, 'lxml')  # lxml is faster than html.parser
        except:
            soup = BeautifulSoup(page_source, 'html.parser')  # Fallback to html.parser
        
        # Find all review containers using stable CSS selector (faster than XPath)
        review_containers = soup.select("div.c-single-comment")
        
        if not review_containers:
            print(f"      ⚠️  No reviews found with selector 'div.c-single-comment'")
            extraction_duration = time.time() - start_time
            print(f"      ⏱️  [TIMING] Review extraction took {extraction_duration:.2f}s (0 reviews)")
            return reviews
        
        print(f"      ✓ Found {len(review_containers)} review containers")
        
        # Date pattern for extraction
        date_pattern = re.compile(
            r'((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+)?'
            r'(?:[A-Z][a-z]{2,3}\s+\d{1,2},\s+\d{4}|'
            r'[A-Z][a-z]+\s+\d{1,2},\s+\d{4}))'
        )
        
        seen_texts = set()
        
        # Extract each review using stable selectors
        for review_elem in review_containers:
            try:
                # Extract review text using stable selector
                comment_elem = review_elem.select_one("[data-qa-target='user-comment']")
                if not comment_elem:
                    continue
                
                review_text = comment_elem.get_text(strip=True)
                if len(review_text) < 30:
                    continue
                
                # Clean up review text
                review_text = re.sub(r'(×|Post\s+a\s+Response|Are\s+you.*?\?|Yes|No|Reply\s+Flag)', '', review_text, flags=re.I)
                review_text = re.sub(r'More\s+details', '', review_text, flags=re.I)
                review_text = re.sub(r'\d+\s+other.*?found\s+this\s+helpful', '', review_text, flags=re.I)
                review_text = re.sub(r'Helpful', '', review_text, flags=re.I)
                review_text = re.sub(r'\s+', ' ', review_text).strip()
                
                # Extract date using stable selector
                date_elem = review_elem.select_one("[data-qa-target='comment-date']")
                if not date_elem:
                    continue
                
                date_text = date_elem.get_text()
                date_match = date_pattern.search(date_text)
                if not date_match:
                    continue
                
                date_str = date_match.group(1).strip()
                
                # Extract author if present
                author = None
                author_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?)\s+–\s+', date_str)
                if author_match:
                    author = author_match.group(1)
                    date_str = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)?\s+–\s+', '', date_str)
                
                # Extract rating using stable selector
                rating = extract_rating_from_element(review_elem)
                
                # Validate and add review
                if (30 < len(review_text) < 5000 and 
                    review_text not in seen_texts):
                    reviews.append({
                        'text': review_text,
                        'date': date_str,
                        'author': author,
                        'rating': rating
                    })
                    seen_texts.add(review_text)
                    
            except Exception as e:
                continue  # Skip this review if extraction fails
        
        extraction_duration = time.time() - start_time
        print(f"      ✓ Extracted {len(reviews)} reviews")
        print(f"      ⏱️  [TIMING] Review extraction took {extraction_duration:.2f}s ({len(reviews)} reviews, avg {extraction_duration/len(reviews) if reviews else 0:.3f}s per review)")
        
    except Exception as e:
        # First, try to find review elements using Selenium (more reliable for dynamic content)
        print(f"      🔍 Searching for review elements...")
        
        # Try to find review elements directly with Selenium
        # Look for actual review items, not summary sections
        review_elements_selenium = []
        selectors = [
            # PRIMARY: Use c-single-comment (top-level review container with unique data-comment-id)
            # This is the outer container for each review, avoiding nested duplicates
            "//div[contains(@class, 'c-single-comment') and @data-comment-id]",
            # SECONDARY: Fallback to c-single-comment without requiring data-comment-id
            "//div[contains(@class, 'c-single-comment')]",
            # TERTIARY: Use l-single-comment-container (but prefer c-single-comment)
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
        ]
        
        # Try all selectors and use the one that finds the most elements
        # This handles cases where the primary selector is too specific
        print(f"      🔍 Trying {len(selectors)} selectors...")
        best_match = None
        best_count = 0
        for selector in selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                count = len(elements)
                if count > 0:
                    print(f"      ✓ Found {count} elements with selector: {selector[:50]}...")
                    # Use the selector that finds the most elements (but prefer specific ones if counts are similar)
                    if count > best_count or (count >= best_count and 'l-single-comment-container' in selector):
                        best_match = elements
                        best_count = count
                        # If we found a good match with the primary selector and it has reasonable count, use it
                        if 'l-single-comment-container' in selector and count >= 3:
                            review_elements_selenium = elements
                            print(f"      ✅ Using primary selector (found {count} elements)")
                            break
            except Exception as e:
                print(f"      ⚠️  Error with selector {selector[:50]}...: {e}")
                continue
        
        # If we didn't break early, use the best match
        if not review_elements_selenium and best_match:
            # Filter best_match to only include elements that look like actual review containers
            # Also deduplicate by data-comment-id to avoid matching nested elements
            filtered_elements = []
            seen_comment_ids = set()
            
            for elem in best_match:
                try:
                    # Get unique comment ID if available (for deduplication)
                    comment_id = elem.get_attribute('data-comment-id')
                    if comment_id and comment_id in seen_comment_ids:
                        continue  # Skip duplicate
                    if comment_id:
                        seen_comment_ids.add(comment_id)
                    
                    # Check if this element has review-specific markers
                    has_comment = len(elem.find_elements(By.XPATH, ".//div[@data-qa-target='user-comment']")) > 0
                    has_date = len(elem.find_elements(By.XPATH, ".//div[@data-qa-target='comment-date']")) > 0
                    has_container_class = 'l-single-comment-container' in (elem.get_attribute('class') or '')
                    is_single_comment = 'c-single-comment' in (elem.get_attribute('class') or '')
                    text_length = len(elem.text)
                    
                    # Include if it has review markers or is a known container class
                    # Prefer c-single-comment (top-level) over nested elements
                    if is_single_comment or (has_comment and has_date) or has_container_class or (text_length > 100 and 'review' in (elem.get_attribute('class') or '')):
                        filtered_elements.append(elem)
                except:
                    # If we can't check, include it (better to have false positives than miss reviews)
                    if len(elem.text) > 50:
                        filtered_elements.append(elem)
            
            if filtered_elements:
                review_elements_selenium = filtered_elements
                print(f"      ✅ Using filtered best match (found {len(filtered_elements)}/{best_count} actual review elements)")
            else:
                review_elements_selenium = best_match
                print(f"      ✅ Using best match selector (found {best_count} elements, couldn't filter)")
        
        if not review_elements_selenium:
            print(f"      ⚠️  No review elements found with any selector")
        
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
        if review_elements_selenium:
            print(f"      🔍 Extracting reviews from {len(review_elements_selenium)} Selenium elements (with ratings)...")
            print(f"      📊 Elements with ratings: {len(element_ratings)}/{len(review_elements_selenium)}")
            selenium_reviews_found = 0
            for idx, elem in enumerate(review_elements_selenium):
                try:
                    elem_text = elem.text
                    # Skip if this looks like a header/navigation element
                    if len(elem_text) < 50 or 'Your trust is our top concern' in elem_text:
                        print(f"      ⚠️  Skipping element {idx+1}: too short ({len(elem_text)} chars) or header text")
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
                    
                    # Debug: print what we found for first few elements
                    if idx < 5:
                        print(f"      🔍 Element {idx+1}: review_text={bool(review_text)}, date_str={bool(date_str)}, rating={element_ratings.get(idx, 'N/A')}")
                        if not review_text and not date_str:
                            print(f"         Preview: {elem_text[:150]}...")
                    
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
                        
                        # Debug validation for first few elements
                        if idx < 5:
                            text_len = len(review_text)
                            is_duplicate = review_text in seen_texts
                            has_indicator = any(indicator in text_lower for indicator in review_indicators)
                            print(f"      🔍 Element {idx+1} validation: len={text_len}, duplicate={is_duplicate}, has_indicator={has_indicator}")
                            if not (30 < text_len < 5000):
                                print(f"         ❌ Length check failed: {text_len} not in (30, 5000)")
                            if is_duplicate:
                                print(f"         ❌ Duplicate check failed")
                            if not has_indicator:
                                print(f"         ❌ Indicator check failed, preview: {review_text[:100]}...")
                        
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
                        elif idx < 5:
                            print(f"      ⚠️  Element {idx+1} failed validation, not extracted")
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
        
        extraction_duration = time.time() - start_time
        print(f"      ✓ Extracted {len(reviews)} reviews")
        print(f"      ⏱️  [TIMING] Review extraction took {extraction_duration:.2f}s ({len(reviews)} reviews, avg {extraction_duration/len(reviews) if reviews else 0:.3f}s per review)")
        
    except Exception as e:
        extraction_duration = time.time() - start_time
        print(f"      ⚠️  Error extracting reviews: {e}")
        print(f"      ⏱️  [TIMING] Review extraction failed after {extraction_duration:.2f}s")
        import traceback
        traceback.print_exc()
    
    return reviews

def scrape_doctor_reviews(driver, npi, first_name, last_name, url, skip_existing=True):
    """Scrape reviews for a single doctor using provided driver"""
    doctor_start_time = time.time()
    print(f"\n   📋 Processing: {first_name} {last_name} (NPI: {npi})")
    print(f"      URL: {url}")
    print(f"      ⏱️  [TIMING] Starting doctor processing at {datetime.now().strftime('%H:%M:%S')}")
    
    # Check if already scraped
    safe_name = f"{npi}_{first_name}_{last_name}".replace(' ', '_')
    md_filename = f"reviews_{safe_name}.md"
    md_filepath = REVIEWS_OUTPUT_DIR / md_filename
    
    if skip_existing and md_filepath.exists():
        skip_duration = time.time() - doctor_start_time
        print(f"      ⏭️  Already exists, skipping...")
        print(f"      ⏱️  [TIMING] Skip check took {skip_duration:.2f}s")
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
        nav_start = time.time()
        print(f"      🌐 Navigating to profile page...")
        # Navigate to the main profile page (not /comments directly)
        driver.get(profile_url)
        
        # Wait for navigation to complete
        wait = WebDriverWait(driver, 20)
        wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
        nav_duration = time.time() - nav_start
        print(f"      ⏱️  [TIMING] Navigation took {nav_duration:.2f}s")
        
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
            # Wait for page to load
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return document.readyState') == 'complete')
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
        load_start = time.time()
        print(f"      ⏳ Waiting for page content to load...")
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        load_duration = time.time() - load_start
        print(f"      ⏱️  [TIMING] Page load wait took {load_duration:.2f}s")
        
        # Close popups and modals that might be blocking the page
        popup_start = time.time()
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
        
        popup_duration = time.time() - popup_start
        print(f"      ✓ Popup handling complete")
        print(f"      ⏱️  [TIMING] Popup handling took {popup_duration:.2f}s")
        
        # Scroll down to find reviews section
        scroll_start = time.time()
        print(f"      📜 Scrolling to reviews section...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);") 
        
        # Wait for reviews section to appear
        review_wait_start = time.time()
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
        review_wait_duration = time.time() - review_wait_start
        print(f"      ⏱️  [TIMING] Reviews section wait took {review_wait_duration:.2f}s")
        
        # Verify popups are closed before trying to click "Show more reviews"
        verify_start = time.time()
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
        verify_duration = time.time() - verify_start
        print(f"      ⏱️  [TIMING] Popup verification took {verify_duration:.2f}s")
        
        # Click "Show more reviews" button/link until all reviews loaded
        print(f"      🔽 Expanding reviews by clicking 'Show more reviews'...")
        click_show_more_reviews(driver)  # Will click as many times as needed
        
        # Scroll thoroughly to trigger lazy loading of all reviews
        scroll_all_start = time.time()
        print(f"      📜 Scrolling to load all reviews...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scroll_attempts = 10  # Increased attempts
        
        while scroll_attempts < max_scroll_attempts:
            # Scroll down incrementally to trigger lazy loading
            current_scroll = driver.execute_script("return window.pageYOffset || document.documentElement.scrollTop")
            scroll_step = 500
            max_scroll = driver.execute_script("return document.body.scrollHeight")
            
            # Scroll in smaller increments
            for step in range(0, max_scroll, scroll_step):
                driver.execute_script(f"window.scrollTo(0, {step});")
                # Wait for lazy loading to trigger
                try:
                    WebDriverWait(driver, 0.5).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except:
                    pass  # Continue if timeout
            
            # Final scroll to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Wait for any final lazy loading
            try:
                WebDriverWait(driver, 2).until(
                    lambda d: d.execute_script('return document.readyState') == 'complete'
                )
            except:
                pass
            
            # Wait for page height to stabilize
            try:
                WebDriverWait(driver, 1).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") != last_height or True
                )
            except:
                pass
            
            # Calculate new scroll height and compare with last scroll height
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # No new content loaded, try scrolling up a bit and back down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight - 1000);")
                try:
                    WebDriverWait(driver, 0.5).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except:
                    pass
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                try:
                    WebDriverWait(driver, 1).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                except:
                    pass
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
            last_height = new_height
            scroll_attempts += 1
        
        # Final scroll to bottom and wait
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # Final wait for lazy loading
        try:
            WebDriverWait(driver, 3).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except:
            pass
        scroll_all_duration = time.time() - scroll_all_start
        print(f"      ⏱️  [TIMING] Full page scrolling took {scroll_all_duration:.2f}s ({scroll_attempts} attempts)")
        
        # Click all "More details" buttons to expand truncated reviews
        click_more_details_buttons(driver)
        
        # DEBUG: Count review elements before extraction
        print(f"      🔍 DEBUG: Counting review elements before extraction...")
        debug_selectors = [
            "//div[contains(@class, 'l-single-comment-container')]",
            "//div[contains(@class, 'review')]",
            "//div[contains(@class, 'comment')]",
        ]
        for selector in debug_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                print(f"         Found {len(elements)} elements with: {selector[:60]}...")
            except:
                pass
        
        # Extract reviews first (while page is loaded)
        reviews = extract_reviews_from_page(driver)
        
        # Get page source and save as markdown
        save_start = time.time()
        print(f"      💾 Saving results to markdown file...")
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
        
        save_duration = time.time() - save_start
        doctor_total_duration = time.time() - doctor_start_time
        print(f"      ✅ Saved: {md_filename}")
        print(f"      ⏱️  [TIMING] File save took {save_duration:.2f}s")
        print(f"      ⏱️  [TIMING] Total doctor processing time: {doctor_total_duration:.2f}s ({doctor_total_duration/60:.1f} minutes)")
        
        return md_filename, reviews, md_filepath
        
    except Exception as e:
        doctor_total_duration = time.time() - doctor_start_time
        print(f"      ❌ Error scraping reviews: {e}")
        print(f"      ⏱️  [TIMING] Doctor processing failed after {doctor_total_duration:.2f}s")
        import traceback
        traceback.print_exc()
        return None, None, None

def main(limit=None):
    main_start_time = time.time()
    print("🏥 Starting Healthgrades Reviews Scraper")
    if limit:
        print(f"🧪 TEST MODE: Limiting to {limit} doctors")
    print("=" * 60)
    print(f"⏱️  [TIMING] Script started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Read verification results CSV
    doctors = []
    try:
        with open(VERIFICATION_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Apply limit early if specified (for testing) to avoid processing all doctors
            if limit:
                print(f"🧪 Limiting to first {limit} doctors (skipping URL lookup for others)")
            
            for row in reader:
                # Early exit if we've hit our limit (only count doctors with valid URLs)
                if limit and len(doctors) >= limit:
                    print(f"   ✅ Reached limit of {limit} doctors with valid URLs, stopping URL lookup")
                    break
                
                npi = row['npi']
                first_name = row['first_name']
                last_name = row['last_name']
                filename = row['filenames']
                
                # Skip if no filename or "None"
                if not filename or filename == "None" or "None" in filename:
                    continue
                
                # Get URL for this doctor
                url_lookup_start = time.time()
                print(f"   🔍 Looking up URL for {first_name} {last_name} (NPI: {npi}, filename: {filename})")
                url = get_doctor_url(npi, filename)
                url_lookup_duration = time.time() - url_lookup_start
                if not url:
                    print(f"   ⚠️  Skipping {first_name} {last_name} (NPI: {npi}): No URL found")
                    print(f"   ⏱️  [TIMING] URL lookup took {url_lookup_duration:.2f}s")
                    continue
                
                print(f"   ✅ Found URL: {url}")
                print(f"   ⏱️  [TIMING] URL lookup took {url_lookup_duration:.2f}s")
                
                doctors.append({
                    'npi': npi,
                    'first_name': first_name,
                    'last_name': last_name,
                    'filename': filename,
                    'url': url
                })
                
                # Check limit again after adding (in case we just hit the limit)
                if limit and len(doctors) >= limit:
                    print(f"   ✅ Reached limit of {limit} doctors with valid URLs, stopping URL lookup")
                    break
    except Exception as e:
        print(f"❌ Error reading verification CSV: {e}")
        return
    
    print(f"📊 Found {len(doctors)} doctors with valid URLs")
    
    # Setup single browser session for all doctors (MAJOR OPTIMIZATION)
    browser_setup_start = time.time()
    print(f"🌐 Setting up browser session...")
    driver = setup_selenium_driver()
    browser_setup_duration = time.time() - browser_setup_start
    if not driver:
        print("❌ Failed to setup browser. Exiting.")
        return
    
    print(f"✅ Browser ready - reusing session for all {len(doctors)} doctors")
    print(f"⏱️  [TIMING] Browser setup took {browser_setup_duration:.2f}s")
    
    try:
        # Process each doctor using shared browser session
        results = []
        for i, doctor in enumerate(doctors, 1):
            doctor_iter_start = time.time()
            print(f"\n[{i}/{len(doctors)}]")
            print(f"⏱️  [TIMING] Starting doctor {i} at {datetime.now().strftime('%H:%M:%S')}")
            
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
            
            doctor_iter_duration = time.time() - doctor_iter_start
            print(f"⏱️  [TIMING] Doctor {i} iteration total: {doctor_iter_duration:.2f}s")
    
    finally:
        # Always quit the browser when done
        browser_close_start = time.time()
        print(f"\n🔚 Closing browser session...")
        driver.quit()
        browser_close_duration = time.time() - browser_close_start
        print(f"✅ Browser closed")
        print(f"⏱️  [TIMING] Browser close took {browser_close_duration:.2f}s")
    
    # Save results to CSV
    if results:
        csv_save_start = time.time()
        print(f"\n💾 Saving results to {MAPPING_CSV}")
        with open(MAPPING_CSV, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['npi', 'first_name', 'last_name', 'reviews_md_file', 'review_index', 'review_text', 'review_author', 'review_date', 'review_rating']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        total_reviews = sum(1 for r in results if r['review_index'] > 0)
        csv_save_duration = time.time() - csv_save_start
        main_total_duration = time.time() - main_start_time
        print(f"✅ Saved {len(results)} review rows ({total_reviews} reviews from {len(set(r['npi'] for r in results))} doctors)")
        print(f"   📁 Reviews saved in: {REVIEWS_OUTPUT_DIR}")
        print(f"   📄 Mapping saved in: {MAPPING_CSV}")
        print(f"⏱️  [TIMING] CSV save took {csv_save_duration:.2f}s")
        print(f"⏱️  [TIMING] Total script execution time: {main_total_duration:.2f}s ({main_total_duration/60:.1f} minutes)")
        print(f"⏱️  [TIMING] Script completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        main_total_duration = time.time() - main_start_time
        print("❌ No results to save")
        print(f"⏱️  [TIMING] Total script execution time: {main_total_duration:.2f}s ({main_total_duration/60:.1f} minutes)")

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

