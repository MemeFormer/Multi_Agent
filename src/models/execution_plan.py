# src/models/execution_plan.py
from pydantic import BaseModel

class ExecutionPlan(BaseModel):
    """
    Represents a proposed command and its description.
    """
    command: str
    description: str
