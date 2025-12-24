# Complete Search Flow Documentation

This document outlines every step that takes place when a user performs a search, from entering their information to seeing results.

## **Required User Flow Sequence**

The UI enforces a specific sequence that users must follow:

1. **Medical Analysis** (Phase 1-5): User enters information and gets medical analysis results
2. **Generate CPT Codes** (Phase 6): User must generate CPT codes before specialist search
3. **Show Specialists** (Phase 7): User can then search for specialists (button only appears after CPT codes are generated)

**Important**: The "Show me suggested specialists" button is conditionally rendered and only appears in the DOM after CPT codes have been generated. This enforces the dependency at the UI level.

## Overview

The search flow involves multiple components:
- **Frontend (React)**: User interface and API calls
- **Backend API (FastAPI)**: Request processing and business logic
- **AI Services**: Medical analysis, specialist recommendations, and ranking
- **Database (PostgreSQL)**: Provider data storage and retrieval
- **External Services**: CMS data, PubMed, VuMedi

---

## Step-by-Step Flow

### **PHASE 1: User Input Collection (Frontend - HomePage.tsx)**

1. **User fills out the search form** with:
   - State selection
   - City selection
   - ZIP code
   - Symptoms (required)
   - Diagnosis (required)
   - Patient age (month and year)
   - Proximity preference (statewide/US-wide)
   - Gender (optional)
   - Medications (optional)
   - Medical history (optional)
   - Surgical history (optional)
   - File uploads (optional PDFs)

2. **User clicks "Search" button**, triggering `handleSearch()` function

   **Note**: The search flow has been separated into two steps:
   - **Step 1 (HomePage)**: User enters information and clicks "Search" → Gets medical analysis only (no providers)
   - **Step 2 (ResultsPage)**: After seeing medical analysis, user clicks "Show me suggested specialists" → Gets provider search and rankings

---

### **PHASE 2: Frontend Validation & Preparation (HomePage.tsx)**

4. **Form validation**:
   - Checks that all required fields are filled:
     - State, City, ZIP code
     - Symptoms, Diagnosis
     - Patient age (month and year)
     - Proximity
   - Shows alert if validation fails

5. **Clear previous results**:
   - Removes `mdspecialist_search_results` from localStorage

6. **Set loading state**:
   - `setIsLoading(true)` to show loading spinner

---

### **PHASE 3: Initial API Call (HomePage.tsx)**

7. **Call `getMedicalAnalysis()` API** (`/api/v1/medical-analysis`):
   - **Request payload**:
     - Symptoms, Diagnosis
     - Medical history, Medications, Surgical history
     - Uploaded files (if any)
   - **This is a POST request with FormData** (multipart/form-data)
   - **Note**: This is the ONLY API call made from HomePage. Provider search happens later on ResultsPage.

---

### **PHASE 4: Backend Medical Analysis (medical_analysis.py endpoint)**

10. **Endpoint receives request** at `/api/v1/medical-analysis`

11. **Medical analysis processing**:
    - Analyzes patient information (symptoms, diagnosis, medical history, etc.)
    - Generates treatment options
    - Predicts ICD-10 codes
    - **Determines specialty** for provider search (optimization - avoids duplicate GPT calls later)
    - Creates search query for specialist information retrieval
    - Returns patient profile with all analysis results including `determined_specialty`

    **Note**: CPT codes are NOT generated in this step - they are generated separately later via a separate API call (Phase 6). CPT code generation is **required** before specialist search can proceed.

