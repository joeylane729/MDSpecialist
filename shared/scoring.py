"""
Shared scoring utilities for ConciergeMD.
Contains functions to calculate doctor grades based on objective criteria.
"""

from typing import Dict, List, Any
import math


def calculate_publication_score(publications: List[Dict[str, Any]]) -> float:
    """
    Calculate publication score based on number and quality of publications.
    
    Args:
        publications: List of publication dictionaries with 'type' and 'year' keys
        
    Returns:
        Float score from 0-100
    """
    if not publications:
        return 0.0
    
    score = 0.0
    
    for pub in publications:
        pub_type = pub.get('type', 'other').lower()
        year = pub.get('year', 2024)
        current_year = 2024
        
        # Base points for publication type
        type_points = {
            'peer_reviewed': 10,
            'journal_article': 8,
            'book_chapter': 6,
            'conference_paper': 4,
            'case_study': 3,
            'other': 2
        }
        
        base_points = type_points.get(pub_type, 2)
        
        # Recency bonus (more recent = higher score)
        years_ago = current_year - year
        if years_ago <= 2:
            recency_multiplier = 1.5
        elif years_ago <= 5:
            recency_multiplier = 1.2
        elif years_ago <= 10:
            recency_multiplier = 1.0
        else:
            recency_multiplier = 0.8
            
        score += base_points * recency_multiplier
    
    # Cap at 100
    return min(score, 100.0)


def calculate_training_score(education: Dict[str, Any]) -> float:
    """
    Calculate training score based on medical education and training.
    
    Args:
        education: Dictionary containing education information
        
    Returns:
        Float score from 0-100
    """
    score = 0.0
    
    # Medical school ranking (simplified)
    med_school_tier = education.get('med_school_tier', 'unknown')
    tier_scores = {
        'top_10': 25,
        'top_25': 20,
        'top_50': 15,
        'top_100': 10,
        'other': 5,
        'unknown': 0
    }
    score += tier_scores.get(med_school_tier, 0)
    
    # Residency program ranking
    residency_tier = education.get('residency_tier', 'unknown')
    score += tier_scores.get(residency_tier, 0)
    
    # Fellowship programs
    fellowships = education.get('fellowships', [])
    for fellowship in fellowships:
        fellowship_tier = fellowship.get('tier', 'unknown')
        score += tier_scores.get(fellowship_tier, 0) * 0.5  # Fellowships worth half
    
    # Board certifications
    board_certs = education.get('board_certifications', [])
    score += len(board_certs) * 5
    
    # Years of experience
    years_exp = education.get('years_experience', 0)
    if years_exp >= 20:
        score += 20
    elif years_exp >= 15:
        score += 15
    elif years_exp >= 10:
        score += 10
    elif years_exp >= 5:
        score += 5
    
    return min(score, 100.0)


def calculate_experience_score(experience: Dict[str, Any]) -> float:
    """
    Calculate experience score based on clinical and research experience.
    
    Args:
        experience: Dictionary containing experience information
        
    Returns:
        Float score from 0-100
    """
    score = 0.0
    
    # Clinical experience
    clinical_years = experience.get('clinical_years', 0)
    score += min(clinical_years * 2, 30)  # Max 30 points for clinical
    
    # Research experience
    research_years = experience.get('research_years', 0)
    score += min(research_years * 1.5, 20)  # Max 20 points for research
    
    # Teaching experience
    teaching_years = experience.get('teaching_years', 0)
    score += min(teaching_years, 15)  # Max 15 points for teaching
    
    # Leadership roles
    leadership_roles = experience.get('leadership_roles', [])
    score += len(leadership_roles) * 3  # 3 points per leadership role
    
    # Awards and honors
    awards = experience.get('awards', [])
    score += len(awards) * 2  # 2 points per award
    
    return min(score, 100.0)


def calculate_online_presence_score(online_data: Dict[str, Any]) -> float:
    """
    Calculate online presence score based on website mentions, reviews, etc.
    
    Args:
        online_data: Dictionary containing online presence information
        
    Returns:
        Float score from 0-100
    """
    score = 0.0
    
    # Website mentions
    website_mentions = online_data.get('website_mentions', 0)
    score += min(website_mentions * 0.5, 20)  # Max 20 points
    
    # Patient reviews
    patient_reviews = online_data.get('patient_reviews', [])
    if patient_reviews:
        avg_rating = sum(review.get('rating', 0) for review in patient_reviews) / len(patient_reviews)
        score += avg_rating * 4  # Max 40 points for 5-star average
    
    # Social media presence
    social_media = online_data.get('social_media', {})
    for platform, followers in social_media.items():
        if followers > 10000:
            score += 5
        elif followers > 5000:
            score += 3
        elif followers > 1000:
            score += 1
    
    # Professional directory listings
    directory_listings = online_data.get('directory_listings', [])
    score += len(directory_listings) * 2
    
    return min(score, 100.0)


