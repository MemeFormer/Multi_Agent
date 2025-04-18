# prototype_v4.0_readfile.py
import asyncio
import logging
import os
from typing import Optional # Added Optional for type hinting

from src.adapters.groq_adapter import GroqAdapter
from src.agents.planner_agent import PlannerAgent
from src.agents.executor_agent import ExecutorAgent
from src.models.read_file_plan import ReadFilePlan
from src.models.file_content_result import FileContentResult

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Quieten httpx logs
# Optional: Adjust agent/adapter log levels if needed
# logging.getLogger("src.agents.planner_agent").setLevel(logging.DEBUG)
# logging.getLogger("src.agents.executor_agent").setLevel(logging.DEBUG)

# Use models appropriate for the task (Planner needs strong reasoning, Executor is tool-based)
PLANNER_MODEL = "deepseek-r1-distill-llama-70b" # Example strong model
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # Not used for execution logic here

async def main():
    logging.info("--- Starting Prototype V4.0: Read File Task ---")

    try:
        adapter = GroqAdapter()
        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL)
        # Executor uses default data_dir="data", doesn't matter for this test
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL)
        logging.info("Adapter and Agents initialized.")
    except Exception as e:
        logging.critical(f"Initialization failed: {e}", exc_info=True)
        return

    # --- Define Target File ---
    # Choose a file that exists in your project structure
    target_file = "src/agents/executor_agent.py" # Example - should exist based on previous steps
    # target_file = "prototype_v3.0_wordgame.py" # Another example
    # target_file = "requirements.txt" # Simple text file

    if not os.path.exists(target_file):
         logging.error(f"Target file does not exist: {target_file}. Aborting.")
         return

    logging.info(f"Target file for reading: {target_file}")

    # --- Workflow ---
    read_plan: Optional[ReadFilePlan] = None
    read_result: Optional[FileContentResult] = None

    try:
        # 1. Plan file read
        logging.info("Requesting file read plan from Planner...")
        read_plan = await planner.plan_read_file_task(target_file)

        if not read_plan:
            logging.error("Planner failed to create a read file plan.")
            return # End early if planning fails

        # 2. Execute file read
        logging.info(f"Plan received: Action='{read_plan.action}', File='{read_plan.file_path}'. Requesting execution...")
        read_result = await executor.execute_read_file(read_plan)

        if not read_result:
             logging.error("Executor failed unexpectedly during read execution (returned None).")
             return # End early if execution fails fundamentally

        # 3. Log Result
        logging.info("--- File Read Task Finished ---")
        if read_result.status == "Success" and read_result.content is not None:
            logging.info(f"Status: {read_result.status}")
            logging.info(f"File Path: {read_result.file_path}")
            logging.info(f"Message: {read_result.message}")
            # Log beginning of content (avoid logging huge files)
            content_preview = read_result.content[:200].replace('\n', '\\n') # Show first 200 chars, escape newlines
            logging.info(f"Content Preview ({len(read_result.content)} chars total): '{content_preview}...'")
        else:
            # Log failure details
            logging.error(f"Status: {read_result.status}")
            logging.error(f"File Path: {read_result.file_path}")
            logging.error(f"Message: {read_result.message}") # Contains error details

    except Exception as e:
        logging.critical(f"Critical error during read file workflow: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
