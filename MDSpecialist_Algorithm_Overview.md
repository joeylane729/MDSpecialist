# MDSpecialist Algorithm Overview

## Purpose
This document outlines the step-by-step process of the MDSpecialist algorithm, including all LLM prompts used to match patients with medical specialists.

---

## Algorithm Flow

### Step 1: Search Query Generation
**Purpose:** Convert the patient's diagnosis into a structured search query for finding relevant medical literature.

**Input:**
- User-entered diagnosis
- Anatomical location

**LLM Prompt:**
```
Generate a concise search query to find PubMed articles and medical lectures from our database using the user-entered diagnosis and the anatomical location:

User-Entered Diagnosis: {user_diagnosis}
Anatomical Location: {anatomical_location}

RULES:
- Diagnostic terms should include all variations of this diagnosis separated by the OR operator
- Anatomic terms should include the anatomic location and all possible ways of describing the anatomic location separated by the OR operator
- The search query should include the diagnostic terms and the anatomic terms separated by the AND operator

Example: (diagnostic_term1 OR diagnostic_term2 OR diagnostic_term3) AND (anatomic_location1 OR anatomic_location2 OR anatomic_location3)

IMPORTANT: Do not include quotations around each term in the search query, just the terms themselves separated by the OR operator.
IMPORTANT: Return ONLY the search query string itself with NO explanations, NO markdown, NO code blocks, NO additional text. Just the query.
```

**Output:** Search query string (e.g., "(pituitary adenoma OR pituitary tumor) AND (brain OR pituitary OR sella)")

---

### Step 2: ICD-10 Code Generation (Two-Step Process)

#### Step 2a: Generate ICD-10 Codes with Brief Descriptions

**Purpose:** Generate candidate ICD-10 codes that match the patient's diagnosis.

**Input:**
- Patient diagnosis
- Anatomical location

**LLM Prompt:**
```
Patient Information:
Diagnosis: {diagnosis}
Anatomical Location: {anatomical_location}

Provide between 5 and 10 of the most likely ICD-10 codes for this diagnosis, including:
- Codes for similar pathology in a similar anatomic location
- If codes use terms like "uncertain behavior" or "unspecified behavior" in their descriptions then the anatomic location and/or the pathologic diagnosis must be the same as the original diagnosis
- DO NOT include codes that contain descriptions of anatomy that is not immediately adjacent to the anatomical location
- Preserve the pathologic category of the original diagnosis (e.g. neoplastic, vascular, infectious, degenerative, metabolic).

For each code, provide a brief description of what the code represents.

Return ONLY a JSON array in this exact format:
[
    {"code": "ICD10_CODE", "description": "Brief description"},
    {"code": "ICD10_CODE", "description": "Brief description"}
]

Return ONLY the JSON array with NO markdown, NO code blocks, NO additional text.
```

**Output:** List of ICD-10 codes with LLM-generated descriptions

**Database Lookup:** After LLM generation, the system looks up official descriptions for each code from the ICD-10 database.

#### Step 2b: Assign Relevancy Scores to ICD-10 Codes

**Purpose:** Score each ICD-10 code based on relevance to the patient's specific diagnosis.

**Input:**
- Patient diagnosis
- Anatomical location
- ICD-10 codes with official database descriptions

**LLM Prompt:**
```
Given the patient diagnosis and anatomical location, assign a relevancy score from 0 to 100 for each ICD-10 code below.

Patient Diagnosis: {diagnosis}
Anatomical Location: {anatomical_location}

ICD-10 codes with their official descriptions:
{icd10_list}

Return ONLY a JSON array with one object per code, in the same order, with "code" and "relevancy_score" (integer 0-100):
[
  {"code": "CODE", "relevancy_score": 95},
  {"code": "CODE", "relevancy_score": 70}
]

No markdown, no code blocks, no other text.
```

**Output:** Relevancy scores (0-100) for each ICD-10 code

**Filtering:** Only ICD-10 codes with relevancy ≥ 50% are passed to the next step (CPT code generation).

---

### Step 3: CPT Code Generation (Two-Step Process)

#### Step 3a: Generate CPT Codes with Descriptions

**Purpose:** Generate CPT procedure codes that could be used to treat the patient's condition.

**Input:**
- Diagnosis terms (from search query)
- Anatomic terms (from search query)
- ICD-10 codes (≥50% relevancy only)

**LLM Prompt:**
```
Give an exhaustive list of primary CPT codes that could possibly be used to treat patients with any of these diagnoses in these anatomic locations in a simple or complex treatment:

Diagnosis Terms:
{diagnosis_terms}

Anatomic Terms:
{anatomic_terms}

Specialty: Neurosurgery

IMPORTANT:
- Include all CPT codes for treatment of related diagnoses in an adjacent location in a simple or complex treatment
- Do not include any add-on CPT codes (these generally start with a + sign)
- Do not include codes that start with 99XXX, 98XXX, or 6178X
- Do not include codes ending in 99 or 89 (XXX99, XXX89 format)
- Escape all quotes in descriptions (use \" for quotes inside strings)
- Keep descriptions concise (under 100 characters)
- Do NOT include newlines in description strings
- Ensure all strings are properly closed

Return the response in this exact JSON format (code and description only):
[
    {"code": "CPT_CODE", "description": "Procedure description"},
    {"code": "CPT_CODE", "description": "Procedure description"}
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text.
```

