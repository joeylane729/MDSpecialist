import os
import asyncio
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

class ResidencyMatchingService:
    def __init__(self):
        print("🔧 Initializing ResidencyMatchingService...")
        self.database_url = os.getenv('DATABASE_URL')
        print("📊 Creating database engine...")
        self.engine = create_engine(self.database_url)
        print("🤖 Creating OpenAI client...")
        self.client = ChatOpenAI(model="gpt-5", request_timeout=300)
        print("✅ Service initialization complete!")
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching - lowercase, strip punctuation, extra spaces"""
        if not text:
            return ""
        # Convert to lowercase, remove extra whitespace
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        # Remove punctuation (commas, periods, apostrophes) but keep special chars like &, %
        normalized = re.sub(r'[,.\']', '', normalized)
        # Remove common residency program suffixes
        normalized = re.sub(r'\s*\(residency program\)\s*', '', normalized)
        normalized = re.sub(r'\s*residency program\s*', '', normalized)
        return normalized

    def _parse_bracketed_keys(self, key_string: str) -> List[List[str]]:
        """Parse bracketed location keys like [california, irvine]"""
        if not key_string or not isinstance(key_string, str):
            return []
        
        # Look for [word1, word2, word3] pattern
        matches = re.findall(r'\[([^\]]+)\]', key_string)
        if not matches:
            return []
        
        # Split by comma and clean up
        keys = []
        for match in matches:
            parts = [part.strip().lower() for part in match.split(',')]
            keys.append(parts)
        return keys

    def _match_with_search_keys(self, provider_residency: str, ranked_residencies: List[Dict]) -> Dict[str, Any]:
        """Try to match a provider residency using search keys"""
        normalized_provider = self._normalize_text(provider_residency)
        
        for school in ranked_residencies:
            program_id = school['id']
            
            # Check each search key column
            for confidence_level in ['100', '90', '80']:
                key_column = f'search_key_{confidence_level}'
                if key_column in school and school[key_column]:
                    search_keys = str(school[key_column]).strip()
                    
                    if not search_keys:
                        continue
                    
                    # Handle bracketed location keys FIRST
                    bracketed_keys = self._parse_bracketed_keys(search_keys)
                    if bracketed_keys:
                        # Check if ALL words in any bracketed key are present
                        for key_group in bracketed_keys:
                            if all(word in normalized_provider for word in key_group):
                                return {
                                    'matched': True,
                                    'program_id': program_id,
                                    'confidence': int(confidence_level),
                                    'match_type': 'search_key',
                                    'matched_residency': school,
                                    'matched_key': f"[{', '.join(key_group)}]"
                                }
                    
                    # Handle regular comma-separated keys (EXCLUDE bracketed keys)
                    # Remove bracketed keys from the string before splitting
                    clean_search_keys = search_keys
                    for bracketed_key in bracketed_keys:
                        # Remove the bracketed key from the string
                        bracketed_str = f"[{', '.join(bracketed_key)}]"
                        clean_search_keys = clean_search_keys.replace(bracketed_str, '')
                    
                    regular_keys = [key.strip().lower() for key in clean_search_keys.split(',') if key.strip()]
                    
                    for key in regular_keys:
                        if key in normalized_provider:
                            return {
                                'matched': True,
                                'program_id': program_id,
                                'confidence': int(confidence_level),
                                'match_type': 'search_key',
                                'matched_residency': school,
                                'matched_key': key
                            }
        
        return {
            'matched': False,
            'program_id': None,
            'confidence': 0,
            'match_type': 'none',
            'matched_residency': None,
            'matched_key': None
        }
    
    async def match_all_residencies(self):
        """Match all provider residency programs to rankings table using search keys only"""
        print("🔍 Starting residency program matching with search keys (no GPT)...")
        
        # Get all residency programs from providers
        print("Step 1: Getting provider residencies...")
        provider_residencies = await self._get_provider_residencies()
        print(f"📊 Found {len(provider_residencies)} total residency entries from providers")
        
        # Deduplicate residency strings while keeping track of all NPIs
        print("Step 2: Deduplicating residencies...")
        unique_residencies = {}
        for entry in provider_residencies:
            residency_str = entry['residency']
            if residency_str not in unique_residencies:
                unique_residencies[residency_str] = []
            unique_residencies[residency_str].append(entry['npi'])
        
        print(f"📊 Found {len(unique_residencies)} unique residency strings")
        print(f"💡 Deduplication saves {len(provider_residencies) - len(unique_residencies)} potential duplicate matches!")
        
        # Process all unique residencies
        unique_residency_list = list(unique_residencies.items())
        print(f"📊 Processing all {len(unique_residency_list)} unique residencies")
        
        # Get all ranked residencies with search keys
        print("Step 3: Getting ranked residencies with search keys...")
        ranked_residencies = await self._get_ranked_residencies()
        print(f"📊 Found {len(ranked_residencies)} ranked residency programs")
        
        # Step 4: Search key matching (no GPT fallback)
        print("Step 4: Search key matching (GPT disabled)...")
        search_key_results = []
        unmatched_results = []
        search_key_matches = 0
        
        for residency_str, npis in unique_residency_list:
            match_result = self._match_with_search_keys(residency_str, ranked_residencies)
            
            if match_result['matched']:
                search_key_matches += 1
                # Create results for all NPIs with this residency
                for npi in npis:
                    search_key_results.append({
                        'npi': npi,
                        'provider_residency': residency_str,
                        'matched': True,
                        'residency_program_id': match_result['program_id'],
                        'confidence_score': match_result['confidence'],
                        'match_type': 'search_key',
                        'matched_residency': match_result['matched_residency'],
                        'matched_key': match_result['matched_key']
                    })
                print(f"✅ SEARCH KEY MATCH: '{residency_str}' → {match_result['matched_residency']['program_name']} (confidence: {match_result['confidence']}, key: '{match_result['matched_key']}')")
            else:
                for npi in npis:
                    unmatched_results.append({
                        'npi': npi,
                        'provider_residency': residency_str,
                        'matched': False,
                        'residency_program_id': None,
                        'confidence_score': 0,
                        'match_type': 'none',
                        'matched_residency': None,
                        'matched_key': None
                    })
                print(f"❌ NO MATCH (search keys only): '{residency_str}'")
        
        print(f"📊 Search key results: {search_key_matches}/{len(unique_residency_list)} matches ({search_key_matches/len(unique_residency_list)*100:.1f}%)")
        print("🤖 GPT step skipped - unmatched residencies remain unmatched in this run")
        
        all_results = search_key_results + unmatched_results
        
        # Save results to CSV for analysis
        await self._save_results_to_csv(all_results)
        
        # Calculate final statistics
        total_matches = sum(1 for r in all_results if r['matched'])
        no_matches = sum(1 for r in all_results if not r['matched'])
        
        print(f"🎉 Completed! Processed {len(unique_residency_list)} unique residencies")
        print(f"📊 FINAL RESULTS (Search Keys Only):")
        print(f"✅ Total matches: {total_matches}/{len(all_results)} ({(total_matches/len(all_results)*100 if all_results else 0):.1f}%)")
        print(f"❌ No matches: {no_matches}/{len(all_results)} ({(no_matches/len(all_results)*100 if all_results else 0):.1f}%)")
    
    async def _get_provider_residencies(self) -> List[Dict[str, Any]]:
        """Get all residency programs from US News and Healthgrades data, splitting by | delimiter"""
        with self.engine.connect() as conn:
            all_residencies = []
            
            # Get US News data
            result = conn.execute(text("""
                SELECT npi, residency
                FROM usnews_data 
                WHERE residency IS NOT NULL AND residency != ''
            """))
            
            for row in result:
                npi, residency = row
                # Split by | and process each residency
                residencies = [s.strip() for s in residency.split('|') if s.strip()]
                for program in residencies:
                    all_residencies.append({'npi': npi, 'residency': program})
            
            # Get Healthgrades data (only for NPIs not in US News)
            result = conn.execute(text("""
                SELECT npi, residency
                FROM healthgrades_data 
                WHERE residency IS NOT NULL AND residency != ''
                AND npi NOT IN (
                    SELECT npi FROM usnews_data 
                    WHERE residency IS NOT NULL AND residency != ''
                )
            """))
            
            for row in result:
                npi, residency = row
                # Split by | and process each residency
                residencies = [s.strip() for s in residency.split('|') if s.strip()]
                for program in residencies:
                    all_residencies.append({'npi': npi, 'residency': program})
            
            return all_residencies
    
    async def _get_ranked_residencies(self) -> List[Dict[str, Any]]:
        """Get ranked residency programs with search keys, limited to rank 1–75"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, program_name, city,
                       search_key_100, search_key_90, search_key_80
                FROM residency_rankings
                ORDER BY id
            """))
            residencies = [{
                'id': row[0],
                'program_name': row[1],
                'city': row[2],
                'search_key_100': row[3],
                'search_key_90': row[4],
                'search_key_80': row[5]
            } for row in result]

            print(f"🏷️ Loaded {len(residencies)} ranked residency programs")
            if len(residencies) == 0:
                print("⚠️ Warning: no residency rankings found")
            return residencies
    
    async def _save_results_to_csv(self, all_results: List[Dict[str, Any]]):
        """Save all results (matched and unmatched) to CSV for analysis"""
        import csv
        from datetime import datetime
        
        csv_filename = f'residency_matching_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Fetch ranked residency details for matched IDs
        ranked_residency_details = {}
        matched_ids = {result['residency_program_id'] for result in all_results if result['residency_program_id'] is not None}
        if matched_ids:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT id, program_name, city
                    FROM residency_rankings
                    WHERE id IN ({','.join(map(str, matched_ids))})
                """))
                for row in result:
                    ranked_residency_details[row[0]] = {
                        'program_name': row[1],
                        'city': row[2]
                    }
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'NPI',
                'Provider_Residency',
                'Matched',
                'Residency_Program_ID',
                'Confidence_Score',
                'Program_Name',
                'City',
                'Match_Type'
            ])
            
            # Write data
            for result in all_results:
                program_id = result['residency_program_id']
                details = ranked_residency_details.get(program_id, {})
                writer.writerow([
                    result['npi'],
                    result['provider_residency'],
                    result['matched'],
                    program_id or '',
                    result.get('confidence_score', 0),
                    details.get('program_name', ''),
                    details.get('city', ''),
                    result.get('match_type', 'none')  # search_key, gpt, or none
                ])
        
        print(f"📊 Results saved to CSV: {csv_filename}")
        return csv_filename
