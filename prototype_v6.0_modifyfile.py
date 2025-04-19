# prototype_v6.0_modifyfile.py
import asyncio
import logging
import os
from typing import Optional, Dict

from src.adapters.groq_adapter import GroqAdapter
from src.agents.planner_agent import PlannerAgent
from src.agents.executor_agent import ExecutorAgent
from src.models.read_file_plan import ReadFilePlan
from src.models.file_content_result import FileContentResult
from src.models.write_file_plan import WriteFilePlan
from src.models.write_file_result import WriteFileResult

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
PLANNER_MODEL = "deepseek-r1-distill-llama-70b"
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

async def main():
    logging.info("--- Starting Prototype V6.0: Read-Modify-Write Task ---")
    try:
        adapter = GroqAdapter()
        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL)
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL)
        logging.info("Adapter and Agents initialized.")
    except Exception as e:
        logging.critical(f"Initialization failed: {e}", exc_info=True)
        return

    # --- Define Target File and Initial Content ---
    target_file = os.path.join(executor.data_dir, "test_output.txt")
    initial_content = "Line 1: Original content.\nLine 2: Before modification.\n"
    modification_marker = "-- Modified by Planner (v8) --"

    # --- Setup Initial File State (using executor's tool directly) ---
    logging.info(f"Ensuring target file '{target_file}' exists with initial content...")
    setup_success = executor._write_file_content(target_file, initial_content)
    if not setup_success:
        logging.error("Failed to set up initial file content. Aborting.")
        return
    logging.info("Initial content written successfully.")

    # --- Workflow Variables ---
    original_content: Optional[str] = None
    original_lines: Optional[Dict[int, str]] = None  # Add variable for lines dictionary
    modify_write_plan: Optional[WriteFilePlan] = None
    final_write_result: Optional[WriteFileResult] = None

    try:
        # 1. Plan Read
        logging.info(f"Step 1: Planning to read {target_file}...")
        read_plan = await planner.plan_read_file_task(target_file)
        if not read_plan: 
            raise ValueError("Planner failed to create read plan.")
            
        # 2. Execute Read
        logging.info("Step 2: Executing file read...")
        read_result = await executor.execute_read_file(read_plan)
        if read_result.status != "Success" or read_result.content is None or read_result.lines is None:
            raise ValueError(f"Executor failed to read file/lines: {read_result.message}")
            
        original_content = read_result.content
        original_lines = read_result.lines  # Store the lines dictionary
        logging.info(f"Successfully read original content ({len(original_content)} chars, {len(original_lines)} lines).")
        
        # 3. Plan Modify (Outputting a WriteFilePlan)
        logging.info("Step 3: Planning modification...")
        modify_write_plan = await planner.plan_modify_file_task(target_file, original_content)
        if not modify_write_plan:
            raise ValueError("Planner failed to create modification plan.")
            
        logging.info(f"Modification plan created. Proposed content length: {len(modify_write_plan.content)}")
        
        # 4. Execute Write (with modified content)
        logging.info("Step 4: Executing write with modified content...")
        final_write_result = await executor.execute_write_file(modify_write_plan)
        if final_write_result.status != "Success":
            raise ValueError(f"Executor failed to write modified file: {final_write_result.message}")
            
        logging.info(f"Successfully executed write. Result: {final_write_result.message}")
        
    except Exception as e:
        logging.error(f"Workflow failed: {e}", exc_info=True)
        # Optionally add more detailed error reporting based on which step failed

    # --- Verification Step ---
    logging.info("--- Verification Step ---")
    try:
        if os.path.exists(target_file):
            # Use the executor's tool to read back content AND lines for verification
            actual_content, actual_lines_dict = executor._read_file_content(target_file)
            if actual_content is not None and actual_lines_dict is not None:
                logging.info(f"Successfully read back file: {target_file} ({len(actual_lines_dict)} lines)")
                logging.info(f"Actual content after modification:\n{actual_content}")
                
                # Verification logic using line numbers
                expected_marker = "-- Modified by Planner (v8) --"
                original_last_line_num = len(original_lines) if original_lines else 0
                expected_marker_line_num = original_last_line_num + 1
                marker_found = False
                
                if expected_marker_line_num in actual_lines_dict and actual_lines_dict[expected_marker_line_num] == expected_marker:
                    marker_found = True
                    logging.info(f"Verification successful: Found '{expected_marker}' at expected line {expected_marker_line_num}.")
                else:
                    # Check if it exists on *any* line (fallback check)
                    if any(line == expected_marker for line in actual_lines_dict.values()):
                        logging.warning(f"Verification warning: Found '{expected_marker}', but not at the expected line {expected_marker_line_num}.")
                        marker_found = True # Still counts as found for basic check
                    else:
                        logging.error(f"Verification FAILED: Modification marker '{expected_marker}' NOT found in final content.")
                
                # Optional: More rigorous check for original content preservation if needed
                # E.g., check if actual_lines_dict[1..original_last_line_num] matches original_lines
            else:
                logging.error(f"Verification error: Could not read back file content/lines from {target_file} using tool.")
        else:
            logging.error(f"Verification error: Target file {target_file} does not exist after workflow.")
    except Exception as e:
        logging.error(f"Verification error during read back: {e}", exc_info=True)
        
    logging.info("--- Prototype V6.0 Finished ---")

if __name__ == "__main__":
    asyncio.run(main())