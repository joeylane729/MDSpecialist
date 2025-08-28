"""
Test script for the specialist recommendation system.

This script tests the core functionality of the specialist recommendation service
without requiring the full FastAPI application to be running.
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(__file__))
sys.path.append(backend_dir)

from app.services.specialist_recommendation_service import SpecialistRecommendationService
from app.services.patient_data_processor import PatientDataProcessor
from app.services.retrieval_strategies import RetrievalStrategies
from app.services.specialist_ranking_service import SpecialistRankingService
from app.services.pinecone_service import PineconeService
from app.models.specialist_recommendation import PatientProfile, SpecialistRecommendation, RecommendationResponse

async def test_patient_data_processor():
    """Test patient data processing functionality."""
    print("🧪 Testing Patient Data Processor...")
    
    processor = PatientDataProcessor()
    
    # Test case 1: Chest pain
    patient_input = "I have chest pain and shortness of breath. I think I need to see a cardiologist."
    profile = await processor.process_patient_input(
        patient_input=patient_input,
        location_preference="New York",
        urgency_level="high"
    )
    
    print(f"✅ Processed patient input:")
    print(f"   Symptoms: {profile.symptoms}")
    print(f"   Conditions: {profile.conditions}")
    print(f"   Specialties needed: {profile.specialties_needed}")
    print(f"   Urgency level: {profile.urgency_level}")
    print(f"   Location preference: {profile.location_preference}")
    print()
    
    return profile

async def test_pinecone_connection():
    """Test Pinecone connection and basic functionality."""
    print("🧪 Testing Pinecone Connection...")
    
    try:
        pinecone_service = PineconeService()
        
        # Test connection
        connection_result = pinecone_service.test_connection()
        print(f"✅ Pinecone connection: {connection_result['status']}")
        
        # Get index stats
        index = pinecone_service.pc.Index(pinecone_service.default_index_name)
        stats = index.describe_index_stats()
        print(f"✅ Index stats: {stats.total_vector_count} vectors")
        print()
        
        return pinecone_service
        
    except Exception as e:
        print(f"❌ Pinecone connection failed: {str(e)}")
        return None

async def test_retrieval_strategies(pinecone_service):
    """Test retrieval strategies."""
    print("🧪 Testing Retrieval Strategies...")
    
    if not pinecone_service:
        print("❌ Skipping retrieval test - Pinecone not available")
        return []
    
    try:
        # Create a test patient profile
        processor = PatientDataProcessor()
        profile = await processor.process_patient_input(
            patient_input="I need a cardiologist for chest pain",
            location_preference="New York"
        )
        
        # Test retrieval
        retrieval = RetrievalStrategies(pinecone_service)
        candidates = await retrieval.retrieve_specialists(profile, top_k=5)
        
        print(f"✅ Retrieved {len(candidates)} candidates")
        if candidates:
            print(f"   First candidate: {candidates[0].get('title', 'No title')}")
            print(f"   Specialty: {candidates[0].get('specialty', 'Unknown')}")
        print()
        
        return candidates
        
    except Exception as e:
        print(f"❌ Retrieval test failed: {str(e)}")
        return []

async def test_ranking_service(candidates):
    """Test specialist ranking service."""
    print("🧪 Testing Specialist Ranking Service...")
    
    if not candidates:
        print("❌ Skipping ranking test - No candidates available")
        return []
    
    try:
        # Create a test patient profile
        processor = PatientDataProcessor()
        profile = await processor.process_patient_input(
            patient_input="I need a cardiologist for chest pain"
        )
        
        # Test ranking
        ranking = SpecialistRankingService()
        recommendations = await ranking.rank_specialists(candidates, profile, top_n=3)
        
        print(f"✅ Ranked {len(recommendations)} recommendations")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec.name} - {rec.specialty}")
            print(f"      Confidence: {rec.confidence_score:.2f}")
            print(f"      Reasoning: {rec.reasoning}")
        print()
        
        return recommendations
        
    except Exception as e:
        print(f"❌ Ranking test failed: {str(e)}")
        return []

async def test_full_pipeline():
    """Test the complete specialist recommendation pipeline."""
    print("🧪 Testing Full Specialist Recommendation Pipeline...")
    
    try:
        # Initialize service
        service = SpecialistRecommendationService()
        
        # Test recommendation request
        response = await service.get_specialist_recommendations(
            patient_input="I have chest pain and shortness of breath. I need to see a cardiologist in New York.",
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
            print(f"   Top recommendation: {response.recommendations[0].name}")
            print(f"   Specialty: {response.recommendations[0].specialty}")
            print(f"   Confidence: {response.recommendations[0].confidence_score:.2f}")
        
        print()
        return response
        
    except Exception as e:
        print(f"❌ Full pipeline test failed: {str(e)}")
        return None

async def main():
    """Run all tests."""
    print("🚀 Starting Specialist Recommendation System Tests")
    print("=" * 60)
    
    # Test 1: Patient Data Processor
    profile = await test_patient_data_processor()
    
    # Test 2: Pinecone Connection
    pinecone_service = await test_pinecone_connection()
    
    # Test 3: Retrieval Strategies
    candidates = await test_retrieval_strategies(pinecone_service)
    
    # Test 4: Ranking Service
    recommendations = await test_ranking_service(candidates)
    
    # Test 5: Full Pipeline
    full_response = await test_full_pipeline()
    
    # Summary
    print("📊 Test Summary:")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 5
    
    if profile:
        tests_passed += 1
        print("✅ Patient Data Processor: PASSED")
    else:
        print("❌ Patient Data Processor: FAILED")
    
    if pinecone_service:
        tests_passed += 1
        print("✅ Pinecone Connection: PASSED")
    else:
        print("❌ Pinecone Connection: FAILED")
    
    if candidates:
        tests_passed += 1
        print("✅ Retrieval Strategies: PASSED")
    else:
        print("❌ Retrieval Strategies: FAILED")
    
    if recommendations:
        tests_passed += 1
        print("✅ Ranking Service: PASSED")
    else:
        print("❌ Ranking Service: FAILED")
    
    if full_response:
        tests_passed += 1
        print("✅ Full Pipeline: PASSED")
    else:
        print("❌ Full Pipeline: FAILED")
    
    print(f"\n🎯 Overall Result: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! The specialist recommendation system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the error messages above for details.")

if __name__ == "__main__":
    asyncio.run(main())
