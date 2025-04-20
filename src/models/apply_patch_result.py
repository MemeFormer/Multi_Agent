# src/models/apply_patch_result.py

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict

class ApplyPatchResult(BaseModel):
    """Result reported by the Executor after attempting to apply a V4A patch."""

    status: Literal["Success", "Failure", "Partial Success"] = Field(..., description="Overall outcome of the patch application attempt.")
    message: str = Field(..., description="A summary message describing the outcome (e.g., 'Patch applied successfully', 'Error applying patch', 'Patch applied with errors').")
    file_results: Optional[Dict[str, str]] = Field(None, description="Optional dictionary mapping affected file paths to their individual status (e.g., 'Updated', 'Added', 'Deleted', 'Error'). Provided by the apply_commit function.")
    error_details: Optional[str] = Field(None, description="Specific error message if status is Failure.")