12. **Response returned to frontend** with medical analysis results

    The `patient_profile` object contains:
    
    ```json
    {
      "status": "success",
      "patient_profile": {
        // Patient profile data (from process_patient_input)
        "symptoms": ["Severe headaches", "Visual disturbances", "Nausea"],
        "conditions": ["Cluster headaches", "Migraine variants"],
        "specialties_needed": ["Neurological Surgery", "Pain Medicine"],
        "location_preference": "New York, NY",
        "additional_notes": "Patient has tried multiple medications without relief",
        
        // User input fields
        "user_diagnosis": "Suspected cluster headache, possibly trigeminal neuralgia",
        
        // Medical analysis data
        "predicted_icd10": "G44.009",
        "icd10_description": "Cluster headache syndrome, unspecified, not intractable",
        "treatment_options": [
          {
            "name": "Trigeminal Nerve Decompression Surgery",
            "outcomes": "High success rate (80-90%) for long-term pain relief. Most patients experience significant improvement within 2-4 weeks post-surgery.",
            "complications": "Risks include facial numbness, infection, cerebrospinal fluid leak, rare risk of hearing loss or facial weakness. Overall complication rate is low (<5%).",
            "category": "Surgery"
          },
          {
            "name": "Gamma Knife Radiosurgery",
            "outcomes": "Effective in 70-85% of cases. Pain relief typically begins 2-6 months after treatment. Non-invasive alternative to surgery.",
            "complications": "Possible facial numbness or tingling, rare risk of facial weakness. Lower risk profile compared to open surgery.",
            "category": "Radiosurgery"
          },
          {
            "name": "Microvascular Decompression",
            "outcomes": "Excellent long-term results with 85-95% success rate. Provides permanent solution for vascular compression.",
            "complications": "Surgical risks include CSF leak, infection, rare risk of stroke or hearing loss. Requires general anesthesia.",
            "category": "Surgery"
          }
        ],
        "cpt_codes": [],  // Empty initially - generated separately later
        "cpt_prompt_text": "",  // Empty initially
        "diagnoses_prompt_text": "Patient Information:\nSymptoms: Severe headaches...",  // Actual GPT prompt used
        "search_query": "cluster headache trigeminal neuralgia microvascular decompression gamma knife radiosurgery treatment outcomes complications",
        
        // Nested structure for backward compatibility
        "diagnoses": {
          "primary": {
            "code": "G44.009",
            "description": "Cluster headache syndrome, unspecified, not intractable"
          },
          "treatment_options": [
            // Same treatment options as above
          ]
        }
      },
      "message": "Medical analysis completed successfully"
    }
    ```

    **Key fields explained**:
    - **symptoms**: Array of extracted/identified symptoms from patient input
    - **conditions**: Array of identified medical conditions
    - **specialties_needed**: Recommended medical specialties for treatment
    - **predicted_icd10**: Primary ICD-10 diagnosis code
    - **icd10_description**: Human-readable description of the ICD-10 code
    - **treatment_options**: Array of treatment options, each with:
      - `name`: Treatment procedure name
      - `outcomes`: Expected results and success rates
      - `complications`: Potential risks and complications
      - `category`: One of "Surgery", "Radiosurgery", "Endovascular", or "Other"
    - **search_query**: Optimized search string for specialist information retrieval queries (used later for finding relevant medical content)
    - **diagnoses_prompt_text**: The actual GPT prompt that was used to generate the diagnoses (useful for debugging/regeneration)
    - **cpt_codes**: Empty array initially - CPT codes are generated separately via `/api/v1/cpt-codes/generate` endpoint (required before specialist search)

---

### **PHASE 5: Results Page - Medical Analysis Display (ResultsPage.tsx)**

13. **User sees medical analysis results**:
    - Treatment options
    - Predicted diagnoses
    - Other medical insights
    - **Note**: CPT codes are not shown yet - they must be generated in the next step

---

### **PHASE 6: CPT Code Generation (ResultsPage.tsx)**

14. **Required: Generate CPT codes** (before specialist search):
    - User must click "Generate CPT Codes" button
    - Calls `/api/v1/medical-analysis/cpt-codes` endpoint
    - Updates CPT codes in state
    - **UI enforcement**: The "Show me suggested specialists" button only appears after CPT codes are generated
    - The entire CPT codes section (including the button) is conditionally rendered - it doesn't exist in the DOM until CPT codes are present
    - **Required sequence**: Medical Analysis → Generate CPT Codes → Show Specialists

---

### **PHASE 7: Provider Search (ResultsPage.tsx - handleShowSpecialists)**

15. **User clicks "Show me suggested specialists" button** (only visible after CPT codes are generated):
    - **Dependency enforcement**: The button is conditionally rendered - it only appears when CPT codes exist
    - **Runtime safety check**: Even if the button is clicked, the handler validates CPT codes exist before proceeding

16. **Frontend calls `getSpecialistRecommendations()` API** (`/api/v1/specialist-recommendations`):
    - **Request payload**:
      - Symptoms, Diagnosis (still needed for patient_input string)
      - Medical history, Medications, Surgical history
      - State
      - **Medical analysis results (reused from step 11 to avoid duplicate GPT calls)**:
        - Treatment options
        - Predicted ICD-10 code
        - ICD-10 description
        - Search query
        - Determined specialty
      - CPT codes (reused from medical analysis to avoid duplicate generation)
      - Files: empty array
    - **This is a POST request with FormData**
    - **Optimization**: All medical analysis results are passed through, avoiding expensive duplicate GPT API calls

