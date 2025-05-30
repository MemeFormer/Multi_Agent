# src/models/word_action_plan.py
from pydantic import BaseModel, Field
from typing import Literal, Optional

class WordActionPlan(BaseModel):
    """
    Plan generated by the Planner Agent for the Word Game.
    Instructs the Executor Agent on which bin to place the word in.
    """
    word_to_process: str = Field(..., description="The original word received.")
    target_bin: Literal["Vowel Bin", "Consonant Bin"] = Field(..., description="The designated bin based on the first letter.")
    reasoning: Optional[str] = Field(None, description="Optional brief explanation from the Planner.") # Optional reasoning field