def calculate_location_score(doctor_location: Dict[str, Any], patient_location: Dict[str, Any]) -> float:
    """
    Calculate location score based on distance and accessibility.
    
    Args:
        doctor_location: Dictionary containing doctor's location
        patient_location: Dictionary containing patient's location
        
    Returns:
        Float score from 0-100 (100 = same location, decreases with distance)
    """
    # For now, return a simplified score based on metro area match
    doctor_metro = doctor_location.get('metro_area', '').lower()
    patient_metro = patient_location.get('metro_area', '').lower()
    
    if doctor_metro == patient_metro:
        return 100.0
    
    # Check if in same state
    doctor_state = doctor_location.get('state', '').lower()
    patient_state = patient_location.get('state', '').lower()
    
    if doctor_state == patient_state:
        return 80.0
    
    # Check if in same region
    regions = {
        'northeast': ['ny', 'ma', 'ct', 'ri', 'nh', 'vt', 'me', 'nj', 'pa'],
        'southeast': ['fl', 'ga', 'sc', 'nc', 'va', 'wv', 'ky', 'tn', 'al', 'ms', 'ar'],
        'midwest': ['il', 'in', 'mi', 'oh', 'wi', 'mn', 'ia', 'mo', 'nd', 'sd', 'ne', 'ks'],
        'southwest': ['tx', 'ok', 'nm', 'az'],
        'west': ['ca', 'or', 'wa', 'id', 'nv', 'ut', 'co', 'wy', 'mt', 'ak', 'hi']
    }
    
    for region, states in regions.items():
        if doctor_state in states and patient_state in states:
            return 60.0
    
    return 40.0


def calculate_overall_grade(doctor_data: Dict[str, Any], patient_location: Dict[str, Any]) -> str:
    """
    Calculate overall grade (A+ to F) based on all criteria.
    
    Args:
        doctor_data: Dictionary containing all doctor information
        patient_location: Dictionary containing patient's location
        
    Returns:
        String grade from A+ to F
    """
    # Calculate individual scores
    pub_score = calculate_publication_score(doctor_data.get('publications', []))
    training_score = calculate_training_score(doctor_data.get('education', {}))
    experience_score = calculate_experience_score(doctor_data.get('experience', {}))
    online_score = calculate_online_presence_score(doctor_data.get('online_presence', {}))
    location_score = calculate_location_score(doctor_data.get('location', {}), patient_location)
    
    # Weight the scores
    weighted_score = (
        pub_score * 0.25 +           # 25% - Publications
        training_score * 0.25 +      # 25% - Training
        experience_score * 0.25 +    # 25% - Experience
        online_score * 0.15 +        # 15% - Online presence
        location_score * 0.10        # 10% - Location
    )
    
    # Convert to letter grade
    if weighted_score >= 95:
        return "A+"
    elif weighted_score >= 90:
        return "A"
    elif weighted_score >= 85:
        return "A-"
    elif weighted_score >= 80:
        return "B+"
    elif weighted_score >= 75:
        return "B"
    elif weighted_score >= 70:
        return "B-"
    elif weighted_score >= 65:
        return "C+"
    elif weighted_score >= 60:
        return "C"
    elif weighted_score >= 55:
        return "C-"
    elif weighted_score >= 50:
        return "D+"
    elif weighted_score >= 45:
        return "D"
    elif weighted_score >= 40:
        return "D-"
    else:
        return "F"


def rank_doctors(doctors: List[Dict[str, Any]], patient_location: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Rank doctors based on overall score and location preference.
    
    Args:
        doctors: List of doctor dictionaries
        patient_location: Dictionary containing patient's location
        
    Returns:
        List of doctors sorted by rank (highest first)
    """
    for doctor in doctors:
        doctor['overall_grade'] = calculate_overall_grade(doctor, patient_location)
        doctor['overall_score'] = _grade_to_numeric(doctor['overall_grade'])
    
    # Sort by overall score (descending) and then by location score
    sorted_doctors = sorted(
        doctors,
        key=lambda x: (x['overall_score'], x.get('location_score', 0)),
        reverse=True
    )
    
    # Add rank
    for i, doctor in enumerate(sorted_doctors):
        doctor['rank'] = i + 1
    
    return sorted_doctors


def _grade_to_numeric(grade: str) -> float:
    """Convert letter grade to numeric value for sorting."""
    grade_map = {
        'A+': 4.3, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'D-': 0.7,
        'F': 0.0
    }
    return grade_map.get(grade, 0.0)
