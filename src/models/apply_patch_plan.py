# src/models/apply_patch_plan.py

from pydantic import BaseModel, Field
from typing import Literal, Optional

class ApplyPatchPlan(BaseModel):
    """Plan instructing the Executor to apply a V4A formatted patch."""

    action: Literal["apply_patch"] = Field(..., description="Specifies the action to apply a V4A patch.")
    patch_content: str = Field(..., description="The full V4A patch content string (including Begin/End Patch sentinels).")
    reasoning: Optional[str] = Field(None, description="Optional reasoning from the Planner about why this patch is needed.")
