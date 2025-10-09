import os
import asyncio
import re
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

class MedicalSchoolMatchingService:
    def __init__(self):
        print("🔧 Initializing MedicalSchoolMatchingService...")
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
        # Remove common medical school suffixes
        normalized = re.sub(r'\s*\(medical school\)\s*', '', normalized)
        normalized = re.sub(r'\s*medical school\s*', '', normalized)
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

    def _match_with_search_keys(self, provider_school: str, ranked_schools: List[Dict]) -> Dict[str, Any]:
        """Try to match a provider school using search keys"""
        normalized_provider = self._normalize_text(provider_school)
        
        for school in ranked_schools:
            school_id = school['id']
            
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
                                    'school_id': school_id,
                                    'confidence': int(confidence_level),
                                    'match_type': 'search_key',
                                    'matched_school': school,
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
                                'school_id': school_id,
                                'confidence': int(confidence_level),
                                'match_type': 'search_key',
                                'matched_school': school,
                                'matched_key': key
                            }
        
        return {
            'matched': False,
            'school_id': None,
            'confidence': 0,
            'match_type': 'none',
            'matched_school': None,
            'matched_key': None
        }
    
    async def match_all_medical_schools(self):
        """Match all provider medical schools to rankings table using search keys first, then GPT fallback"""
        print("🔍 Starting medical school matching with search keys + GPT fallback...")
        
        # Get all medical schools from providers
        print("Step 1: Getting provider schools...")
        provider_schools = await self._get_provider_medical_schools()
        print(f"📊 Found {len(provider_schools)} total school entries from providers")
        
        # Deduplicate school strings while keeping track of all NPIs
        print("Step 2: Deduplicating schools...")
        unique_schools = {}
        for entry in provider_schools:
            school_str = entry['medical_school']
            if school_str not in unique_schools:
                unique_schools[school_str] = []
            unique_schools[school_str].append(entry['npi'])
        
        print(f"📊 Found {len(unique_schools)} unique school strings")
        print(f"💡 Deduplication saves {len(provider_schools) - len(unique_schools)} GPT calls!")
        
        # Process all unique schools
        unique_school_list = list(unique_schools.items())
        print(f"📊 Processing all {len(unique_school_list)} unique schools")
        
        # Get all ranked schools with search keys
        print("Step 3: Getting ranked schools with search keys...")
        ranked_schools = await self._get_ranked_schools()
        print(f"📊 Found {len(ranked_schools)} ranked medical schools")
        
        # Step 4: Try search key matching first
        print("Step 4: Search key matching...")
        search_key_results = []
        gpt_candidates = []
        search_key_matches = 0
        
        for school_str, npis in unique_school_list:
            match_result = self._match_with_search_keys(school_str, ranked_schools)
            
            if match_result['matched']:
                search_key_matches += 1
                # Create results for all NPIs with this school
                for npi in npis:
                    search_key_results.append({
                        'npi': npi,
                        'provider_school': school_str,
                        'matched': True,
                        'medical_school_id': match_result['school_id'],
                        'confidence_score': match_result['confidence'],
                        'match_type': 'search_key',
                        'matched_school': match_result['matched_school'],
                        'matched_key': match_result['matched_key']
                    })
                print(f"✅ SEARCH KEY MATCH: '{school_str}' → {match_result['matched_school']['school_listed']} (confidence: {match_result['confidence']}, key: '{match_result['matched_key']}')")
            else:
                gpt_candidates.append((school_str, npis))
                print(f"❌ NEEDS GPT: '{school_str}'")
        
        print(f"📊 Search key results: {search_key_matches}/{len(unique_school_list)} matches ({search_key_matches/len(unique_school_list)*100:.1f}%)")
        
        # Step 5: GPT matching for non-matches
        all_results = search_key_results.copy()
        
        if gpt_candidates:
            print(f"Step 5: GPT matching for {len(gpt_candidates)} schools...")
            gpt_results = await self._gpt_match_candidates(gpt_candidates, ranked_schools)
            all_results.extend(gpt_results)
        
        # Insert ALL results into database (including unmatched with NULL medical_school_id)
        await self._insert_all_results(all_results)
        
        # Save results to CSV for analysis
        await self._save_results_to_csv(all_results)
        
        # Calculate final statistics
        total_matches = sum(1 for r in all_results if r['matched'])
        search_key_matches = sum(1 for r in all_results if r.get('match_type') == 'search_key')
        gpt_matches = sum(1 for r in all_results if r.get('match_type') == 'gpt')
        no_matches = sum(1 for r in all_results if not r['matched'])
        
        print(f"🎉 Completed! Processed {len(unique_school_list)} unique schools")
        print(f"📊 FINAL RESULTS:")
        print(f"✅ Total matches: {total_matches}/{len(all_results)} ({total_matches/len(all_results)*100:.1f}%)")
        print(f"🔑 Search key matches: {search_key_matches}/{len(all_results)} ({search_key_matches/len(all_results)*100:.1f}%)")
        print(f"🤖 GPT matches: {gpt_matches}/{len(all_results)} ({gpt_matches/len(all_results)*100:.1f}%)")
        print(f"❌ No matches: {no_matches}/{len(all_results)} ({no_matches/len(all_results)*100:.1f}%)")
        print(f"💡 Search keys saved {search_key_matches} GPT calls!")
    
    async def _gpt_match_candidates(self, gpt_candidates: List[tuple], ranked_schools: List[Dict]) -> List[Dict[str, Any]]:
        """Use GPT to match schools that didn't match with search keys"""
        if not gpt_candidates:
            return []
        
        # Prepare ranked schools list for GPT
        ranked_list = []
        for school in ranked_schools:
            ranked_list.append(f"{school['id']}: {school['school_listed']}")
        
        ranked_schools_text = "\n".join(ranked_list)
        
        # Process in batches of 3
        batch_size = 3
        all_results = []
        total_tokens = 0
        
        for i in range(0, len(gpt_candidates), batch_size):
            batch = gpt_candidates[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(gpt_candidates) + batch_size - 1) // batch_size
            
            print(f"🔄 GPT batch {batch_num}/{total_batches} ({len(batch)} schools)...")
            
            # Extract school strings for this batch
            school_strings = [item[0] for item in batch]
            
            # Create prompt
            prompt = f"""You are a medical school matching expert. Match each provider-reported medical school name to the most appropriate ranked medical school from the list below.

RANKED MEDICAL SCHOOLS:
{ranked_schools_text}

PROVIDER SCHOOLS TO MATCH:
{chr(10).join([f"{i+1}. {school}" for i, school in enumerate(school_strings)])}

INSTRUCTIONS:
- Match each provider school to the most appropriate ranked school by ID
- Consider name variations, abbreviations, and common aliases
- Only match if you're at least 60% confident
- For each match, provide: ID,CONFIDENCE_SCORE
- If no good match exists, respond: NO_MATCH,0
- Respond with one line per provider school in the same order

OUTPUT FORMAT (one line per school):
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
                        
                    school_str, npis = batch[j]
                    line = line.strip()
                    
                    if not line:
                        # Create results for all NPIs with this school
                        for npi in npis:
                            batch_results.append({
                                'npi': npi,
                                'provider_school': school_str,
                                'matched': False,
                                'medical_school_id': None,
                                'confidence_score': 0,
                                'match_type': 'gpt',
                                'matched_school': None,
                                'matched_key': None
                            })
                        continue
                    
                    try:
                        if line.upper().startswith('NO_MATCH'):
                            # Create results for all NPIs with this school
                            for npi in npis:
                                batch_results.append({
                                    'npi': npi,
                                    'provider_school': school_str,
                                    'matched': False,
                                    'medical_school_id': None,
                                    'confidence_score': 0,
                                    'match_type': 'gpt',
                                    'matched_school': None,
                                    'matched_key': None
                                })
                        else:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                school_id = int(parts[0].strip())
                                confidence = int(parts[1].strip())
                                
                                # Find the matched school
                                matched_school = None
                                for school in ranked_schools:
                                    if school['id'] == school_id:
                                        matched_school = school
                                        break
                                
                                # Create results for all NPIs with this school
                                for npi in npis:
                                    batch_results.append({
                                        'npi': npi,
                                        'provider_school': school_str,
                                        'matched': True,
                                        'medical_school_id': school_id,
                                        'confidence_score': confidence,
                                        'match_type': 'gpt',
                                        'matched_school': matched_school,
                                        'matched_key': None
                                    })
                            else:
                                # Create results for all NPIs with this school
                                for npi in npis:
                                    batch_results.append({
                                        'npi': npi,
                                        'provider_school': school_str,
                                        'matched': False,
                                        'medical_school_id': None,
                                        'confidence_score': 0,
                                        'match_type': 'gpt',
                                        'matched_school': None,
                                        'matched_key': None
                                    })
                    except (ValueError, IndexError):
                        # Create results for all NPIs with this school
                        for npi in npis:
                            batch_results.append({
                                'npi': npi,
                                'provider_school': school_str,
                                'matched': False,
                                'medical_school_id': None,
                                'confidence_score': 0,
                                'match_type': 'gpt',
                                'matched_school': None,
                                'matched_key': None
                            })
                
                all_results.extend(batch_results)
                
                # Count successful matches in this batch
                matched_schools = set()
                for result in batch_results:
                    if result['matched']:
                        matched_schools.add(result['provider_school'])
                batch_matches = len(matched_schools)
                
                print(f"✅ GPT batch {batch_num} completed: {batch_matches}/{len(batch)} matches")
                
                # Add small delay to avoid rate limits
                if batch_num < total_batches:
                    print("⏳ Waiting 2 seconds to avoid rate limits...")
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"❌ GPT batch {batch_num} failed: {e}")
                # Create failed results for all schools in this batch
                for school_str, npis in batch:
                    for npi in npis:
                        all_results.append({
                            'npi': npi,
                            'provider_school': school_str,
                            'matched': False,
                            'medical_school_id': None,
                            'confidence_score': 0,
                            'match_type': 'gpt',
                            'matched_school': None,
                            'matched_key': None
                        })
        
        return all_results
    
    async def _get_provider_medical_schools(self) -> List[Dict[str, Any]]:
        """Get all medical schools from US News and Healthgrades data, splitting by | delimiter"""
        with self.engine.connect() as conn:
            all_schools = []
            
            # Get US News data
            result = conn.execute(text("""
                SELECT npi, medical_school
                FROM usnews_data 
                WHERE medical_school IS NOT NULL AND medical_school != ''
            """))
            
            for row in result:
                npi, medical_school = row
                # Split by | and process each school
                schools = [s.strip() for s in medical_school.split('|') if s.strip()]
                for school in schools:
                    all_schools.append({'npi': npi, 'medical_school': school})
            
            # Get Healthgrades data (only for NPIs not in US News)
            result = conn.execute(text("""
                SELECT npi, medical_school
                FROM healthgrades_data 
                WHERE medical_school IS NOT NULL AND medical_school != ''
                AND npi NOT IN (
                    SELECT npi FROM usnews_data 
                    WHERE medical_school IS NOT NULL AND medical_school != ''
                )
            """))
            
            for row in result:
                npi, medical_school = row
                # Split by | and process each school
                schools = [s.strip() for s in medical_school.split('|') if s.strip()]
                for school in schools:
                    all_schools.append({'npi': npi, 'medical_school': school})
            
            return all_schools
    
    async def _get_ranked_schools(self) -> List[Dict[str, Any]]:
        """Get ranked medical schools with search keys, limited to rank 1–75"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, rank, school_listed, full_official_name, city, state_region,
                       search_key_100, search_key_90, search_key_80
                FROM medical_school_rankings
                WHERE rank BETWEEN 1 AND 75
                ORDER BY rank, id
            """))
            schools = [{
                'id': row[0],
                'rank': row[1],
                'school_listed': row[2],
                'full_official_name': row[3],
                'city': row[4],
                'state_region': row[5],
                'search_key_100': row[6],
                'search_key_90': row[7],
                'search_key_80': row[8]
            } for row in result]

            print(f"🏷️ Using ranked schools 1–75 only: {len(schools)} schools loaded")
            if len(schools) < 75:
                print("⚠️ Warning: fewer than 75 schools returned (check rank data and filters)")
            return schools
    
    async def _gpt_match_batch_deduplicated(self, batch: List[tuple], ranked_schools: List[Dict], batch_num: int = 0) -> tuple[List[Dict], int]:
        """Process a batch of unique school strings with GPT. Returns (results, tokens_used)"""
        try:
            # Create ranked schools list for GPT
            ranked_list = "\n".join([
                f"{school['id']}: {school['school_listed']} | {school['full_official_name']}"
                for school in ranked_schools
            ])
            
            # Create batch prompt for unique schools
            provider_schools_text = "\n".join([
                f"{i+1}. {school_str}"
                for i, (school_str, npis) in enumerate(batch)
            ])
            
            prompt = f"""Match each medical school to a ranked school ID. Return EXACTLY {len(batch)*2} comma-separated values.

