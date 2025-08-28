"""
Test LangChain Specialist Recommendation System
"""

import asyncio
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.services.pinecone_service import PineconeService
from app.services.langchain_patient_processor import LangChainPatientProcessor
from app.services.langchain_retrieval_strategies import LangChainRetrievalStrategies
from app.services.langchain_ranking_service import LangChainRankingService
from app.services.langchain_specialist_recommendation_service import LangChainSpecialistRecommendationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_patient_processor():
    """Test LangChain patient data processor."""
    print("🧪 Testing LangChain Patient Data Processor...")
    
    try:
        processor = LangChainPatientProcessor()
        profile = await processor.process_patient_input(
            patient_input="I have chest pain and shortness of breath",
            location_preference="New York",
            urgency_level="high"
        )
        
        print(f"✅ Processed patient input:")
        print(f"   Symptoms: {profile.symptoms}")
        print(f"   Conditions: {profile.conditions}")
        print(f"   Specialties needed: {profile.specialties_needed}")
        print(f"   Urgency level: {profile.urgency_level}")
        print(f"   Location preference: {profile.location_preference}")
        
        return profile
        
    except Exception as e:
        print(f"❌ Patient processor test failed: {str(e)}")
        return None

async def test_pinecone_connection():
    """Test Pinecone connection."""
    print("🧪 Testing Pinecone Connection...")
    
    try:
        service = PineconeService()
        success = service.test_connection()
        
        if success:
            index = service.pc.Index(service.default_index_name)
            stats = index.describe_index_stats()
            print(f"✅ Pinecone connection: success")
            print(f"✅ Index stats: {stats.total_vector_count} vectors")
            return True
        else:
            print("❌ Pinecone connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Pinecone test failed: {str(e)}")
        return False

async def test_retrieval_strategies(patient_profile):
    """Test LangChain retrieval strategies."""
    print("🧪 Testing LangChain Retrieval Strategies...")
    
    try:
        pinecone_service = PineconeService()
        retrieval = LangChainRetrievalStrategies(pinecone_service)
        
        specialist_information = await retrieval.retrieve_specialist_information(
            patient_profile=patient_profile,
            top_k=5
        )
        
        print(f"✅ Retrieved {len(specialist_information)} specialist information records")
        if specialist_information:
            first = specialist_information[0]
            print(f"   First record: {first.get('title', 'Unknown')}")
            print(f"   Specialty: {first.get('specialty', 'Unknown')}")
        
        return specialist_information
        
    except Exception as e:
        print(f"❌ Retrieval test failed: {str(e)}")
        return []

async def test_ranking_service(specialist_information, patient_profile):
    """Test LangChain ranking service."""
    print("🧪 Testing LangChain Ranking Service...")
    
    if not specialist_information:
        print("❌ Skipping ranking test - No specialist information available")
        return []
    
    try:
        ranking = LangChainRankingService()
        recommendations = await ranking.rank_specialists_from_information(
            specialist_information=specialist_information,
            patient_profile=patient_profile,
            top_n=3
        )
        
        print(f"✅ Ranked {len(recommendations)} recommendations")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec.name} - {rec.specialty}")
            print(f"      Confidence: {rec.confidence_score:.2f}")
            print(f"      Reasoning: {rec.reasoning}")
        
        return recommendations
        
    except Exception as e:
        print(f"❌ Ranking test failed: {str(e)}")
        return []

async def test_full_pipeline():
    """Test full LangChain pipeline."""
    print("🧪 Testing Full LangChain Specialist Recommendation Pipeline...")
    
    try:
        service = LangChainSpecialistRecommendationService()
        
        response = await service.get_specialist_recommendations(
            patient_input="I have chest pain and shortness of breath",
            location_preference="New York",
            urgency_level="high",
            max_recommendations=3
        )
        
        print(f"✅ Full pipeline test completed:")
        print(f"   Processing time: {response.processing_time_ms}ms")
        print(f"   Total candidates found: {response.total_candidates_found}")
        print(f"   Recommendations returned: {len(response.recommendations)}")
        print(f"   Strategies used: {response.retrieval_strategies_used}")
        
        if response.recommendations:
            top_rec = response.recommendations[0]
            print(f"   Top recommendation: {top_rec.name}")
            print(f"   Specialty: {top_rec.specialty}")
            print(f"   Confidence: {top_rec.confidence_score:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Full pipeline test failed: {str(e)}")
        return False

async def main():
    """Run all tests."""
    print("🚀 Starting LangChain Specialist Recommendation System Tests")
    print("=" * 60)
    
    # Test 1: Patient Data Processor
    patient_profile = await test_patient_processor()
    
    # Test 2: Pinecone Connection
    pinecone_ok = await test_pinecone_connection()
    
    # Test 3: Retrieval Strategies
    specialist_information = []
    if patient_profile and pinecone_ok:
        specialist_information = await test_retrieval_strategies(patient_profile)
    
    # Test 4: Ranking Service
    recommendations = []
    if specialist_information and patient_profile:
        recommendations = await test_ranking_service(specialist_information, patient_profile)
    
    # Test 5: Full Pipeline
    pipeline_ok = await test_full_pipeline()
    
    # Summary
    print("\n📊 Test Summary:")
    print("=" * 60)
    
    tests = [
        ("Patient Data Processor", patient_profile is not None),
        ("Pinecone Connection", pinecone_ok),
        ("Retrieval Strategies", len(specialist_information) > 0),
        ("Ranking Service", len(recommendations) > 0),
        ("Full Pipeline", pipeline_ok)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The LangChain specialist recommendation system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the error messages above for details.")

if __name__ == "__main__":
    asyncio.run(main())
