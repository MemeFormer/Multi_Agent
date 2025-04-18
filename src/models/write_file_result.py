# src/models/write_file_result.py

from pydantic import BaseModel, Field
from typing import Literal, Optional

class WriteFileResult(BaseModel):
    """
    Result reported by the Executor after attempting to write to a file.
    """
    file_path: str = Field(
        ...,
        description="The path to the file where writing was attempted."
    )
    status: Literal["Success", "Failure"] = Field(
        ...,
        description="The outcome of the write attempt."
    )
    message: Optional[str] = Field(
        None,
        description="An optional message, e.g., confirmation or error description."
    )
    bytes_written: Optional[int] = Field(
        None,
        description="Number of bytes written if successful."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "file_path": "path/to/your/file.txt",
                    "status": "Success",
                    "message": "Successfully wrote 65 bytes to path/to/your/file.txt",
                    "bytes_written": 65
                },
                {
                    "file_path": "path/to/nonexistent/dir/file.txt",
                    "status": "Failure",
                    "message": "Error writing content to file path/to/nonexistent/dir/file.txt: [Errno 2] No such file or directory: 'path/to/nonexistent/dir/file.txt'",
                    "bytes_written": None
                }
            ]
        }
    }
