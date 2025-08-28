# Specialist Recommendation System

A LangChain-powered specialist recommendation system that uses Pinecone vector database to match patients with relevant medical specialists from the Vumedi medical video content dataset.

## Overview

This system processes patient input (symptoms, conditions, preferences) and returns ranked specialist recommendations using multiple retrieval strategies and intelligent scoring. The system is built on top of the Vumedi medical video content dataset, which contains medical education videos featuring individual doctors and specialists.

## Data Source

The system uses the **Vumedi medical video content dataset** loaded into Pinecone, which contains:
- **86,729 medical education videos** from various medical institutions
- **Individual doctor names** in the `featuring` field (e.g., "POULINA UDDIN", "ARSHA KARBASSI")
- **Medical institutions** in the `author` field (e.g., "SCRIPPS HEALTH", "MCMASTER UNIVERSITY")
- **Specialty information** (Cardiology, Neurology, Dermatology, etc.)
- **Video metadata** (title, duration, views, date, etc.)

**Key Fields:**
- `featuring`: Individual doctor/specialist names (used for recommendations)
- `author`: Medical institution/hospital names
- `specialty`: Medical specialty area
- `title`: Video title describing the medical content
- `chunk_text`: Combined text for semantic search

## Architecture

### Core Components

1. **SpecialistRecommendationService** - Main orchestration service
2. **PatientDataProcessor** - Processes and structures patient input
3. **RetrievalStrategies** - Multiple retrieval approaches from Pinecone
4. **SpecialistRankingService** - Ranks and scores specialist candidates
5. **API Endpoints** - FastAPI endpoints for the service

### Data Flow

```
Patient Input → Patient Processing → Multi-Strategy Retrieval → Ranking → Recommendations
```

## Features

- **Multi-Strategy Retrieval**: Vector similarity, metadata filtering, specialty-specific, and hybrid search
- **Intelligent Ranking**: Multi-criteria scoring based on relevance, expertise, availability, and preferences
- **Patient Data Processing**: Extracts symptoms, conditions, and specialty needs from free text
- **Configurable Scoring**: Adjustable weights for different ranking criteria
- **Comprehensive API**: RESTful endpoints for all functionality

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_pinecone_environment
```

## Usage

### Basic Usage

```python
from app.services.specialist_recommendation_service import SpecialistRecommendationService

# Initialize service
service = SpecialistRecommendationService()

# Get recommendations
response = await service.get_specialist_recommendations(
    patient_input="I have chest pain and shortness of breath",
    location_preference="New York",
    urgency_level="high",
    max_recommendations=5
)

# Access results
for recommendation in response.recommendations:
    print(f"{recommendation.name} - {recommendation.specialty}")
    print(f"Confidence: {recommendation.confidence_score:.2f}")
    print(f"Reasoning: {recommendation.reasoning}")
```

### API Usage

```bash
# Get specialist recommendations
curl -X POST "http://localhost:8000/specialist-recommendation/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_input": "I have chest pain and shortness of breath",
    "location_preference": "New York",
    "urgency_level": "high",
    "max_recommendations": 5
  }'

# Search specialists by specialty
curl -X POST "http://localhost:8000/specialist-recommendation/search" \
  -H "Content-Type: application/json" \
  -d '{
    "specialty": "cardiology",
    "location": "New York",
    "top_k": 10
  }'

# Get service statistics
curl "http://localhost:8000/specialist-recommendation/stats"
```

## Testing

Run the test script to verify functionality:

```bash
python test_specialist_recommendation.py
```

This will test:
- Patient data processing
- Pinecone connection
- Retrieval strategies
- Ranking service
- Full pipeline

## Configuration

### Ranking Criteria Weights

```python
from app.services.specialist_ranking_service import RankingCriteria

# Customize ranking weights
criteria = RankingCriteria(
    relevance_weight=0.4,      # How relevant to patient needs
    expertise_weight=0.3,      # Specialist qualifications
    availability_weight=0.1,   # Appointment availability
    location_weight=0.1,       # Location proximity
    patient_preference_weight=0.1  # Patient preferences
)
```

### Retrieval Strategy Configuration

```python
from app.services.retrieval_strategies import RetrievalStrategies