17. **Frontend calls `searchNPIProviders()` API** (`/api/v1/npi/search-providers`):
    - **Request payload**:
      - State, City, ZIP code, Proximity
      - Diagnosis, Symptoms
      - Uploaded files: empty array
      - **Required**: Must pass `determined_specialty` from medical analysis (no fallback)
      - **Optional**: Also passes `predicted_icd10` and `icd10_description` from medical analysis
        - These values are extracted from `searchParams` or `aiRecommendations.patient_profile`
        - All values come from medical analysis step - no duplicate GPT API calls
    - **This is a POST request with FormData** (multipart/form-data)
    - **Note**: If `determined_specialty` is missing, the request will fail with an error message

---

### **PHASE 8: Backend NPI Provider Search (npi.py endpoint)**

18. **Endpoint receives request** at `/api/v1/npi/search-providers`

19. **Use pre-determined values from medical analysis** (required):
    - **Uses `determined_specialty`** (required) from medical analysis step
      - If missing, returns error - these values must come from medical analysis
    - **Uses `predicted_icd10` and `icd10_description`** (optional but recommended) from medical analysis step
      - If missing, logs warning but continues (specialty is main filtering criteria)
    - **No fallback logic**: The system always relies on values from medical analysis step
      - This ensures consistency and avoids duplicate GPT API calls

20. **Taxonomy code mapping**:
    - Converts specialty name to taxonomy codes using `get_taxonomy_codes_for_specialty()`
    - Uses the pre-determined specialty from step 19 (always from medical analysis)
    - Example: "Neurological Surgery" → `['207T00000X']`

21. **Database query**:
    - Builds SQL query filtering by:
      - Entity type = '1' (individual providers only)
      - Taxonomy codes (matches any of 15 possible taxonomy code fields)
      - State (if proximity is "statewide")
    - Orders by last name, first name
    - No LIMIT clause - fetches all matching providers

22. **Provider enrichment**:
    For each provider found:
    - **Education data** (with fallback logic):
      - First tries US News data (`usnews_data` table)
      - Falls back to Healthgrades data (`healthgrades_data` table) per field
      - Fields: medical_school, residency, fellowship, certifications
    - **Years of experience**:
      - Extracts latest year from residency text
      - Calculates: current_year - graduation_year
    - **Exclusion check**:
      - Checks `exclusions` table by NPI
      - If not found, checks by first name + last name
      - Sets `isExcluded` flag if found

23. **Response formatting**:
    - Returns JSON with:
      - `total_providers`: Count of filtered providers
      - `providers`: Array of provider objects with all details
      - `search_criteria`: Determined specialty, predicted ICD-10, etc.

---

### **PHASE 9: Backend Specialist Recommendations (specialist_recommendation.py endpoint)**

24. **Endpoint receives request** at `/api/v1/specialist-recommendations`

25. **Service initialization**:
    - Creates `SpecialistRecommendationService` instance

26. **Medical analysis** (reuses results from previous analysis - required, no fallback):
    - **Uses pre-generated medical analysis results** from step 11 to avoid duplicate GPT calls:
      - Treatment options (reused - required)
      - Predicted ICD-10 code (reused - required)
      - ICD-10 description (reused)
      - Search query (reused - required)
      - Determined specialty (reused)
      - CPT codes (reused)
    - **No GPT calls are made** - all values are passed through from the first medical analysis step
    - **Required fields validation**: If required medical analysis results (treatment_options, predicted_icd10, search_query) are missing, raises ValueError - no fallback to re-running analysis

27. **Specialist information retrieval**:
    - Calls `specialist_information_retrieval_service.retrieve_specialist_information()`:
      - Uses Postgres database
      - Searches for relevant medical content (VuMedi videos, PubMed articles)
      - Uses the generated search query from medical analysis
      - Retrieves all matching results (no limit)
    - Returns treatment-specific specialist information

28. **CMS data retrieval**:
    - Queries CMS provider data for clinical volume information using CPT codes from step 14 (CPT code generation)
    - Extracts Tot_Srvcs (total services) for providers

