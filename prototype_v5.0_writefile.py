# prototype_v5.0_writefile.py
import asyncio
import logging
import os
from typing import Optional # Added Optional

from src.adapters.groq_adapter import GroqAdapter
from src.agents.planner_agent import PlannerAgent
from src.agents.executor_agent import ExecutorAgent
from src.models.write_file_plan import WriteFilePlan
from src.models.write_file_result import WriteFileResult

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)

PLANNER_MODEL = "deepseek-r1-distill-llama-70b"
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # Not used for execution logic

async def main():
    logging.info("--- Starting Prototype V5.0: Write File Task ---")

    try:
        adapter = GroqAdapter()
        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL)
        # Using default data_dir="data" for executor
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL)
        logging.info("Adapter and Agents initialized.")
    except Exception as e:
        logging.critical(f"Initialization failed: {e}", exc_info=True)
        return

    # --- Define Target File and Content ---
    # Ensure we write to a safe location within the executor's data dir
    target_file = os.path.join(executor.data_dir, "test_output.txt")
    test_content = """Hello from Prototype V5.0!
This file was written by the Executor Agent.
Line 3.
End of test content.
"""

    logging.info(f"Target file for writing: {target_file}")
    logging.info(f"Content to write:\n{test_content}")

    # --- Workflow ---
    write_plan: Optional[WriteFilePlan] = None
    write_result: Optional[WriteFileResult] = None

    try:
        # 1. Plan file write
        logging.info("Requesting file write plan from Planner...")
        write_plan = await planner.plan_write_file_task(target_file, test_content)

        if not write_plan:
            logging.error("Planner failed to create a write file plan.")
            return

        # 2. Execute file write
        logging.info(f"Plan received: Action='{write_plan.action}', File='{write_plan.file_path}'. Requesting execution...")
        # Log content preview from plan for debugging
        plan_content_preview = write_plan.content[:100].replace('\n', '\\n') + ('...' if len(write_plan.content) > 100 else '')
        logging.debug(f"Content in plan: '{plan_content_preview}'")

        write_result = await executor.execute_write_file(write_plan)

        if not write_result:
             logging.error("Executor failed unexpectedly during write execution (returned None).")
             return

        # 3. Log Result
        logging.info("--- File Write Task Finished ---")
        logging.info(f"Status: {write_result.status}")
        logging.info(f"File Path: {write_result.file_path}")
        logging.info(f"Message: {write_result.message}")
        if write_result.bytes_written is not None:
             logging.info(f"Bytes Written: {write_result.bytes_written}")

        # 4. Verification Step
        logging.info("--- Verification Step ---")
        if os.path.exists(target_file):
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    actual_content = f.read()
                logging.info(f"Successfully read back file: {target_file}")
                logging.info(f"Actual content read:\n{actual_content}")
                # Optional: Compare actual_content with test_content
                if actual_content.rstrip() == test_content.rstrip():
                     logging.info("Verification successful: Content matches expected content.")
                else:
                     logging.warning("Verification warning: Content read does not match expected content.")
            except Exception as e:
                logging.error(f"Verification error: Could not read back file {target_file}: {e}", exc_info=True)
        else:
             logging.error(f"Verification error: Target file {target_file} does not exist after write attempt.")


    except Exception as e:
        logging.critical(f"Critical error during write file workflow: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
