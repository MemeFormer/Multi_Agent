# prototype_v7.0_diffedit.py
import asyncio
import logging
import os
from typing import Optional # <-- Added import

from src.adapters.groq_adapter import GroqAdapter
from src.agents.planner_agent import PlannerAgent
from src.agents.executor_agent import ExecutorAgent
from src.models.read_file_plan import ReadFilePlan
from src.models.file_content_result import FileContentResult
from src.models.apply_patch_plan import ApplyPatchPlan
from src.models.apply_patch_result import ApplyPatchResult

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("src.tools.patch_tool").setLevel(logging.INFO) # Adjust if needed
logging.getLogger("src.agents.planner_agent").setLevel(logging.DEBUG)


PLANNER_MODEL =  "deepseek-r1-distill-llama-70b"      #"llama3-70b-8192"
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # Executor doesn't use LLM for patch apply

async def main():
    logging.info("--- Starting Prototype V7.0: Diff-Based Edit Task ---")

    try:
        adapter = GroqAdapter()
        # Increase max_tokens for planner if patches might be large
        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL, max_tokens=3000)
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL) # Executor model not used for patch apply
        logging.info("Adapter and Agents initialized.")
    except Exception as e:
        logging.critical(f"Initialization failed: {e}", exc_info=True)
        return

    # --- Define Target File, Initial Content, and Modification ---
    target_file = os.path.join(executor.data_dir, "test_diff_edit.txt")
    initial_content = """Line 1: Some original content.
Line 2: The second line.
Line 3: Another line here.
Line 4: End of original file.
"""
    # Example Modification Request: Insert a line
    modification_request = "Insert a new line 'Line 2.5: Inserted via V4A patch.' between Line 2 and Line 3."
    # Example Modification Request: Modify a line
    # modification_request = "In Line 1, change 'original' to 'modified'."
    # Example Modification Request: Delete a line
    # modification_request = "Delete Line 3."

    # --- Setup Initial File State ---
    logging.info(f"Setting up initial content for '{target_file}'...")
    setup_success = executor._write_file_content(target_file, initial_content)
    if not setup_success:
        logging.error("Failed to set up initial file content. Aborting.")
        return
    logging.info(f"Initial content written to {target_file}.")
    logging.info(f"Modification Request: {modification_request}")

    # --- Workflow Variables ---
    original_content: Optional[str] = None
    apply_patch_plan: Optional[ApplyPatchPlan] = None
    apply_patch_result: Optional[ApplyPatchResult] = None

    try:
        # 1. Plan and Execute Read
        logging.info("Step 1: Reading initial file content...")
        read_plan = await planner.plan_read_file_task(target_file)
        if not read_plan: raise ValueError("Planner failed to create read plan.")
        read_result = await executor.execute_read_file(read_plan)
        if read_result.status != "Success" or read_result.content is None:
            raise ValueError(f"Executor failed to read file: {read_result.message}")
        original_content = read_result.content
        logging.info(f"Successfully read original content ({len(original_content)} chars).")

        # 2. Plan Apply Patch
        logging.info("Step 2: Planning V4A patch based on request...")
        apply_patch_plan = await planner.plan_apply_patch_task(
            target_file, original_content, modification_request
        )
        if not apply_patch_plan:
            raise ValueError("Planner failed to create apply patch plan.")
        logging.info(f"Apply patch plan created.")
        # Log preview of patch content
        patch_preview = apply_patch_plan.patch_content.replace('\n', '\\n')[:300] + "..."
        logging.debug(f"Generated Patch Content Preview:\n{patch_preview}")


        # 3. Execute Apply Patch
        logging.info("Step 3: Executing apply patch...")
        apply_patch_result = await executor.execute_apply_patch(apply_patch_plan)
        if not apply_patch_result: # Should always return an object
             raise ValueError("Executor failed to return any result for apply patch.")
        logging.info(f"Patch application result: Status={apply_patch_result.status}, Msg={apply_patch_result.message}")
        if apply_patch_result.file_results:
             logging.info(f"Detailed File Results: {apply_patch_result.file_results}")
        if apply_patch_result.status == "Failure":
             # Log error details if available, otherwise the message
             error_info = apply_patch_result.error_details or apply_patch_result.message
             raise ValueError(f"Executor reported failure applying patch: {error_info}")
        elif apply_patch_result.status == "Partial Success":
             logging.warning("Patch application completed with partial success. Check file results.")
             # Decide if this should halt the process or continue to verification
             # For now, let's continue to verification


    except Exception as e:
        logging.error(f"Workflow failed: {e}", exc_info=True)

    # --- Verification Step ---
    logging.info("--- Verification Step ---")
    try:
        if os.path.exists(target_file):
            actual_content, actual_lines = executor._read_file_content(target_file)
            if actual_content is not None:
                logging.info(f"Successfully read back file: {target_file}")
                logging.info(f"Final content:\n{actual_content}")
                # Add specific checks based on the modification_request
                if "Insert a new line 'Line 2.5" in modification_request:
                     expected_line = "Line 2.5: Inserted via V4A patch."
                     # Check if the line exists and is roughly in the right place
                     expected_sequence = "Line 2: The second line.\nLine 2.5: Inserted via V4A patch.\nLine 3: Another line here."
                     if expected_line in actual_content and expected_sequence in actual_content:
                          logging.info("Verification successful: Expected inserted line found in correct sequence.")
                     elif expected_line in actual_content:
                          logging.warning("Verification warning: Expected inserted line found, but sequence might be off.")
                     else:
                          logging.error("Verification FAILED: Expected inserted line NOT found.")
                elif "change 'original' to 'modified'" in modification_request:
                     expected_line = "Line 1: Some modified content."
                     if expected_line in actual_content.splitlines()[0]: # Check first line specifically
                          logging.info("Verification successful: Expected modified line found.")
                     else:
                          logging.error("Verification FAILED: Expected modified line NOT found.")
                elif "Delete Line 3" in modification_request:
                      deleted_line = "Line 3: Another line here."
                      if deleted_line not in actual_content:
                           logging.info("Verification successful: Expected deleted line is gone.")
                      else:
                           logging.error("Verification FAILED: Expected deleted line IS STILL PRESENT.")
                else:
                     logging.warning("Verification skipped: Unknown modification request type.")
            else:
                logging.error(f"Verification error: Could not read back file {target_file}")
        else:
             # If the request was to delete the file, this might be expected
             if "Delete File:" in (apply_patch_plan.patch_content if apply_patch_plan else ""):
                  logging.info(f"Verification: Target file {target_file} correctly deleted as per patch plan.")
             else:
                  logging.error(f"Verification error: Target file {target_file} does not exist after workflow (and wasn't planned for deletion).")
    except Exception as e:
        logging.error(f"Verification error during read back: {e}", exc_info=True)

    logging.info("--- Prototype V7.0 Finished ---")


if __name__ == "__main__":
    asyncio.run(main())
