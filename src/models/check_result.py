# src/models/check_result.py
"""
Defines the Pydantic model for the result of a bin check action.
"""

from pydantic import BaseModel, Field
from typing import Literal

class CheckResult(BaseModel):
    """
    Represents the outcome of checking for a word in a specific bin.
    """
    word: str = Field(..., description="The word that was checked.")
    bin_checked: Literal["Vowel Bin", "Consonant Bin"] = Field(..., description="The bin where the check was performed.")
    status: Literal["Present", "Not Present"] = Field(..., description="Result of the check - whether the word was found in the bin.")