Schools to match:
{provider_schools_text}

Ranked schools:
{ranked_list}

CRITICAL: Return ONLY comma-separated values in this exact format:
- For matches: ID,SCORE (where SCORE is 60-100)
- For no matches: NO_MATCH,0

Example for 3 schools: 104,95,NO_MATCH,0,43,85

Return ONLY the values, no explanation:"""
            
            response = await self.client.ainvoke(prompt)
            
            # Extract token usage (LangChain doesn't provide this directly)
            tokens_used = 0  # Will be estimated based on prompt length
            
            # Parse results (expecting ID,SCORE pairs)
            result_text = response.content.strip()
            results = [r.strip() for r in result_text.split(',')]
            
            # Create results for each unique school, then expand to all NPIs
            batch_results = []
            for i, (school_str, npis) in enumerate(batch):
                # Each school should have 2 values: ID and score
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
                        print(f"⚠️ Invalid format for school {i+1}: ID='{id_str}', Score='{score_str}'")
                        match_id = None
                        confidence_score = 0
                        matched = False
                else:
                    print(f"⚠️ Missing data for school {i+1}: expected indices {id_index},{score_index}, got {len(results)} results")
                    match_id = None
                    confidence_score = 0
                    matched = False
                
                # Create result for each NPI with this school
                for npi in npis:
                    batch_results.append({
                        'npi': npi,
                        'medical_school_id': match_id,
                        'provider_school': school_str,
                        'matched': matched,
                        'confidence_score': confidence_score
                    })
            
            return batch_results, tokens_used
                
        except Exception as e:
            print(f"❌ GPT batch error: {e}")
            # Return empty results for the batch
            batch_results = []
            for school_str, npis in batch:
                for npi in npis:
                    batch_results.append({
                        'npi': npi,
                        'medical_school_id': None,
                        'provider_school': school_str,
                        'matched': False,
                        'confidence_score': 0
                    })
            return batch_results, 0

    
    async def _insert_all_results(self, all_results: List[Dict[str, Any]]):
        """Insert all results (matched and unmatched) into npi_medical_school_mapping table"""
        with self.engine.connect() as conn:
            # Group results by NPI to handle multiple schools per NPI
            npi_results = {}
            for result in all_results:
                npi = result['npi']
                if npi not in npi_results:
                    npi_results[npi] = []
                npi_results[npi].append(result)
            
            for npi, results in npi_results.items():
                try:
                    # For each NPI, we'll store the BEST match (highest confidence)
                    # or the first match if no confidence scores
                    best_result = None
                    best_confidence = -1
                    
                    for result in results:
                        if result['matched'] and result.get('confidence_score', 0) > best_confidence:
                            best_result = result
                            best_confidence = result.get('confidence_score', 0)
                    
                    # If no matches found, use the first result (unmatched)
                    if best_result is None:
                        best_result = results[0]
                    
                    conn.execute(text("""
                        INSERT INTO npi_medical_school_mapping (npi, medical_school_id)
                        VALUES (:npi, :medical_school_id)
                        ON CONFLICT (npi) DO UPDATE SET
                        medical_school_id = EXCLUDED.medical_school_id
                    """), {
                        'npi': npi,
                        'medical_school_id': best_result['medical_school_id']
                    })
                    
                except Exception as e:
                    print(f"❌ Database error for NPI {npi}: {e}")
            
            conn.commit()
    
    async def _save_results_to_csv(self, all_results: List[Dict[str, Any]]):
        """Save all results (matched and unmatched) to CSV for analysis"""
        import csv
        from datetime import datetime
        
        csv_filename = f'medical_school_matching_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        
        # Fetch ranked school details for matched IDs
        ranked_school_details = {}
        matched_ids = {result['medical_school_id'] for result in all_results if result['medical_school_id'] is not None}
        if matched_ids:
            with self.engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT id, rank, school_listed, full_official_name, city, state_region
                    FROM medical_school_rankings
                    WHERE id IN ({','.join(map(str, matched_ids))})
                """))
                for row in result:
                    ranked_school_details[row[0]] = {
                        'rank': row[1],
                        'school_listed': row[2],
                        'full_official_name': row[3],
                        'city': row[4],
                        'state_region': row[5]
                    }
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow([
                'NPI',
                'Provider_Medical_School',
                'Matched',
                'Medical_School_ID',
                'Confidence_Score',
                'School_Listed',
                'Full_Official_Name',
                'Rank',
                'City',
                'State_Region',
                'Match_Type'
            ])
            
            # Write data
            for result in all_results:
                school_id = result['medical_school_id']
                details = ranked_school_details.get(school_id, {})
                writer.writerow([
                    result['npi'],
                    result['provider_school'],
                    result['matched'],
                    school_id or '',
                    result.get('confidence_score', 0),
                    details.get('school_listed', ''),
                    details.get('full_official_name', ''),
                    details.get('rank', ''),
                    details.get('city', ''),
                    details.get('state_region', ''),
                    result.get('match_type', 'none')  # search_key, gpt, or none
                ])
        
        print(f"📊 Results saved to CSV: {csv_filename}")
        return csv_filename
