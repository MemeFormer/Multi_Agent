# src/models/execution_result.py
from pydantic import BaseModel, Field
from typing import Literal

class ExecutionResult(BaseModel):
    """
    Result reported back by the Executor Agent after attempting an action.
    """
    status: Literal["Success", "Failure"] = Field(..., description="Outcome of the execution attempt.")
    message: str = Field(..., description="A message detailing the outcome (e.g., confirmation or error).")