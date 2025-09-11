from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...services.match_service import MatchService
from ...schemas.match import MatchRequest, MatchResponse

router = APIRouter()

@router.post("/match", response_model=MatchResponse)
async def match_doctors(
    match_request: MatchRequest,
    db: Session = Depends(get_db)
):
    """
    Match patients with doctors based on diagnosis and location.
    
    This endpoint takes a patient's diagnosis and location preferences
    and returns a ranked list of matching doctors based on objective criteria.
    """
    try:
        match_service = MatchService(db)
        result = match_service.match_doctors(match_request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to match doctors: {str(e)}"
        )

@router.get("/suggestions/diagnosis")
async def get_diagnosis_suggestions(
    query: str,
    db: Session = Depends(get_db)
):
    """Get diagnosis suggestions based on partial input."""
    try:
        match_service = MatchService(db)
        suggestions = match_service.get_match_suggestions(query)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get diagnosis suggestions: {str(e)}"
        )

@router.get("/suggestions/metro")
async def get_metro_suggestions(
    query: str,
    db: Session = Depends(get_db)
):
    """Get metro area suggestions based on partial input."""
    try:
        match_service = MatchService(db)
        suggestions = match_service.get_metro_suggestions(query)
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metro suggestions: {str(e)}"
        )