**Database Lookup:** The system also queries the ICD-10 to CPT mapping database using the filtered ICD-10 codes to find additional CPT codes.

**Database Description Lookup:** For each CPT code, the system looks up the full official description from the CPT Consolidated database.

#### Step 3b: Categorize and Score CPT Codes

**Purpose:** Assign treatment categories and relevancy scores to each CPT code.

**Input:**
- CPT codes with descriptions
- Diagnosis terms
- Anatomic terms

**LLM Prompt (processed in batches of 10):**
```
Categorize the following CPT codes into ONE of these 5 categories:

Categories (you MUST use only these):
{categories}

CPT Codes:
{cpt_codes}

Then, for each CPT code, assign a relevancy score from 0-100% indicating how likely the code is to be used to treat the diagnosis and anatomic terms below.

Diagnosis Terms:
{diagnosis_terms}

Anatomic Terms:
{anatomic_terms}

Return the response in this exact JSON format:
[
    {
        "code": "CPT_CODE",
        "category": "Category name",
        "relevancy_score": 95
    }
]

Return ONLY the JSON array with NO markdown formatting, NO code blocks, NO additional text. Use ONLY the categories provided above.
```

**Categories:** Surgery, Radiation, Endovascular, Medical, Diagnostic Testing

**Output:** CPT codes with categories and relevancy scores (0-100)

**Filtering:** CPT codes with relevancy < 10% are marked as "irrelevant" and excluded from clinical volume calculations.

---

### Step 4: CMS Clinical Volume Query

**Purpose:** Query CMS public data to find providers who perform the relevant CPT procedures.

**Input:**
- CPT codes (only those with relevancy ≥ 10%)
- Optional state filter

**Process:**
- Queries CMS Medicare Provider Utilization and Payment Data
- Aggregates data across multiple years (2019-2023)
- Retrieves provider NPI, procedure counts (Tot_Srvcs), and other metadata
- Filters to only include providers matching the determined specialty (e.g., Neurological Surgery)

**Output:** List of providers with their procedure volumes for each CPT code

---

### Step 5: Specialist Information Retrieval

**Purpose:** Find relevant medical literature (PubMed articles and VuMedi lectures) for each treatment category.

**Input:**
- Search query (from Step 1)
- CPT codes grouped by treatment category

**Process:**
- **PubMed Search:** Queries the PubMed database using the search query. Requires at least one diagnostic term AND one anatomic term match per article.
- **VuMedi Search:** Queries the VuMedi database (medical lectures) using similar search criteria.
- Groups results by treatment category based on CPT codes.

**Output:** 
- PubMed articles (title, PMID, authors, journal, publication date, author position, journal quartile)
- VuMedi lectures (title, link, featuring specialists)
- Grouped by treatment category

---

### Step 6: Provider Ranking

**Purpose:** Score and rank providers based on multiple objective criteria.

**Scoring Components (weights sum to 100%):**

1. **PubMed Publications (70%)**
   - Base points per article (1 point)
   - Author position bonus:
     - First author: +2 points
     - Last author: +1 point
     - Middle author: +0 points
   - Journal quartile bonus:
     - Q1 (top 25%): +3 points
     - Q2 (25-50%): +2 points
     - Q3 (50-75%): +1 point
     - Q4 (bottom 25%): +0 points

2. **Clinical Volume (10%)**
   - Based on CMS procedure counts (Tot_Srvcs)
   - Normalized as percentage of maximum among all providers
   - Only includes CPT codes with relevancy ≥ 10%
   - Filtered by user-selected treatment categories

3. **Training (10%)**
   - Medical school ranking (top 10/25/50/100)
   - Residency program ranking
   - Board certifications

4. **Experience (5%)**
   - Years of clinical experience
   - Calculated from graduation year

5. **VuMedi Medical Lectures (5%)**
   - Count of relevant medical lectures/presentations

**Process:**
- Each component is normalized to 0-100%
- Weighted by the percentages above
- Final score = sum of weighted components
- Providers are ranked by final score (highest first)

**Output:** Ranked list of providers with detailed score breakdowns

---

### Step 7: Patient Reviews

**Purpose:** Retrieve and filter patient reviews for context.

**Input:**
- Provider NPIs
- Search query terms (diagnostic + anatomic)

**Process:**
- Fetches reviews from Healthgrades database
- Marks reviews as "relevant" if they contain at least one diagnostic term AND one anatomic term
- Calculates average rating for relevant reviews

**Output:** Reviews with relevancy flags and rating statistics
