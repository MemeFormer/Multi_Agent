# src/models/review_feedback.py
from typing import Optional
from pydantic import BaseModel

class ReviewFeedback(BaseModel):
    """
    Represents the feedback from a review process, indicating approval
    and optional reasoning.
    """
    approved: bool
    reasoning: Optional[str] = None
