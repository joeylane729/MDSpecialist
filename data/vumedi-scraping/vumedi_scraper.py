#!/usr/bin/env python3
"""
VuMedi Scraper

This script scrapes content from VuMedi's cerebrovascular section.
Handles login authentication and extracts relevant medical content.

Requirements:
- Chrome/Chromium browser
- ChromeDriver (automatically managed by webdriver-manager)
- Selenium package

Usage:
    python vumedi_scraper.py
"""

import time
import random
import csv
import json
import logging
import sys
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('vumedi_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class VuMediScraper:
    """
    VuMedi scraper with login authentication and content extraction
    """
    
    def __init__(self, headless: bool = False):
        """
        Initialize the VuMedi scraper
        
        Args:
            headless: Whether to run browser in headless mode (default: False for login)
        """
        self.base_url = "https://www.vumedi.com"
        self.target_url = "https://www.vumedi.com/video/browse/"  # Main video browse page
        self.content = []
        self.driver = None
        self.headless = headless
        
        # User agents to rotate through
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ]
        
        self.setup_driver()
    
    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options"""
        try:
            chrome_options = Options()
            
            # Add user agent
            chrome_options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
            
            # Don't run headless for login (user needs to see the page)
            if self.headless:
                chrome_options.add_argument('--headless')
                logging.warning("Running in headless mode - manual login not possible!")
            
            # Disable notifications and popups
            chrome_options.add_argument('--disable-notifications')
            chrome_options.add_argument('--disable-popup-blocking')
            
            # Disable automation detection
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set up the service and driver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set window size
            self.driver.set_window_size(1920, 1080)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logging.info("Chrome WebDriver initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def interactive_login(self) -> bool:
        """Interactive login process - user manually logs in through browser"""
        logging.info("Starting interactive login process...")
        
        try:
            # Navigate to VuMedi
            logging.info("Navigating to VuMedi...")
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Skip looking for login buttons - go straight to manual login prompt
            print("\n" + "=" * 60)
            print("🔐 MANUAL LOGIN REQUIRED")
            print("=" * 60)
            print("Please complete the following steps in the browser window:")
            print("1. Enter your VuMedi username/email")
            print("2. Enter your password")
            print("3. Click the login/sign-in button")
            print("4. Complete any 2FA if required")
            print("5. Wait for the page to fully load")
            print()
            print("Once you're successfully logged in, press ENTER here to continue...")
            print("=" * 60)
            
            # Wait for user to press Enter
            input()
            
            # Check if login was successful by looking at the current URL
            time.sleep(2)
            current_url = self.driver.current_url
            
            if 'login' in current_url.lower() or 'signin' in current_url.lower():
                logging.warning("Still on login page - login may not have been completed")
                return False
            
            logging.info("Login appears successful!")
            return True
            
        except Exception as e:
            logging.error(f"Error during interactive login: {e}")
            return False
    
    def navigate_to_target_page(self) -> bool:
        """Navigate to the cerebrovascular section"""
        try:
            logging.info(f"Navigating to target page: {self.target_url}")
            self.driver.get(self.target_url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Check if we're redirected to login (login might have expired)
            if 'login' in self.driver.current_url.lower():
                logging.warning("Redirected to login page - authentication may have failed")
                return False
            
            logging.info("Successfully navigated to cerebrovascular section")
            return True
            
        except Exception as e:
            logging.error(f"Error navigating to target page: {e}")
            return False
    
    def analyze_page_structure(self):
        """Analyze the page structure to understand what content is available"""
        logging.info("Analyzing page structure...")
        
        try:
            # Get page title
            title = self.driver.title
            logging.info(f"Page title: {title}")
            
            # Look for common content containers
            content_selectors = [
                'article', '.article', '[class*="article"]',
                '.content', '[class*="content"]',
                '.post', '[class*="post"]',
                '.video', '[class*="video"]',
                '.card', '[class*="card"]',
                '.item', '[class*="item"]',
                'h1', 'h2', 'h3', 'h4'
            ]
            
            for selector in content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logging.info(f"Found {len(elements)} elements with selector: {selector}")
                        
                        # Show sample content from first few elements
                        for i, elem in enumerate(elements[:3]):
                            text = elem.text.strip()[:100]
                            if text:
                                logging.info(f"  Sample {i+1}: {text}...")
                                
                except Exception:
                    continue
            
            # Look for pagination or load more buttons
            pagination_selectors = [
                '.pagination', '[class*="pagination"]',
                '.load-more', '[class*="load-more"]',
                '.next', '[class*="next"]',
                'button[class*="load"]',
                'a[class*="more"]'
            ]
            
            for selector in pagination_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logging.info(f"Found pagination/load-more elements: {selector}")
                except Exception:
                    continue
                    
        except Exception as e:
            logging.error(f"Error analyzing page structure: {e}")
    
    # Note: extract_content method removed - use extract_content_with_pagination instead
    
    def extract_single_item(self, element, item_number: int) -> Optional[Dict]:
        """Extract metadata from a single video item"""
        try:
            # Extract video title
            title = None
            try:
                title_elem = element.find_element(By.CSS_SELECTOR, '.video-item__title a')
                title = title_elem.text.strip()
                if not title:
                    # Fallback to just the h2 text
                    title_elem = element.find_element(By.CSS_SELECTOR, '.video-item__title')
                    title = title_elem.text.strip()
            except NoSuchElementException:
                logging.warning(f"Could not find title for video {item_number}")
                return None
            
            # Extract video link
            link = None
            try:
                link_elem = element.find_element(By.CSS_SELECTOR, '.video-item__title a')
                link = link_elem.get_attribute('href')
                if link and not link.startswith('http'):
                    link = self.base_url + link
            except NoSuchElementException:
                pass
            
            # Extract author/speaker
            author = None
            try:
                author_elem = element.find_element(By.CSS_SELECTOR, '.video-item__author a')
                author = author_elem.text.strip()
            except NoSuchElementException:
                pass
            
            # Extract publication date
            date = None
            try:
                date_elem = element.find_element(By.CSS_SELECTOR, '.video-item__created_date')
                date = date_elem.text.strip()
                # Clean up the date text (remove icon text)
                if date:
                    date = date.replace('August 14, 2025', '').strip()
            except NoSuchElementException:
                pass
            
            # Extract view count
            views = None
            try:
                views_elem = element.find_element(By.CSS_SELECTOR, '.video-item__number_of_views')
                views = views_elem.text.strip()
                # Clean up the views text (remove icon text)
                if views:
                    views = views.replace('4 views', '').strip()
            except NoSuchElementException:
                pass
            
            # Extract video duration
            duration = None
            try:
                duration_elem = element.find_element(By.CSS_SELECTOR, '.video-duration')
                duration = duration_elem.text.strip()
            except NoSuchElementException:
                pass
            
            # Extract thumbnail image URL
            thumbnail = None
            try:
                img_elem = element.find_element(By.CSS_SELECTOR, '.video-item__img')
                thumbnail = img_elem.get_attribute('src')
                if thumbnail and not thumbnail.startswith('http'):
                    thumbnail = 'https:' + thumbnail
            except NoSuchElementException:
                pass
            
            # Extract featuring information (who is featured in the video)
            featuring = None
            try:
                # Look for the div that contains "FEATURING" text
                desc_elements = element.find_elements(By.CSS_SELECTOR, '.video-item__desc')
                for desc_elem in desc_elements:
                    desc_text = desc_elem.text.strip()
                    if 'FEATURING' in desc_text:
                        # Extract the person's name after "FEATURING"
                        featuring_text = desc_text.replace('FEATURING', '').strip()
                        if featuring_text:
                            featuring = featuring_text
                            break
                        
                        # If no text after FEATURING, try to get the link text
                        try:
                            featuring_link = desc_elem.find_element(By.CSS_SELECTOR, 'a')
                            if featuring_link:
                                featuring = featuring_link.text.strip()
                                break
                        except NoSuchElementException:
                            pass
                        
                        # If still no text, try to get any text content in the div
                        if not featuring and desc_text:
                            # Remove "FEATURING" and clean up
                            clean_text = desc_text.replace('FEATURING', '').strip()
                            if clean_text:
                                featuring = clean_text
                                break
            except Exception as e:
                logging.debug(f"Error extracting featuring info: {e}")
                pass
            
            return {
                'title': title,
                'author': author,
                'date': date,
                'views': views,
                'duration': duration,
                'link': link,
                'thumbnail': thumbnail,
                'featuring': featuring,
                'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logging.warning(f"Error extracting video {item_number}: {e}")
            return None
    
    def save_to_csv(self, filename: str = "vumedi_content.csv"):
        """Save content to CSV file"""
        if not self.content:
            logging.warning("No content to save")
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['title', 'author', 'date', 'views', 'duration', 'link', 'thumbnail', 'featuring', 'specialty', 'specialty_url', 'page_number', 'source', 'scraped_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for item in self.content:
                    writer.writerow(item)
            
            logging.info(f"Saved {len(self.content)} items to {filename}")
        except Exception as e:
            logging.error(f"Error saving to CSV: {e}")
    
    def save_to_json(self, filename: str = "vumedi_content.json"):
        """Save content to JSON file"""
        if not self.content:
            logging.warning("No content to save")
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as jsonfile:
                json.dump(self.content, jsonfile, indent=2, ensure_ascii=False)
            
            logging.info(f"Saved {len(self.content)} items to {filename}")
        except Exception as e:
            logging.error(f"Error saving to JSON: {e}")
    
    def print_summary(self):
        """Print a summary of the scraped content"""
        if not self.content:
            print("No content was scraped.")
            return
        
        print(f"\n=== VUMEDI VIDEO METADATA SUMMARY ===")
        print(f"Total videos scraped: {len(self.content)}")
        print(f"First 5 videos:")
        
        for i, item in enumerate(self.content[:5]):
            print(f"  {i+1}. {item['title']}")
            if item['specialty']:
                print(f"     Specialty: {item['specialty']}")
            if item['page_number']:
                print(f"     Page: {item['page_number']}")
            if item['author']:
                print(f"     Author: {item['author']}")
            if item['featuring']:
                print(f"     Featuring: {item['featuring']}")
            if item['date']:
                print(f"     Date: {item['date']}")
            if item['duration']:
                print(f"     Duration: {item['duration']}")
            if item['views']:
                print(f"     Views: {item['views']}")
            if item['link']:
                print(f"     Link: {item['link']}")
            print()
    
    def close(self):
        """Close the browser and clean up"""
        if self.driver:
            self.driver.quit()
            logging.info("Browser closed")

    def get_total_pages(self) -> int:
        """Get the total number of pages available"""
        try:
            # Look for pagination elements with multiple strategies
            page_numbers = []
            
            # Strategy 1: Look for all page links
            try:
                page_links = self.driver.find_elements(By.CSS_SELECTOR, '.pagination a[href*="page="]')
                for elem in page_links:
                    href = elem.get_attribute('href')
                    if href and 'page=' in href:
                        # Extract page number from href
                        page_num = href.split('page=')[-1].split('&')[0]
                        if page_num.isdigit():
                            page_numbers.append(int(page_num))
            except Exception as e:
                logging.warning(f"Strategy 1 failed: {e}")
            
            # Strategy 2: Look for page numbers in the text content
            try:
                page_elements = self.driver.find_elements(By.CSS_SELECTOR, '.pagination .page-item')
                for elem in page_elements:
                    text = elem.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
            except Exception as e:
                logging.warning(f"Strategy 2 failed: {e}")
            
            # Strategy 3: Look for any elements with page numbers in href attributes
            try:
                all_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="page="]')
                for elem in all_links:
                    href = elem.get_attribute('href')
                    if href and 'page=' in href:
                        page_num = href.split('page=')[-1].split('&')[0]
                        if page_num.isdigit():
                            page_numbers.append(int(page_num))
            except Exception as e:
                logging.warning(f"Strategy 3 failed: {e}")
            
            if page_numbers:
                total_pages = max(page_numbers)
                logging.info(f"Found pagination with {total_pages} total pages")
                print(f"🔍 Detected {total_pages} total pages available")
                return total_pages
            else:
                logging.warning("Could not determine total pages, assuming single page")
                print("⚠️  Could not detect total pages, assuming single page")
                return 1
                
        except Exception as e:
            logging.error(f"Error getting total pages: {e}")
            print(f"❌ Error detecting total pages: {e}")
            return 1
    
    def navigate_to_page(self, page_number: int, current_section_url: str = None) -> bool:
        """Navigate to a specific page number"""
        max_retries = 3
        retry_count = 0
        
        # Use current section URL if provided, otherwise fall back to target_url
        base_url = current_section_url if current_section_url else self.target_url
        
        while retry_count < max_retries:
            try:
                if page_number == 1:
                    # For page 1, just refresh the current URL
                    self.driver.get(base_url)
                else:
                    # For other pages, append page parameter
                    page_url = f"{base_url}?page={page_number}"
                    self.driver.get(page_url)
                
                # Wait for page to load
                time.sleep(3)
                
                # Wait for content to be visible
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                    )
                except TimeoutException:
                    # If timeout, check if we're on a valid page
                    if 'page not found' in self.driver.title.lower() or '404' in self.driver.current_url:
                        logging.warning(f"Page {page_number} appears to not exist (404)")
                        return False
                    # Otherwise, retry
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.warning(f"Timeout waiting for content on page {page_number}, retrying... (attempt {retry_count})")
                        time.sleep(2)
                        continue
                    else:
                        logging.error(f"Failed to load content on page {page_number} after {max_retries} attempts")
                        return False
                
                logging.info(f"Successfully navigated to page {page_number}")
                return True
                
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    logging.warning(f"Error navigating to page {page_number}, retrying... (attempt {retry_count}): {e}")
                    time.sleep(2)
                    continue
                else:
                    logging.error(f"Error navigating to page {page_number} after {max_retries} attempts: {e}")
                    return False
        
        return False

    def extract_content_with_pagination(self, max_items: int = 1000, current_section_url: str = None) -> List[Dict]:
        """
        Extract content from all available pages
        
        Args:
            max_items: Maximum number of items to extract (0 for unlimited)
            current_section_url: URL of the current section being scraped
            
        Returns:
            List of dictionaries containing extracted content from all pages
        """
        logging.info(f"Starting content extraction with pagination (max {max_items if max_items > 0 else 'unlimited'} items)...")
        
        try:
            # First analyze the page to understand its structure
            self.analyze_page_structure()
            
            # Get total number of pages
            total_pages = self.get_total_pages()
            logging.info(f"Total pages to scrape: {total_pages}")
            
            if total_pages == 1:
                logging.info("Single page detected, using single page extraction")
                return self.extract_content_from_current_page()
            
            all_content = []
            current_page = 1
            
            print(f"\n🔄 Starting pagination: {total_pages} pages to scrape")
            print("=" * 50)
            
            while current_page <= total_pages and (max_items == 0 or len(all_content) < max_items):
                progress_percent = (current_page / total_pages) * 100
                print(f"📄 Page {current_page}/{total_pages} ({progress_percent:.1f}%) - Items found so far: {len(all_content)}")
                logging.info(f"Scraping page {current_page}/{total_pages}...")
                
                # Navigate to the current page
                if not self.navigate_to_page(current_page, current_section_url):
                    logging.error(f"Failed to navigate to page {current_page}")
                    print(f"❌ Failed to navigate to page {current_page}, skipping...")
                    current_page += 1
                    continue
                
                # Extract content from current page
                page_content = self.extract_content_from_current_page()
                
                if page_content:
                    all_content.extend(page_content)
                    print(f"✅ Page {current_page}: Found {len(page_content)} items. Total: {len(all_content)}")
                    logging.info(f"Page {current_page}: Found {len(page_content)} items. Total so far: {len(all_content)}")
                else:
                    print(f"⚠️  Page {current_page}: No content found")
                    logging.warning(f"Page {current_page}: No content found")
                
                # Check if we've reached the item limit
                if max_items > 0 and len(all_content) >= max_items:
                    print(f"🎯 Reached item limit ({max_items}), stopping pagination")
                    logging.info(f"Reached item limit ({max_items}), stopping pagination")
                    break
                
                current_page += 1
                
                # Small delay between pages to be respectful
                if current_page <= total_pages:
                    print("⏳ Waiting 2 seconds before next page...")
                    time.sleep(2)
            
            self.content = all_content
            print(f"\n🎉 Pagination completed! Total items extracted: {len(all_content)}")
            logging.info(f"Pagination completed. Total items extracted: {len(all_content)}")
            return all_content
            
        except Exception as e:
            logging.error(f"Error during paginated content extraction: {e}")
            return []
    
    def extract_content_from_current_page(self) -> List[Dict]:
        """Extract content from the current page only"""
        try:
            # VuMedi uses specific video-item structure
            content_selectors = [
                '.video-item',  # Main video container
                '[class*="video-item"]'  # Alternative selector
            ]
            
            content_elements = []
            for selector in content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        # Filter elements that have meaningful content
                        meaningful_elements = [elem for elem in elements if elem.text.strip() and len(elem.text.strip()) > 20]
                        if meaningful_elements:
                            content_elements = meaningful_elements
                            logging.info(f"Found {len(content_elements)} content items using selector: {selector}")
                            break
                except Exception:
                    continue
            
            if not content_elements:
                logging.warning("No content elements found with standard selectors, trying fallback...")
                # Fallback: look for any elements with text content
                all_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div, article, section')
                content_elements = [elem for elem in all_elements if elem.text.strip() and len(elem.text.strip()) > 50]
                content_elements = content_elements[:20]  # Limit to first 20 for fallback
                logging.info(f"Fallback found {len(content_elements)} elements with content")
            
            # Extract information from each content element
            extracted_items = []
            for i, element in enumerate(content_elements):
                try:
                    item_data = self.extract_single_item(element, i + 1)
                    if item_data:
                        extracted_items.append(item_data)
                        
                except Exception as e:
                    logging.warning(f"Error extracting item {i+1}: {e}")
                    continue
                
                # Small delay between extractions
                time.sleep(0.2)
            
            return extracted_items
            
        except Exception as e:
            logging.error(f"Error during page content extraction: {e}")
            return []

    def estimate_total_videos(self) -> int:
        """Estimate total number of videos based on first page content"""
        try:
            # Get content from first page to estimate
            first_page_content = self.extract_content_from_current_page()
            if first_page_content:
                # Assume each page has similar number of videos
                videos_per_page = len(first_page_content)
                total_pages = self.get_total_pages()
                estimated_total = videos_per_page * total_pages
                logging.info(f"Estimated total videos: {estimated_total} ({videos_per_page} per page × {total_pages} pages)")
                return estimated_total
            return 0
        except Exception as e:
            logging.error(f"Error estimating total videos: {e}")
            return 0

    def scrape_all_sections(self, pages_per_section: int = 3) -> List[Dict]:
        """
        Scrape multiple medical sections, getting specified pages from each
        
        Args:
            pages_per_section: Number of pages to scrape from each section
            
        Returns:
            List of all extracted content from all sections
        """
        all_content = []
        total_sections = len(self.medical_sections)
        
        print(f"\n🏥 Starting multi-section scrape: {total_sections} medical sections")
        if pages_per_section == 0:
            print(f"📄 Pages per section: ALL AVAILABLE PAGES")
        else:
            print(f"📄 Pages per section: {pages_per_section}")
        print("=" * 60)
        
        completed_sections = 0
        total_videos_so_far = 0
        
        for section_idx, section in enumerate(self.medical_sections, 1):
            print(f"\n🔬 Section {section_idx}/{total_sections}: {section['name']}")
            print(f"📍 URL: {self.base_url}{section['url']}")
            print("-" * 40)
            
            try:
                # Navigate to this section
                section_url = self.base_url + section['url']
                print(f"🌐 Navigating to: {section_url}")
                self.driver.get(section_url)
                time.sleep(3)
                
                # Verify we're on the right section
                current_url = self.driver.current_url
                print(f"📍 Current URL: {current_url}")
                
                # Wait for content to load
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                    )
                except TimeoutException:
                    print(f"⚠️  No video content found in {section['name']}, skipping...")
                    continue
                
                # Get total pages for this section
                total_pages = self.get_total_pages()
                print(f"📊 Total pages available: {total_pages}")
                
                # Calculate how many pages to scrape (don't exceed available pages)
                if pages_per_section == 0:
                    # Scrape ALL pages
                    pages_to_scrape = total_pages
                    print(f"🎯 Scraping ALL {total_pages} pages from {section['name']}")
                else:
                    # Scrape limited pages
                    pages_to_scrape = min(pages_per_section, total_pages)
                    print(f"🎯 Scraping {pages_to_scrape} pages from {section['name']}")
                
                # Scrape this section
                if pages_per_section == 0:
                    # For unlimited, we need to calculate max items based on total pages
                    max_items_for_section = total_pages * 25  # Assume 25 videos per page
                    section_content = self.extract_content_with_pagination(max_items=max_items_for_section, current_section_url=section_url)
                else:
                    section_content = self.extract_content_with_pagination(max_items=pages_to_scrape * 25, current_section_url=section_url)
                
                if section_content:
                    # Add section information to each item
                    for item in section_content:
                        item['section'] = section['name']
                        item['section_url'] = section['url']
                    
                    all_content.extend(section_content)
                    section['completed'] = True
                    section['pages_scraped'] = pages_to_scrape
                    
                    completed_sections += 1
                    total_videos_so_far += len(section_content)
                    
                    print(f"✅ {section['name']}: Successfully scraped {len(section_content)} videos")
                    print(f"📊 Progress: {completed_sections}/{total_sections} sections completed, {total_videos_so_far} total videos")
                else:
                    print(f"❌ {section['name']}: No content extracted")
                
                # Small delay between sections
                if section_idx < total_sections:
                    print("⏳ Waiting 3 seconds before next section...")
                    time.sleep(3)
                
            except Exception as e:
                print(f"❌ Error scraping {section['name']}: {e}")
                logging.error(f"Error scraping section {section['name']}: {e}")
                continue
        
        self.content = all_content
        print(f"\n🎉 Multi-section scrape completed!")
        print(f"📊 Total videos across all sections: {len(all_content)}")
        
        # Show summary by section
        print("\n📋 Section Summary:")
        for section in self.medical_sections:
            status = "✅" if section['completed'] else "❌"
            print(f"  {status} {section['name']}: {section['pages_scraped']} pages scraped")
        
        return all_content

    def scrape_recently_added_section(self, max_videos: int = 1000) -> List[Dict]:
        """
        Scrape the "Recently Added" section from the main neurosurgery page
        
        Args:
            max_videos: Maximum number of videos to extract (0 for unlimited)
            
        Returns:
            List of dictionaries containing extracted video metadata
        """
        logging.info(f"Starting to scrape 'Recently Added' section (max {max_videos if max_videos > 0 else 'unlimited'} videos)...")
        
        try:
            # Navigate to the main neurosurgery page
            print(f"🌐 Navigating to main neurosurgery page: {self.target_url}")
            self.driver.get(self.target_url)
            time.sleep(5)
            
            # Wait for the page to load and look for the "Recently Added" section
            print("🔍 Looking for 'Recently Added' section...")
            
            # Wait for the Recently Added section to appear
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//h3[contains(text(), 'Recently Added')]"))
                )
                print("✅ Found 'Recently Added' section")
            except TimeoutException:
                print("⚠️  'Recently Added' section not found, trying alternative selectors...")
                # Try alternative selectors
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".js_newsVideos"))
                    )
                    print("✅ Found news videos section")
                except TimeoutException:
                    print("❌ Could not find Recently Added section")
                    return []
            
            # Wait a bit more for content to load
            time.sleep(3)
            
            # Look for video items specifically in the Recently Added section
            print("🔍 Looking for video items in 'Recently Added' section...")
            
            # First, locate the Recently Added section specifically
            try:
                recently_added_section = self.driver.find_element(By.CSS_SELECTOR, ".js_newsVideos")
                print("✅ Located Recently Added section container")
            except NoSuchElementException:
                print("❌ Could not locate Recently Added section container")
                return []
            
            # Try different selectors for video items within the Recently Added section
            video_selectors = [
                '.video-item',
                '[class*="video-item"]',
                '.related-video',
                '[class*="related-video"]'
            ]
            
            video_elements = []
            for selector in video_selectors:
                try:
                    # Look for videos specifically within the Recently Added section
                    elements = recently_added_section.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > 0:
                        video_elements = elements
                        print(f"✅ Found {len(video_elements)} video items in Recently Added section using selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not video_elements:
                print("⚠️  No video items found with standard selectors, trying fallback...")
                # Fallback: look for any elements that might contain video content within the Recently Added section
                try:
                    # Look in the news videos section specifically
                    video_elements = recently_added_section.find_elements(By.CSS_SELECTOR, "div, article, section")
                    video_elements = [elem for elem in video_elements if elem.text.strip() and len(elem.text.strip()) > 50]
                    print(f"Fallback found {len(video_elements)} potential video elements in Recently Added section")
                except Exception as e:
                    print(f"Fallback also failed: {e}")
                    return []
            
            # Extract video information
            extracted_videos = []
            print(f"📹 Starting to extract video metadata from {len(video_elements)} elements...")
            
            for i, element in enumerate(video_elements):
                if max_videos > 0 and len(extracted_videos) >= max_videos:
                    break
                    
                try:
                    video_data = self.extract_single_item(element, i + 1)
                    if video_data:
                        # Add section information
                        video_data['section'] = 'Recently Added'
                        video_data['section_url'] = '/neurosurgery/'
                        extracted_videos.append(video_data)
                        print(f"✅ Extracted video {len(extracted_videos)}: {video_data['title'][:50]}...")
                        
                except Exception as e:
                    logging.warning(f"Error extracting video {i+1}: {e}")
                    continue
                
                # Small delay between extractions
                time.sleep(0.2)
            
            # Check if there's a "Show more" button and click it to load more videos
            print("🔍 Checking for 'Show more' button in Recently Added section...")
            try:
                # Look for show more button specifically within the Recently Added section
                show_more_button = recently_added_section.find_element(By.CSS_SELECTOR, ".js_showMore")
                if show_more_button and show_more_button.is_displayed():
                    print("📱 Found 'Show more' button in Recently Added section, clicking to load additional videos...")
                    show_more_button.click()
                    time.sleep(5)
                    
                    # Extract additional videos from the Recently Added section
                    additional_elements = recently_added_section.find_elements(By.CSS_SELECTOR, '.video-item')
                    if additional_elements and len(additional_elements) > len(video_elements):
                        print(f"📈 Loaded {len(additional_elements) - len(video_elements)} additional videos in Recently Added section")
                        # Extract the new videos
                        for i, element in enumerate(additional_elements[len(video_elements):]):
                            if max_videos > 0 and len(extracted_videos) >= max_videos:
                                break
                                
                            try:
                                video_data = self.extract_single_item(element, len(extracted_videos) + 1)
                                if video_data:
                                    video_data['section'] = 'Recently Added'
                                    video_data['section_url'] = '/neurosurgery/'
                                    extracted_videos.append(video_data)
                                    print(f"✅ Extracted additional video {len(extracted_videos)}: {video_data['title'][:50]}...")
                                    
                            except Exception as e:
                                logging.warning(f"Error extracting additional video: {e}")
                                continue
                            
                            time.sleep(0.2)
            except Exception as e:
                print(f"ℹ️  No 'Show more' button found in Recently Added section or error: {e}")
            
            # For Recently Added section, use infinite scroll to load more videos
            print("🔄 Using infinite scroll to load more videos in Recently Added section...")
            initial_video_count = len(video_elements)
            scroll_attempts = 0
            max_scroll_attempts = 10  # Limit scroll attempts to avoid infinite loops
            
            while scroll_attempts < max_scroll_attempts:
                # Scroll to the bottom of the Recently Added section
                self.driver.execute_script("arguments[0].scrollIntoView(false);", recently_added_section)
                time.sleep(3)
                
                # Check if new videos were loaded
                current_video_elements = recently_added_section.find_elements(By.CSS_SELECTOR, '.video-item')
                if len(current_video_elements) > initial_video_count:
                    new_videos = len(current_video_elements) - initial_video_count
                    print(f"📈 Scroll loaded {new_videos} new videos (total: {len(current_video_elements)})")
                    
                    # Extract the new videos
                    for i, element in enumerate(current_video_elements[initial_video_count:]):
                        if max_videos > 0 and len(extracted_videos) >= max_videos:
                            break
                            
                        try:
                            video_data = self.extract_single_item(element, len(extracted_videos) + 1)
                            if video_data:
                                video_data['section'] = 'Recently Added'
                                video_data['section_url'] = '/neurosurgery/'
                                extracted_videos.append(video_data)
                                print(f"✅ Extracted scroll-loaded video {len(extracted_videos)}: {video_data['title'][:50]}...")
                                
                        except Exception as e:
                            logging.warning(f"Error extracting scroll-loaded video: {e}")
                            continue
                        
                        time.sleep(0.2)
                    
                    # Update the initial count for next scroll
                    initial_video_count = len(current_video_elements)
                    scroll_attempts = 0  # Reset scroll attempts since we found new content
                else:
                    scroll_attempts += 1
                    print(f"🔄 Scroll attempt {scroll_attempts}/{max_scroll_attempts} - no new videos loaded")
                
                # Small delay between scrolls
                time.sleep(2)
            
            print(f"🔄 Completed infinite scroll loading. Total videos found: {initial_video_count}")
            
            self.content = extracted_videos
            print(f"\n🎉 'Recently Added' section scraping completed!")
            print(f"📊 Total videos extracted: {len(extracted_videos)}")
            
            return extracted_videos
            
        except Exception as e:
            logging.error(f"Error during Recently Added section scraping: {e}")
            print(f"❌ Error: {e}")
            return []

    def scrape_video_browse_pages(self, max_pages: int = 0) -> List[Dict]:
        """
        Scrape video browse pages with pagination
        
        Args:
            max_pages: Maximum number of pages to scrape (0 means scrape all available pages)
            
        Returns:
            List of dictionaries containing extracted video metadata
        """
        logging.info(f"Starting to scrape video browse pages (max_pages: {max_pages})")
        
        try:
            # Navigate to the main video browse page
            print(f"🌐 Navigating to video browse page: {self.target_url}")
            self.driver.get(self.target_url)
            time.sleep(5)
            
            # Wait for the page to load and look for video items
            print("🔍 Looking for video items...")
            
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                )
                print("✅ Found video items on the page")
            except TimeoutException:
                print("❌ Could not find video items")
                return []
            
            # Get total pages available
            total_pages = self.get_total_pages()
            print(f"📊 Total pages available: {total_pages}")
            
            # Calculate how many pages to scrape
            if max_pages == 0:
                pages_to_scrape = total_pages
                print(f"🎯 Scraping ALL {total_pages} pages from video browse")
            else:
                pages_to_scrape = min(max_pages, total_pages)
                print(f"🎯 Scraping {pages_to_scrape} pages from video browse")
            
            all_videos = []
            
            for page_num in range(1, pages_to_scrape + 1):
                print(f"\n📄 Scraping page {page_num}/{pages_to_scrape}")
                
                if page_num == 1:
                    # For page 1, we're already on it
                    current_url = self.target_url
                else:
                    # Navigate to specific page
                    current_url = f"{self.target_url}?page={page_num}"
                    print(f"🌐 Navigating to: {current_url}")
                    self.driver.get(current_url)
                    time.sleep(3)
                    
                    # Wait for videos to load
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                        )
                    except TimeoutException:
                        print(f"⚠️  Timeout waiting for page {page_num} to load")
                        continue
                
                # Extract videos from current page
                print(f"🔍 Extracting videos from page {page_num}...")
                page_videos = self.extract_videos_from_current_page()
                
                if page_videos:
                    # Add page information to each video
                    for video in page_videos:
                        video['page_number'] = page_num
                        video['source'] = 'Video Browse'
                    
                    all_videos.extend(page_videos)
                    print(f"✅ Page {page_num}: Found {len(page_videos)} videos. Total so far: {len(all_videos)}")
                else:
                    print(f"⚠️  Page {page_num}: No videos found")
                
                # Small delay between pages
                if page_num < pages_to_scrape:
                    print("⏳ Waiting 2 seconds before next page...")
                    time.sleep(2)
            
            self.content = all_videos
            print(f"\n🎉 Video browse scraping completed!")
            print(f"📊 Total videos extracted: {len(all_videos)}")
            
            return all_videos
            
        except Exception as e:
            logging.error(f"Error during video browse scraping: {e}")
            print(f"❌ Error: {e}")
            return []
    
    def extract_videos_from_current_page(self) -> List[Dict]:
        """Extract all videos from the current page"""
        try:
            # Look for video items
            video_elements = self.driver.find_elements(By.CSS_SELECTOR, '.video-item')
            
            if not video_elements:
                print("⚠️  No video items found on current page")
                return []
            
            print(f"📹 Found {len(video_elements)} video items on current page")
            
            # Extract information from each video
            extracted_videos = []
            for i, element in enumerate(video_elements):
                try:
                    video_data = self.extract_single_item(element, i + 1)
                    if video_data:
                        extracted_videos.append(video_data)
                        
                except Exception as e:
                    logging.warning(f"Error extracting video {i+1}: {e}")
                    continue
                
                # Small delay between extractions
                time.sleep(0.1)
            
            return extracted_videos
            
        except Exception as e:
            logging.error(f"Error extracting videos from current page: {e}")
            return []

    def scrape_all_specialties_videos(self) -> List[Dict]:
        """
        Scrape videos from all specialties by navigating to each specialty first,
        then going to video browse from that specialty context
        """
        logging.info("Starting multi-specialty video scraping...")
        
        try:
            # Navigate to the main VuMedi page to see all specialties
            print("🌐 Navigating to main VuMedi page to identify specialties...")
            self.driver.get(self.base_url)
            time.sleep(5)
            
            # Look for specialty navigation elements
            print("🔍 Looking for specialty navigation...")
            
            # First, try to find and click the specialties dropdown to make it visible
            try:
                specialty_dropdown_button = self.driver.find_element(By.CSS_SELECTOR, '#navbar-spec-dropdown')
                print("🎯 Found specialties dropdown button, clicking to open...")
                specialty_dropdown_button.click()
                time.sleep(2)  # Wait for dropdown to open
            except Exception as e:
                print(f"⚠️  Could not click specialties dropdown: {e}")
            
            # Now look for specialty links in the dropdown menu
            specialty_selectors = [
                '.js_navSpecialtiesDropdownMenu .dropdown-item',
                '.dropdown-menu .dropdown-item[href*="/"]',
                'a[href*="/cardiology/"]',
                'a[href*="/dental/"]',
                'a[href*="/urology/"]',
                'a[href*="/neurosurgery/"]',
                'a[href*="/orthopaedics/"]',
                'a[href*="/oncology/"]',
                'a[href*="/pediatrics/"]',
                'a[href*="/psychiatry/"]',
                'a[href*="/dermatology/"]',
                'a[href*="/ophthalmology/"]',
                'a[href*="/radiology/"]',
                'a[href*="/emergency/"]',
                'a[href*="/family/"]',
                'a[href*="/surgery/"]',
                'a[href*="/obstetricsgynecology/"]',
                'a[href*="/anesthesiology/"]',
                'a[href*="/pathology/"]',
                'a[href*="/neurology/"]',
                'a[href*="/endocrinology/"]'
            ]
            
            specialty_links = []
            for selector in specialty_selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for link in links:
                        href = link.get_attribute('href')
                        text = link.text.strip()
                        if href and '/term/' in href and text:
                            specialty_links.append({
                                'name': text,
                                'url': href,
                                'term': href.split('/term/')[-1].split('/')[0]
                            })
                except Exception as e:
                    logging.warning(f"Selector {selector} failed: {e}")
                    continue
            
            if not specialty_links:
                print("⚠️  Could not find specialty links, trying alternative approach...")
                # Fallback: try to find specialty links in the page content
                try:
                    # Look for main specialty pages from the dropdown menu
                    main_specialty_patterns = [
                        '/dental/', '/cardiology/', '/urology/', '/neurosurgery/', '/orthopaedics/',
                        '/oncology/', '/pediatrics/', '/psychiatry/', '/dermatology/', '/ophthalmology/',
                        '/radiology/', '/emergency/', '/family/', '/surgery/', '/obstetricsgynecology/',
                        '/anesthesiology/', '/pathology/', '/neurology/', '/endocrinology/', '/gastroenterology-and-hepatology/',
                        '/general-surgery/', '/hematology-and-oncology/', '/infectious-disease/', '/nephrology/',
                        '/oral-maxillofacial/', '/otolaryngology/', '/plastic-surgery/', '/podiatry/', '/pulmonology/',
                        '/radiation-oncology/', '/rheumatology/', '/adult-and-family-medicine/', '/allergy-asthma-immunology/'
                    ]
                    
                    # Try to find dropdown items first
                    dropdown_items = self.driver.find_elements(By.CSS_SELECTOR, '.js_navSpecialtiesDropdownMenu .dropdown-item')
                    if dropdown_items:
                        print(f"🔍 Found {len(dropdown_items)} dropdown items")
                        for item in dropdown_items:
                            href = item.get_attribute('href')
                            text = item.text.strip()
                            if href and text:
                                specialty_links.append({
                                    'name': text,
                                    'url': href,
                                    'specialty': href.split('/')[-2] if href.endswith('/') else href.split('/')[-1]
                                })
                    else:
                        # Fallback to searching all links
                        all_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/"]')
                        for link in all_links:
                            href = link.get_attribute('href')
                            text = link.text.strip()
                            if href and text and len(text) < 50:  # Reasonable length for specialty names
                                # Check if this is a main specialty page
                                for pattern in main_specialty_patterns:
                                    if pattern in href:
                                        specialty_links.append({
                                            'name': text,
                                            'url': href,
                                            'specialty': pattern.strip('/')
                                        })
                                        break
                except Exception as e:
                    logging.error(f"Fallback specialty detection failed: {e}")
            
            # Remove duplicates and clean up
            unique_specialties = []
            seen_urls = set()
            for specialty in specialty_links:
                if specialty['url'] not in seen_urls and specialty['name']:
                    seen_urls.add(specialty['url'])
                    unique_specialties.append(specialty)
            
            print(f"🎯 Found {len(unique_specialties)} unique specialties")
            
            if not unique_specialties:
                print("❌ No specialties found, cannot proceed")
                return []
            
            # Show first few specialties for verification
            print("\n📋 First 10 specialties found:")
            for i, specialty in enumerate(unique_specialties[:10]):
                print(f"  {i+1}. {specialty['name']} -> {specialty['url']}")
            
            if len(unique_specialties) > 10:
                print(f"  ... and {len(unique_specialties) - 10} more")
            
            # Now scrape videos from each specialty
            all_videos = []
            
            for i, specialty in enumerate(unique_specialties):
                print(f"\n🏥 Processing specialty {i+1}/{len(unique_specialties)}: {specialty['name']}")
                
                try:
                    # Navigate to the specialty page first
                    print(f"🌐 Navigating to specialty: {specialty['url']}")
                    self.driver.get(specialty['url'])
                    time.sleep(3)
                    
                    # Now navigate to video browse from this specialty context
                    video_browse_url = f"{self.base_url}/video/browse/"
                    print(f"🎬 Going to video browse from {specialty['name']} context...")
                    self.driver.get(video_browse_url)
                    time.sleep(5)
                    
                    # Wait for videos to load
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                        )
                        print(f"✅ Videos loaded for {specialty['name']}")
                    except TimeoutException:
                        print(f"⚠️  No videos found for {specialty['name']}, skipping...")
                        continue
                    
                    # Get total pages for this specialty
                    total_pages = self.get_total_pages()
                    print(f"📊 {specialty['name']}: {total_pages} pages available")
                    
                    if total_pages == 0:
                        print(f"⚠️  No pages found for {specialty['name']}, skipping...")
                        continue
                    
                    # Scrape videos from this specialty (get ALL pages)
                    specialty_videos = []
                    pages_to_scrape = total_pages  # Scrape ALL pages for each specialty
                    
                    print(f"🎯 Scraping ALL {total_pages} pages for {specialty['name']}")
                    
                    for page_num in range(1, pages_to_scrape + 1):
                        print(f"  📄 Scraping page {page_num}/{pages_to_scrape} for {specialty['name']}")
                        
                        if page_num == 1:
                            current_url = video_browse_url
                        else:
                            current_url = f"{video_browse_url}?page={page_num}"
                            self.driver.get(current_url)
                            time.sleep(3)
                            
                            try:
                                WebDriverWait(self.driver, 15).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, '.video-item'))
                                )
                            except TimeoutException:
                                print(f"    ⚠️  Timeout on page {page_num}, skipping...")
                                continue
                        
                        # Extract videos from current page
                        page_videos = self.extract_videos_from_current_page()
                        
                        if page_videos:
                            # Add specialty and page information
                            for video in page_videos:
                                video['specialty'] = specialty['name']
                                video['specialty_url'] = specialty['url']
                                video['page_number'] = page_num
                                video['source'] = f'Video Browse ({specialty["name"]})'
                            
                            specialty_videos.extend(page_videos)
                            print(f"    ✅ Page {page_num}: {len(page_videos)} videos. Total for {specialty['name']}: {len(specialty_videos)}")
                        
                        # Small delay between pages
                        if page_num < pages_to_scrape:
                            time.sleep(2)
                    
                    # Add specialty videos to total
                    all_videos.extend(specialty_videos)
                    print(f"🎉 {specialty['name']}: {len(specialty_videos)} videos scraped. Total so far: {len(all_videos)}")
                    
                    # Delay between specialties
                    if i < len(unique_specialties) - 1:
                        print("⏳ Waiting 3 seconds before next specialty...")
                        time.sleep(3)
                    
                except Exception as e:
                    logging.error(f"Error processing specialty {specialty['name']}: {e}")
                    print(f"❌ Error with {specialty['name']}: {e}")
                    continue
            
            self.content = all_videos
            print(f"\n🎉 Multi-specialty video scraping completed!")
            print(f"📊 Total videos extracted across all specialties: {len(all_videos)}")
            
            return all_videos
            
        except Exception as e:
            logging.error(f"Error during multi-specialty scraping: {e}")
            print(f"❌ Error: {e}")
            return []

def main():
    """Main function to run the VuMedi scraper"""
    scraper = None
    
    try:
        print("🏥 VuMedi Video Browse Scraper")
        print("=" * 50)
        
        # Create scraper instance (not headless so user can login)
        scraper = VuMediScraper(headless=False)
        
        # Step 1: Login
        print("Step 1: Logging in...")
        if not scraper.interactive_login():
            logging.error("Login failed or was not completed")
            return
        
        # Step 2: Navigate to target page
        print("Step 2: Navigating to cerebrovascular content...")
        if not scraper.navigate_to_target_page():
            logging.error("Failed to navigate to target page")
            return
        
        # Step 3: Extract video metadata
        print("Step 3: Extracting video metadata...")
        
        print(f"🚀 Starting comprehensive multi-specialty video scraping (ALL videos from ALL specialties)...")
        content = scraper.scrape_all_specialties_videos()
        
        if content:
            # Step 4: Save data
            print("Step 4: Saving data...")
            scraper.save_to_csv()
            scraper.save_to_json()
            
            # Step 5: Show summary
            scraper.print_summary()
            
            print("\n✅ Scraping completed successfully!")
            print("📁 Files saved:")
            print("   - vumedi_content.csv")
            print("   - vumedi_content.json") 
            print("   - vumedi_scraper.log")
            
        else:
            logging.error("No content was extracted")
            print("\n❌ No content was found or extracted")
            print("This could be due to:")
            print("- Login issues")
            print("- Page structure changes")
            print("- Access restrictions")
            print("- Content loading delays")
    
    except KeyboardInterrupt:
        logging.info("Scraping interrupted by user")
        print("\n⏹️  Scraping interrupted")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print(f"\n❌ Error: {e}")
    finally:
        # Always close the browser
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