29. **Response construction**:
    - Converts specialist information to recommendations
    - Includes:
      - `patient_profile`: Treatment options, CPT codes, search query, etc.
      - `recommendations`: Specialist recommendations
      - `shared_specialist_information`: Treatment-grouped specialist data
      - `cms_data`: CMS provider data
      - `search_query`: Pre-generated query for specialist information retrieval

---

### **PHASE 10: Frontend Ranking (ResultsPage.tsx)**

30. **After both specialist recommendations and NPI data are received**:

31. **Call `rankNPIProviders()` API** (`/api/v1/npi/rank-npi-providers`):
    - **Request payload**:
      - `npi_providers`: Array of provider objects from NPI search
      - `patient_input`: Combined symptoms and diagnosis
      - `shared_specialist_information`: From specialist recommendations
      - `search_query`: From medical analysis (same as used for PubMed)
      - `cms_data`: CMS data (if available)

---

### **PHASE 11: Backend NPI Ranking (npi_ranking.py endpoint)**

32. **Endpoint receives request** at `/api/v1/npi/rank-npi-providers`

33. **Extract CMS Tot_Srvcs data**:
    - Extracts NPI → Tot_Srvcs mapping from CMS data
    - Used for clinical volume scoring

34. **Initialize specialist recommendation service**:
    - Creates `SpecialistRecommendationService` instance

35. **Call ranking method**:
    - `specialist_service.rank_npi_providers_with_specialist_data()`:
      - Takes NPI providers, patient input, shared specialist info
      - Uses treatment-specific specialist data
      - Ranks providers per treatment option

36. **Ranking process** (in `ranking_service.py`):
    - **For each treatment option**:
      - **Extract treatment-specific specialist data**
      - **Match provider names** with specialist content:
        - VuMedi videos (doctor names in "featuring" field)
        - PubMed articles (author names)
      - **Calculate scores** for each provider:
        - **PubMed score**: Based on PubMed article matches (weighted by author position and journal quartile)
        - **VuMedi score**: Based on VuMedi video matches
        - **Medical school score**: Based on US News rankings
        - **Certification score**: Based on board certifications
        - **Clinical volume score**: Based on CMS Tot_Srvcs (percentage-based)
        - **Combined score**: Weighted combination of all factors
      - **Sort by final score** (descending)

37. **Response formatting**:
    - Returns:
      - `treatment_rankings`: Object keyed by treatment ID
        - Each treatment contains:
          - `ranked_providers`: Array of NPI numbers in ranked order
          - `provider_links`: VuMedi links and PubMed articles per provider
          - `provider_scores`: Detailed scoring breakdown per provider
      - `total_treatments`: Number of treatments processed

---

### **PHASE 12: Frontend Result Processing (ResultsPage.tsx)**

38. **Process ranking response**:
    - Extracts first treatment's ranking (can be filtered later)
    - Maps ranked NPI numbers back to full provider objects
    - Captures provider links and scores

39. **Update state with ranked providers**:
    - Saves complete search state:
      - Search parameters (state, city, symptoms, diagnosis, etc.)
      - Ranked providers
      - Treatment rankings

40. **Switch to specialists view**:
    - Updates `searchParams` to mark specialists as enabled
    - Sets `activeView` to 'specialists'
    - Displays ranked providers

---

### **PHASE 13: Results Page Initialization (ResultsPage.tsx)**

41. **Component mounts** and receives location.state

42. **Load data from location.state**:
    - Sets providers state
    - Sets search parameters
    - Sets medical analysis data (from initial medical analysis API response)
    - Sets ranking data
    - Sets treatment rankings

43. **Fallback to localStorage** (if location.state is missing):
    - Attempts to load from `mdspecialist_search_results` in localStorage
    - Useful for page refresh scenarios

44. **Determine initial view**:
    - If `searchOptions.specialists` is true → 'specialists' view
    - If `searchOptions.diagnosis` is true → 'assessment' view
    - Otherwise → 'assessment' view (default)

45. **Initialize treatment selection**:
    - If treatment rankings exist, selects first treatment by default
    - Sets `selectedTreatmentId`

---

### **PHASE 14: Results Display (ResultsPage.tsx)**

46. **Provider filtering and pagination**:
    - Filters providers by:
      - Search term (name search)
      - Category (if filtering by treatment category)
    - Paginates results (default: 20 per page)

47. **Provider card rendering**:
    - For each provider in current page:
      - Calculates display score and breakdown
      - Determines if provider is "top result" (rank 1)
      - Renders `NPIProviderCard` component with:
        - Provider information (name, address, phone, etc.)
        - Score and score breakdown
        - Education details
        - Provider links (VuMedi videos, PubMed articles)
        - Certification status
        - Red flags (if any)
        - Patient diagnosis and symptoms (for context)

