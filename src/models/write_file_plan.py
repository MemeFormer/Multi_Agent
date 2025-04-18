# src/models/write_file_plan.py

from pydantic import BaseModel, Field
from typing import Literal

class WriteFilePlan(BaseModel):
    """
    Plan instructing the Executor to write specific content to a file,
    overwriting any existing content.
    """
    action: Literal["write_file"] = Field(
        ...,
        description="Specifies the action to write content to a file."
    )
    file_path: str = Field(
        ...,
        description="The path to the file to be written."
    )
    content: str = Field(
        ...,
        description="The new content to write to the file."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "action": "write_file",
                    "file_path": "path/to/your/file.txt",
                    "content": "This is the new content for the file.\nIt can span multiple lines."
                }
            ]
        }
    }
