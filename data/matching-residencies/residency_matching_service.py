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
        """Match all provider residency programs to rankings table using search keys first, then GPT fallback"""
        print("🔍 Starting residency program matching with search keys + GPT fallback...")
        
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
        print(f"💡 Deduplication saves {len(provider_residencies) - len(unique_residencies)} GPT calls!")
        
        # Process all unique residencies
        unique_residency_list = list(unique_residencies.items())
        print(f"📊 Processing all {len(unique_residency_list)} unique residencies")
        
        # Get all ranked residencies with search keys
        print("Step 3: Getting ranked residencies with search keys...")
        ranked_residencies = await self._get_ranked_residencies()
        print(f"📊 Found {len(ranked_residencies)} ranked residency programs")
        
        # Step 4: Try search key matching first
        print("Step 4: Search key matching...")
        search_key_results = []
        gpt_candidates = []
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
                gpt_candidates.append((residency_str, npis))
                print(f"❌ NEEDS GPT: '{residency_str}'")
        
        print(f"📊 Search key results: {search_key_matches}/{len(unique_residency_list)} matches ({search_key_matches/len(unique_residency_list)*100:.1f}%)")
        
        # Step 5: GPT matching for non-matches
        all_results = search_key_results.copy()
        
        if gpt_candidates:
            print(f"Step 5: GPT matching for {len(gpt_candidates)} residencies...")
            gpt_results = await self._gpt_match_candidates(gpt_candidates, ranked_residencies)
            all_results.extend(gpt_results)
        
        # Save results to CSV for analysis
        await self._save_results_to_csv(all_results)
        
        # Calculate final statistics
        total_matches = sum(1 for r in all_results if r['matched'])
        search_key_matches = sum(1 for r in all_results if r.get('match_type') == 'search_key')
        gpt_matches = sum(1 for r in all_results if r.get('match_type') == 'gpt')
        no_matches = sum(1 for r in all_results if not r['matched'])
        
        print(f"🎉 Completed! Processed {len(unique_residency_list)} unique residencies")
        print(f"📊 FINAL RESULTS:")
        print(f"✅ Total matches: {total_matches}/{len(all_results)} ({total_matches/len(all_results)*100:.1f}%)")
        print(f"🔑 Search key matches: {search_key_matches}/{len(all_results)} ({search_key_matches/len(all_results)*100:.1f}%)")
        print(f"🤖 GPT matches: {gpt_matches}/{len(all_results)} ({gpt_matches/len(all_results)*100:.1f}%)")
        print(f"❌ No matches: {no_matches}/{len(all_results)} ({no_matches/len(all_results)*100:.1f}%)")
        print(f"💡 Search keys saved {search_key_matches} GPT calls!")
    
    async def _gpt_match_candidates(self, gpt_candidates: List[tuple], ranked_residencies: List[Dict]) -> List[Dict[str, Any]]:
        """Use GPT to match residencies that did not match with search keys"""
        if not gpt_candidates:
            return []
        
        # Prepare ranked residency list for GPT
        ranked_list = []
        for program in ranked_residencies:
            ranked_list.append(f"{program['id']}: {program['program_name']}")
        
        ranked_residencies_text = "\n".join(ranked_list)
        
        # Process in batches of 3
        batch_size = 3
        all_results = []
        total_tokens = 0
        
        for i in range(0, len(gpt_candidates), batch_size):
            batch = gpt_candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(gpt_candidates) + batch_size - 1) // batch_size
            
            print(f"🔄 GPT batch {batch_num}/{total_batches} ({len(batch)} residencies)...")
            
            # Extract residency strings for this batch
            residency_strings = [item[0] for item in batch]
            
            # Create prompt
            prompt = f"""You are a residency program matching expert. Match each provider-reported residency program name to the most appropriate ranked residency program from the list below.

RANKED RESIDENCY PROGRAMS:
{ranked_residencies_text}

PROVIDER RESIDENCIES TO MATCH:
{chr(10).join([f"{i+1}. {school}" for i, school in enumerate(residency_strings)])}

INSTRUCTIONS:
- Match each provider residency to the most appropriate ranked residency by ID
- Consider name variations, abbreviations, and common aliases
- Only match if you're at least 60% confident
- For each match, provide: ID,CONFIDENCE_SCORE
- If no good match exists, respond: NO_MATCH,0
- Respond with one line per provider residency in the same order

OUTPUT FORMAT (one line per residency):
ID,CONFIDENCE_SCORE
or
NO_MATCH,0

Example:
1,85
NO_MATCH,0
15,92"""

            try:
                response = await self.client.ainvoke(prompt)
                gpt_response = response.content.strip()
                
                # Parse GPT response
                lines = gpt_response.strip().split('\n')
                batch_results = []
                
                for j, line in enumerate(lines):
                    if j >= len(batch):
                        break
                        
                    residency_str, npis = batch[j]
                    line = line.strip()
                    
                    if not line:
                        # Create results for all NPIs with this residency
                        for npi in npis:
                            batch_results.append({
                                'npi': npi,
                                'provider_residency': residency_str,
                                'matched': False,
                                'residency_program_id': None,
                                'confidence_score': 0,
                                'match_type': 'gpt',
                                'matched_residency': None,
                                'matched_key': None
                            })
                        continue
                    
                    try:
                        if line.upper().startswith('NO_MATCH'):
                            # Create results for all NPIs with this residency
                            for npi in npis:
                                batch_results.append({
                                    'npi': npi,
                                    'provider_residency': residency_str,
                                    'matched': False,
                                    'residency_program_id': None,
                                    'confidence_score': 0,
                                    'match_type': 'gpt',
                                    'matched_residency': None,
                                    'matched_key': None
                                })
                        else:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                program_id = int(parts[0].strip())
                                confidence = int(parts[1].strip())
                                
                                # Find the matched school
                                matched_residency = None
                                for school in ranked_residencies:
                                    if school['id'] == program_id:
                                        matched_residency = school
                                        break
                                
                                # Create results for all NPIs with this residency
                                for npi in npis:
                                    batch_results.append({
                                        'npi': npi,
                                        'provider_residency': residency_str,
                                        'matched': True,
                                        'residency_program_id': program_id,
                                        'confidence_score': confidence,
                                        'match_type': 'gpt',
                                        'matched_residency': matched_residency,
                                        'matched_key': None
                                    })
                            else:
                                # Create results for all NPIs with this residency
                                for npi in npis:
                                    batch_results.append({
                                        'npi': npi,
                                        'provider_residency': residency_str,
                                        'matched': False,
                                        'residency_program_id': None,
                                        'confidence_score': 0,
                                        'match_type': 'gpt',
                                        'matched_residency': None,
                                        'matched_key': None
                                    })
                    except (ValueError, IndexError):
                        # Create results for all NPIs with this residency
                        for npi in npis:
                            batch_results.append({
                                'npi': npi,
                                'provider_residency': residency_str,
                                'matched': False,
                                'residency_program_id': None,
                                'confidence_score': 0,
                                'match_type': 'gpt',
                                'matched_residency': None,
                                'matched_key': None
                            })
                
                all_results.extend(batch_results)
                
                # Count successful matches in this batch
                matched_residencys = set()
                for result in batch_results:
                    if result['matched']:
                        matched_residencys.add(result['provider_residency'])
                batch_matches = len(matched_residencys)
                
                print(f"✅ GPT batch {batch_num} completed: {batch_matches}/{len(batch)} matches")
                
                # Add small delay to avoid rate limits
                if batch_num < total_batches:
                    print("⏳ Waiting 2 seconds to avoid rate limits...")
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"❌ GPT batch {batch_num} failed: {e}")
                # Create failed results for all residencies in this batch
                for residency_str, npis in batch:
                    for npi in npis:
                        all_results.append({
                            'npi': npi,
                            'provider_residency': residency_str,
                            'matched': False,
                            'residency_program_id': None,
                            'confidence_score': 0,
                            'match_type': 'gpt',
                            'matched_residency': None,
                            'matched_key': None
                        })
        
        return all_results
    
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
    
    async def _gpt_match_batch_deduplicated(self, batch: List[tuple], ranked_residencies: List[Dict], batch_num: int = 0) -> tuple[List[Dict], int]:
        """Process a batch of unique residency strings with GPT. Returns (results, tokens_used)"""
        try:
            # Create ranked residency list for GPT
            ranked_list = "\n".join([
                f"{school['id']}: {school['program_name']}"
                for school in ranked_residencies
            ])
            
            # Create batch prompt for unique residencies
            provider_residencies_text = "\n".join([
                f"{i+1}. {residency_str}"
                for i, (residency_str, npis) in enumerate(batch)
            ])
            
            prompt = f"""Match each residency program to a ranked residency ID. Return EXACTLY {len(batch)*2} comma-separated values.

Residencies to match:
{provider_residencies_text}

Ranked residency programs:
{ranked_list}

CRITICAL: Return ONLY comma-separated values in this exact format:
- For matches: ID,SCORE (where SCORE is 60-100)
- For no matches: NO_MATCH,0

Example for 3 residencies: 104,95,NO_MATCH,0,43,85

Return ONLY the values, no explanation:"""
            
            response = await self.client.ainvoke(prompt)
            
            # Extract token usage (LangChain doesn't provide this directly)
            tokens_used = 0  # Will be estimated based on prompt length
            
            # Parse results (expecting ID,SCORE pairs)
            result_text = response.content.strip()
            results = [r.strip() for r in result_text.split(',')]
            
            # Create results for each unique residency, then expand to all NPIs
            batch_results = []
            for i, (residency_str, npis) in enumerate(batch):
                # Each residency should have 2 values: ID and score
                id_index = i * 2
                score_index = id_index + 1
                
                # More robust parsing with better error handling
                if (id_index < len(results) and score_index < len(results)):
                    id_str = results[id_index].strip()
                    score_str = results[score_index].strip()
                    
                    # Handle NO_MATCH case
                    if id_str == "NO_MATCH" and score_str == "0":
                        match_id = None
                        confidence_score = 0
                        matched = False
                    # Check if both are valid numbers
                    elif id_str.isdigit() and score_str.isdigit():
                        match_id = int(id_str)
                        confidence_score = int(score_str)
                        matched = True
                    else:
                        print(f"⚠️ Invalid format for residency {i+1}: ID='{id_str}', Score='{score_str}'")
                        match_id = None
                        confidence_score = 0
                        matched = False
                else:
                    print(f"⚠️ Missing data for residency {i+1}: expected indices {id_index},{score_index}, got {len(results)} results")
                    match_id = None
                    confidence_score = 0
                    matched = False
                
                # Create result for each NPI with this residency
                for npi in npis:
                    batch_results.append({
                        'npi': npi,
                        'residency_program_id': match_id,
                        'provider_residency': residency_str,
                        'matched': matched,
                        'confidence_score': confidence_score
                    })
            
            return batch_results, tokens_used
                
        except Exception as e:
            print(f"❌ GPT batch error: {e}")
            # Return empty results for the batch of residencies
            batch_results = []
            for residency_str, npis in batch:
                for npi in npis:
                    batch_results.append({
                        'npi': npi,
                        'residency_program_id': None,
                        'provider_residency': residency_str,
                        'matched': False,
                        'confidence_score': 0
                    })
            return batch_results, 0

    
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
