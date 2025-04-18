# src/models/check_plan.py
"""
Defines the Pydantic model for planning a bin check action.
"""

from pydantic import BaseModel, Field
from typing import Literal

class CheckPlan(BaseModel):
    """
    Represents the plan to check if a specific word exists in a designated bin.
    """
    action: Literal["check_bin"] = Field(..., description="Specifies the action to check the bin.")
    word: str = Field(..., description="The word to check for in the bin.")
    bin_name: Literal["Vowel Bin", "Consonant Bin"] = Field(..., description="The specific bin to check.")
