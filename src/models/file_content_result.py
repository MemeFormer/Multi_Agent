# src/models/file_content_result.py
"""
Defines the Pydantic model for the result of a file read action.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional

class FileContentResult(BaseModel):
    """
    Result reported by the Executor after attempting to read a file.
    """
    file_path: str = Field(..., description="The path to the file that was attempted to be read.")
    status: Literal["Success", "Failure"] = Field(..., description="The outcome of the read attempt.")
    content: Optional[str] = Field(None, description="The content of the file if successfully read, otherwise None.")
    message: Optional[str] = Field(None, description="An optional message, e.g., an error description if status is Failure.")