48. **Score calculation** (for display):
    - Retrieves score data from `providerScores` state
    - Breakdown includes:
      - PubMed points (weighted by author position and journal quartile)
      - VuMedi points
      - Medical school points
      - Certification points
      - Clinical volume points
      - Total score

49. **Additional UI elements**:
    - Treatment option selector (if multiple treatments)
    - Category filter (Surgery, Radiosurgery, Endovascular, Other)
    - Search bar for filtering providers by name
    - Pagination controls
    - View switcher (Medical Assessment, Specialists, Debug)

---

### **PHASE 15: User Interaction (ResultsPage.tsx)**

50. **User can interact with results** (optional interactions that can happen at any time):
    - **Click provider card**: Opens detailed view (if implemented)
    - **Filter by category**: Shows only providers for specific treatment category
    - **Search by name**: Filters providers by name
    - **Change page**: Navigates through paginated results
    - **Switch views**: Toggle between Medical Assessment, Specialists, Debug

---

## Key Data Structures

### Provider Object
```typescript
{
  id: string,              // NPI number
  npi: string,             // NPI number
  name: string,            // "First Last"
  specialty: string,       // "Neurological Surgery"
  address: string,
  city: string,
  state: string,
  zip: string,
  phone: string,
  yearsExperience: number,
  boardCertified: boolean | null,
  acceptingPatients: boolean,
  isExcluded: boolean,
  education: {
    medicalSchool: string | null,
    residency: string | null,
    fellowship: string | null,
    certifications: string | null
  }
}
```

### Ranking Response
```typescript
{
  treatment_rankings: {
    [treatmentId: string]: {
      ranked_providers: string[],  // NPI numbers in order
      provider_links: {
        [npi: string]: {
          vumedi_content: Array<{link: string, title: string}>,
          pubmed_articles: Array<{pmid: string, title: string}>
        }
      },
      provider_scores: {
        [npi: string]: {
          score: number,
          pubmed_points: number,
          vumedi_points: number,
          medical_school_points: number,
          certification_points: number,
          clinical_volume_points: number,
          breakdown: {...}
        }
      }
    }
  },
  total_treatments: number
}
```

### Specialist Recommendations Response
```typescript
{
  patient_profile: {
    treatment_options: Array<{
      name: string,
      outcomes: string,
      complications: string,
      category: string
    }>,
    cpt_codes: Array<{code: string, description: string}>,
    predicted_icd10: string,
    icd10_description: string,
    search_query: string,
    specialties_needed: string[]
  },
  recommendations: SpecialistRecommendation[],
  shared_specialist_information: {
    [treatmentId: string]: {
      vumedi: [...],
      pubmed: [...]
    }
  },
  cms_data: {
    results: Array<{
      Rndrng_NPI: string,
      Tot_Srvcs: number,
      ...
    }>
  },
  search_query: string
}
```

---

## Database Tables Used

1. **npi_providers**: Main provider database
2. **usnews_data**: Medical school and education data
3. **healthgrades_data**: Fallback education data
4. **exclusions**: Providers to exclude from results
5. **healthgrades_reviews**: Patient reviews (optional, for future use)

---

## External Services

1. **PostgreSQL**: Database for medical content (VuMedi videos, PubMed articles)
2. **OpenAI GPT-5-mini**: AI model for:
   - Specialty determination
   - Diagnosis prediction
   - Medical analysis
3. **CMS Data**: Clinical volume information (Tot_Srvcs)

---

## Error Handling

- **Frontend**: Shows alerts for validation errors and API failures
- **Backend**: Returns error responses with details
- **Ranking failures**: Falls back to original provider order
- **Missing data**: Uses fallback sources (e.g., Healthgrades if US News unavailable)

---

## Performance Considerations

- **NPI search**: Fetches all matching providers (no limit)
- **Specialist information retrieval**: All matching results per treatment (no limit)
- **Pagination**: 20 providers per page on results
- **Caching**: Results stored in localStorage for persistence
- **Parallel processing**: Some API calls can be made in parallel (if not dependent)

---

## Future Enhancements

- Distance-based filtering (currently only state-based)
- Insurance network filtering
- Availability/accepting patients filtering
- Review integration
- Advanced filtering options
- Export results functionality

---

