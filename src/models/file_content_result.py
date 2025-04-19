# src/models/file_content_result.py
"""
Defines the Pydantic model for the result of a file read action.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict

class FileContentResult(BaseModel):
    """
    Result reported by the Executor after attempting to read a file.
    Includes file path, status, content, and optionally line-numbered content.
    """
    file_path: str = Field(..., description="The path to the file that was attempted to be read.")
    status: Literal["Success", "Failure"] = Field(..., description="The outcome of the read attempt.")
    content: Optional[str] = Field(None, description="The content of the file if successfully read, otherwise None.")
    lines: Optional[Dict[int, str]] = Field(None, description="File content represented as a dictionary with 1-based line numbers as keys and line text as values.")
    message: Optional[str] = Field(None, description="An optional message, e.g., an error description if status is Failure.")