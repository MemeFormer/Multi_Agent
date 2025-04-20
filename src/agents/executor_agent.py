# src/agents/executor_agent.py

import logging
import asyncio
import os
from typing import Dict, Optional, List, Literal, Tuple

from src.adapters.groq_adapter import GroqAdapter
from src.models.word_action_plan import WordActionPlan
from src.models.execution_result import ExecutionResult
from src.models.check_plan import CheckPlan
from src.models.check_result import CheckResult
from src.models.read_file_plan import ReadFilePlan       # <-- Added for Phase 5
from src.models.file_content_result import FileContentResult # <-- Added for Phase 5
from src.models.write_file_plan import WriteFilePlan     # <-- Added for Phase 6
from src.models.write_file_result import WriteFileResult # <-- Added for Phase 6
from src.models.apply_patch_plan import ApplyPatchPlan   # <-- Added for Phase 9
from src.models.apply_patch_result import ApplyPatchResult # <-- Added for Phase 9

# Import patch tool components
from src.tools.patch_tool import (
    text_to_patch,
    patch_to_commit,
    apply_commit,
    identify_files_needed,
    DiffError # Import the specific error type
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

class ExecutorAgent:
    """
    Agent responsible for executing specific actions based on a received plan.
    Manages bin files and performs file operations via internal tools.
    """
    def __init__(self, adapter: GroqAdapter, model_id: str, data_dir: str = "data"):
        self.adapter = adapter
        self.model_id = model_id # Store for potential future LLM use in executor
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.bin_files = {
            "Vowel Bin": os.path.join(self.data_dir, "vowel_bin.txt"),
            "Consonant Bin": os.path.join(self.data_dir, "consonant_bin.txt")
        }
        logger.info(f"ExecutorAgent initialized. Using bin files: {self.bin_files}")
        self._initialize_bin_files() # Ensure files are ready

    def _initialize_bin_files(self):
        """Ensures bin files exist and are empty for a fresh run."""
        logger.debug("Initializing/clearing bin files...")
        try:
            for file_path in self.bin_files.values():
                with open(file_path, 'w') as f: pass # Create/truncate
            logger.debug("Bin files initialized/cleared.")
        except OSError as e:
            logger.error(f"Error initializing bin files: {e}", exc_info=True)

    # --- Internal Tool Methods ---

    def _read_bin_file(self, file_path: str) -> list[str]:
        """Reads all lines from a bin file, strips whitespace, and returns them."""
        lines = []
        try:
            if not os.path.exists(file_path):
                 logger.warning(f"File not found during read: {file_path}. Returning empty list.")
                 return []
            with open(file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            logger.debug(f"Read {len(lines)} lines from {file_path}")
        except OSError as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            return []
        return lines

    def _find_word_in_file(self, word: str, file_path: str) -> bool:
        """Checks if a specific word exists in the given file."""
        logger.debug(f"Checking for word '{word}' in file {file_path}")
        lines = self._read_bin_file(file_path)
        found = word in lines
        logger.debug(f"Word '{word}' found in {file_path}: {found}")
        return found

    def _append_word_to_file(self, word: str, file_path: str) -> bool:
        """Appends a word as a new line to the specified file."""
        logger.debug(f"Appending word '{word}' to file {file_path}")
        try:
            with open(file_path, 'a') as f:
                f.write(word + '\n')
            logger.debug(f"Successfully appended '{word}' to {file_path}")
            return True
        except OSError as e:
            logger.error(f"Error appending word '{word}' to file {file_path}: {e}", exc_info=True)
            return False

    def _read_file_content(self, file_path: str) -> Tuple[Optional[str], Optional[Dict[int, str]]]:
        """Reads the entire content of a file, returning it as a string and a line-number dict."""
        logger.debug(f"Attempting to read content and lines from: {file_path}")
        content: Optional[str] = None
        lines_dict: Optional[Dict[int, str]] = None
        
        if not os.path.exists(file_path):
            logger.error(f"File not found for reading: {file_path}")
            return None, None # Return tuple on failure
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Generate line-numbered dictionary
            lines_list = content.splitlines() # Splits lines, removes trailing newlines from strings
            lines_dict = {i + 1: line for i, line in enumerate(lines_list)}
            
            logger.debug(f"Successfully read {len(content)} characters and {len(lines_dict)} lines from {file_path}.")
            return content, lines_dict # Return tuple on success
            
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error reading file content from {file_path}: {e}", exc_info=True)
            return None, None # Return tuple on failure
        except Exception as e:
            logger.error(f"Unexpected error reading file {file_path}: {e}", exc_info=True)
            return None, None # Return tuple on failure

    def _write_file_content(self, file_path: str, content: str) -> bool:
        """Writes the given content to the file, overwriting existing content."""
        logger.debug(f"Attempting to write {len(content)} characters to: {file_path}")
        try:
            # Ensure the directory exists (it should from __init__, but defensive check)
            # Handle cases where file_path might be just a filename in the current dir
            dir_name = os.path.dirname(file_path)
            if dir_name: # Only create if dirname is not empty (i.e., not current dir)
                 os.makedirs(dir_name, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Successfully wrote content to {file_path}")
            return True
        except (OSError, TypeError) as e: # Catch file errors or if content isn't string
            logger.error(f"Error writing content to file {file_path}: {e}", exc_info=True)
            return False
        except Exception as e: # Catch unexpected errors
            logger.error(f"Unexpected error writing file {file_path}: {e}", exc_info=True)
            return False

    def _remove_file(self, file_path: str) -> bool:
        """Removes the specified file. Returns True if successful or file already gone, False on error."""
        logger.debug(f"Attempting to remove file: {file_path}")
        try:
            os.remove(file_path)
            logger.info(f"Successfully removed file: {file_path}")
            return True
        except FileNotFoundError:
            logger.warning(f"File not found during removal (considered success): {file_path}")
            return True # File is already gone, which is the desired state
        except OSError as e:
            logger.error(f"Error removing file {file_path}: {e}", exc_info=True)
            return False
        except Exception as e: # Catch unexpected errors
            logger.error(f"Unexpected error removing file {file_path}: {e}", exc_info=True)
            return False

    # --- Public Execution Methods ---

    async def execute_check(self, plan: CheckPlan) -> CheckResult:
        """ Executes a check plan using the _find_word_in_file tool. """
        logger.info(f"Executor Agent received check plan: Check '{plan.word}' in '{plan.bin_name}' file using tool.")
        status: Literal["Present", "Not Present"] = "Not Present" # Default
        try:
            file_path = self.bin_files.get(plan.bin_name)
            if not file_path:
                logger.error(f"Invalid bin name '{plan.bin_name}' provided. Cannot find file path.")
                # Consistent error return handled below
                raise ValueError(f"Invalid bin name: {plan.bin_name}")

            word_found = self._find_word_in_file(plan.word, file_path)
            status = "Present" if word_found else "Not Present"
            logger.info(f"Tool-based check result for '{plan.word}' in '{plan.bin_name}': {status}")

        except Exception as e:
            logger.error(f"Error during check execution (using tool) for word '{plan.word}': {e}", exc_info=True)
            status = "Not Present" # Or introduce an "Error" status? Defaulting for safety.

        return CheckResult(
            word=plan.word,
            bin_checked=plan.bin_name,
            status=status
        )

    async def execute_add(self, plan: WordActionPlan) -> ExecutionResult:
        """ Executes an add plan using _find_word_in_file and _append_word_to_file tools. """
        logger.info(f"Executor Agent received add plan: Add '{plan.word_to_process}' to '{plan.target_bin}' using tools.")
        try:
            file_path = self.bin_files.get(plan.target_bin)
            if not file_path:
                logger.error(f"Invalid target bin '{plan.target_bin}' specified. Cannot find file path.")
                return ExecutionResult(status="Failure", message=f"Invalid target bin '{plan.target_bin}'")

            logger.debug(f"Performing pre-add check for '{plan.word_to_process}' in {file_path} using tool.")
            already_exists = self._find_word_in_file(plan.word_to_process, file_path)

            if already_exists:
                message = f"Word '{plan.word_to_process}' already exists. Add action skipped by Executor."
                logger.warning(message)
                return ExecutionResult(status="Success", message=message)

            logger.info(f"Executing add action using tool: Appending '{plan.word_to_process}' to file '{file_path}'...")
            append_success = self._append_word_to_file(plan.word_to_process, file_path)
            # await asyncio.sleep(0.01) # No longer needed as tool is synchronous

            if append_success:
                message = f"Successfully appended '{plan.word_to_process}' to '{plan.target_bin}' file using tool."
                logger.info(message)
                return ExecutionResult(status="Success", message=message)
            else:
                message = f"Failed to append '{plan.word_to_process}' to '{plan.target_bin}' file using tool."
                logger.error(message)
                return ExecutionResult(status="Failure", message=message)

        except Exception as e:
            error_message = f"Error during add execution (using tools) for word '{plan.word_to_process}': {e}"
            logger.error(error_message, exc_info=True)
            return ExecutionResult(status="Failure", message=error_message)

    async def execute_read_file(self, plan: ReadFilePlan) -> FileContentResult:
        """ Executes a read file plan using the _read_file_content tool. """
        logger.info(f"Executor Agent received plan: Read file '{plan.file_path}' using tool.")
        content: Optional[str] = None
        lines_dict: Optional[Dict[int, str]] = None
        message: Optional[str] = None
        status: Literal["Success", "Failure"] = "Failure"

        try:
            content, lines_dict = self._read_file_content(plan.file_path)

            if content is not None and lines_dict is not None:
                status = "Success"
                message = f"Successfully read {len(content)} characters ({len(lines_dict)} lines) from file: {plan.file_path}"
                logger.info(message)
            else:
                status = "Failure"
                message = f"Failed to read file content/lines from: {plan.file_path}. Tool returned None."
                logger.warning(message)
                content = None
                lines_dict = None

        except Exception as e:
            status = "Failure"
            content = None
            lines_dict = None
            message = f"Unexpected error during file read execution for {plan.file_path}: {e}"
            logger.error(message, exc_info=True)

        return FileContentResult(
            file_path=plan.file_path,
            status=status,
            content=content,
            lines=lines_dict,
            message=message
        )

    async def execute_write_file(self, plan: WriteFilePlan) -> WriteFileResult:
        """ Executes a write file plan using the _write_file_content tool. """
        logger.info(f"Executor Agent received plan: Write file '{plan.file_path}' using tool.")
        success: bool = False
        message: Optional[str] = None
        status: Literal["Success", "Failure"] = "Failure"
        bytes_written: Optional[int] = None

        try:
            # --- Use Internal Tool ---
            success = self._write_file_content(plan.file_path, plan.content)

            if success:
                status = "Success"
                try:
                    # Calculate bytes after successful write
                    bytes_written = len(plan.content.encode('utf-8'))
                    message = f"Successfully wrote {bytes_written} bytes to file: {plan.file_path}"
                    logger.info(message)
                except Exception as enc_e: # Handle potential encoding errors during calculation
                    logger.error(f"Error encoding content to calculate bytes for {plan.file_path}: {enc_e}", exc_info=True)
                    message = f"Successfully wrote content to file: {plan.file_path} (byte count unavailable)."
                    # Status remains Success, but message reflects the issue
            else:
                # Error should have been logged by the tool method
                status = "Failure"
                message = f"Failed to write content to: {plan.file_path}. Tool returned False."
                logger.warning(message)

        except Exception as e:
            # Catch unexpected errors during execution phase
            status = "Failure"
            message = f"Unexpected error during file write execution for {plan.file_path}: {e}"
            logger.error(message, exc_info=True)

        # --- Return Result ---
        return WriteFileResult(
            file_path=plan.file_path,
            status=status,
            message=message,
            bytes_written=bytes_written # Will be None if write failed or byte count failed
        )

    async def execute_apply_patch(self, plan: ApplyPatchPlan) -> ApplyPatchResult:
        """ Executes an apply patch plan using the patch_tool logic. """
        logger.info(f"Executor Agent received plan: Apply patch described as: {plan.reasoning or 'No reasoning provided'}")
        original_files: Dict[str, str] = {}
        file_results: Optional[Dict[str, str]] = None

        try:
            # 1. Identify files needed for the patch
            logger.debug("Identifying files needed for the patch...")
            needed_files = identify_files_needed(plan.patch_content)
            logger.info(f"Patch requires access to files: {needed_files}")

            # 2. Load original content of needed files
            for file_path in needed_files:
                logger.debug(f"Reading original content of: {file_path}")
                content, _ = self._read_file_content(file_path) # Ignore lines dict for now
                if content is None:
                    # If a required file cannot be read, the patch cannot be applied safely.
                    error_msg = f"Failed to read required file for patching: {file_path}"
                    logger.error(error_msg)
                    return ApplyPatchResult(
                        status="Failure",
                        message=error_msg,
                        error_details=f"Could not read file content for {file_path}."
                    )
                original_files[file_path] = content
            logger.info(f"Successfully loaded content for {len(original_files)} required files.")

            # 3. Define local I/O wrappers for the synchronous patch tool functions
            def write_wrapper(path: str, content: str) -> bool:
                # Note: Calling sync tool from within async method context
                logger.debug(f"[Wrapper] Writing file: {path}")
                return self._write_file_content(path, content)

            def remove_wrapper(path: str) -> bool:
                # Note: Calling sync tool from within async method context
                logger.debug(f"[Wrapper] Removing file: {path}")
                return self._remove_file(path)

            # 4. Parse the patch text
            logger.debug("Parsing patch content...")
            parsed_patch, fuzz = text_to_patch(plan.patch_content, original_files)
            logger.info(f"Patch parsed successfully. Fuzz factor: {fuzz}")

            # 5. Convert patch actions to commit actions
            logger.debug("Converting parsed patch to commit actions...")
            commit_actions = patch_to_commit(parsed_patch, original_files)
            logger.info(f"Commit created with {len(commit_actions.changes)} changes.")

            # 6. Apply the commit using the wrappers
            logger.info("Applying commit actions to the filesystem...")
            file_results = apply_commit(commit_actions, write_wrapper, remove_wrapper)
            logger.info(f"Commit application finished. Results per file: {file_results}")

            # 7. Determine overall status based on file results
            has_errors = False
            has_success = False
            for status in file_results.values():
                if "Error" in status:
                    has_errors = True
                else:
                    # Consider "Deleted", "Added", "Updated", "Moved" as success indicators
                    has_success = True

            final_status: Literal["Success", "Failure", "Partial Success"]
            final_message: str

            if has_errors and has_success:
                final_status = "Partial Success"
                final_message = "Patch applied with some errors."
                logger.warning(final_message)
            elif has_errors and not has_success:
                final_status = "Failure"
                final_message = "Patch application failed for all targeted files."
                logger.error(final_message)
            elif not has_errors and has_success:
                 final_status = "Success"
                 final_message = "Patch applied successfully to all targeted files."
                 logger.info(final_message)
            else: # No errors, no successes (e.g., empty patch or only targeting non-existent files for delete)
                 final_status = "Success" # Consider this success as no errors occurred
                 final_message = "Patch application completed without errors (no changes might have been needed)."
                 logger.info(final_message)


            return ApplyPatchResult(
                status=final_status,
                message=final_message,
                file_results=file_results
            )

        except DiffError as e:
            error_msg = f"Patch Error: {e}"
            logger.error(error_msg, exc_info=True)
            return ApplyPatchResult(
                status="Failure",
                message="Failed to parse or apply patch due to format/content error.",
                file_results=file_results, # Include partial results if available
                error_details=str(e)
            )
        except Exception as e:
            error_msg = f"Unexpected error during patch execution: {e}"
            logger.error(error_msg, exc_info=True)
            return ApplyPatchResult(
                status="Failure",
                message="An unexpected error occurred during patch application.",
                file_results=file_results, # Include partial results if available
                error_details=str(e)
            )