# Configure retrieval weights
retrieval.vector_search_weight = 0.6
retrieval.metadata_filter_weight = 0.4
retrieval.specialty_boost_factor = 1.2
```

## API Endpoints

### POST `/specialist-recommendation/recommendations`
Get specialist recommendations for a patient.

**Request Body:**
```json
{
  "patient_input": "string",
  "location_preference": "string (optional)",
  "insurance_preference": "string (optional)",
  "urgency_level": "low|medium|high|emergency",
  "max_recommendations": 10
}
```

### GET `/specialist-recommendation/specialist/{specialist_id}`
Get detailed information about a specific specialist.

### POST `/specialist-recommendation/search`
Search for specialists by specialty and location.

### GET `/specialist-recommendation/stats`
Get service statistics and Pinecone index information.

### GET `/specialist-recommendation/health`
Health check endpoint.

## Data Models

### PatientProfile
- `symptoms`: List of patient symptoms
- `conditions`: List of medical conditions
- `specialties_needed`: Required medical specialties
- `urgency_level`: Urgency of the case
- `location_preference`: Preferred location
- `insurance_preference`: Insurance requirements

### SpecialistRecommendation
- `specialist_id`: Unique identifier (derived from Vumedi video link)
- `name`: Individual doctor name (from `featuring` field)
- `specialty`: Medical specialty (from Vumedi data)
- `relevance_score`: Relevance to patient (0-1)
- `confidence_score`: Overall confidence (0-1)
- `reasoning`: Human-readable explanation
- `metadata`: Full Vumedi video record (author, title, link, etc.)

## Performance

- **Processing Time**: Typically 800-900ms for full pipeline (including Pinecone search)
- **Retrieval**: Supports up to 50 initial candidates from 86,729 total records
- **Ranking**: Configurable top-N recommendations (default: top 3)
- **Scalability**: Designed for high-throughput production use
- **Data Volume**: 86,729 medical education videos indexed in Pinecone

## Monitoring

The system provides comprehensive logging and monitoring:

- Processing time tracking
- Retrieval strategy usage
- Error handling and reporting
- Service health checks
- Performance metrics

## Example Output

When you run the system with patient input like "I have chest pain and shortness of breath", you get recommendations like:

```
Top 3 Specialist Recommendations:
1. JAMES CIRONE - Cardiology, Pulmonology
   Confidence: 0.42
   Reasoning: Moderately relevant to your case.

2. CHRISTOPHER NIELSEN - Cardiology  
   Confidence: 0.39
   Reasoning: Moderately relevant to your case.

3. EVAN SHALEN - Adult & Family Medicine, Cardiology
   Confidence: 0.39
   Reasoning: Moderately relevant to your case.
```

These are actual doctor names from the Vumedi dataset who have created educational content in the relevant medical specialties.

## Technical Implementation Details

### Pinecone Integration
- **Index**: `concierge-md-dev` (86,729 vectors)
- **Embedding Model**: `llama-text-embed-v2` (1024 dimensions)
- **Search Method**: `index.search()` with integrated embeddings
- **Query Format**: `{"inputs": {"text": "search query"}, "top_k": 50}`
- **Response Format**: `results.result.hits[].fields`

### Retrieval Strategies
1. **Vector Similarity Search**: Semantic search using patient symptoms/conditions
2. **Metadata Filter Search**: Filter by specialty, location, etc.
3. **Specialty-Specific Search**: Direct specialty matching
4. **Hybrid Search**: Combines multiple strategies with deduplication

### Data Processing
- **Patient Input**: Free text → structured symptoms, conditions, specialties
- **Deduplication**: Uses `link` field as unique identifier (Vumedi videos)
- **Ranking**: Multi-criteria scoring (relevance, expertise, availability, location)

## Future Enhancements

- Real-time availability integration
- Insurance network validation  
- Appointment scheduling integration
- Patient feedback and learning
- Advanced NLP for symptom extraction
- Multi-language support
- Integration with additional medical databases
- Doctor contact information and scheduling links
