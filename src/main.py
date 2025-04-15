# src/main.py
import asyncio
import logging
import os
import shutil
from typing import Optional

# Assuming GroqAdapter is correctly implemented and accessible
# Adjust the import path if your project structure differs
from src.adapters.groq_adapter import GroqAdapter
from src.agents.junior_engineer import JuniorEngineer
from src.agents.senior_engineer import SeniorEngineer
from src.operations.command_execution import execute_command
from src.models.execution_plan import ExecutionPlan
from src.models.review_feedback import ReviewFeedback
from groq import GroqError

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Reduce verbosity from http library

# --- Model Selection (Consider moving to a config file) ---
# Replace with your actual model IDs if different
JUNIOR_MODEL = "llama3-70b-8192" # Or "meta-llama/llama-4-maverick-17b-128e-instruct" if preferred
SENIOR_MODEL = "llama3-70b-8192" # Or "deepseek-r1-distill-qwen-32b" if preferred

# --- Environment Setup ---
TEST_DIR = "main_test_environment" # Use a different dir than the prototype

def setup_test_environment():
    """Creates a clean directory for testing."""
    logging.info(f"Setting up test environment in: {TEST_DIR}")
    try:
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
            logging.debug(f"Removed existing directory: {TEST_DIR}")
        os.makedirs(TEST_DIR)
        logging.debug(f"Created directory: {TEST_DIR}")
        # Create the initial file for the sed task
        test_file_path = os.path.join(TEST_DIR, "test_file_sed.txt")
        with open(test_file_path, "w") as f:
            f.write("apple\napple\nbanana")
        logging.info(f"Created test file: {test_file_path} with initial content.")
        return f"Directory '{TEST_DIR}' created. Contains file 'test_file_sed.txt'."
    except OSError as e:
        logging.error(f"Failed to set up test environment '{TEST_DIR}': {e}", exc_info=True)
        raise # Re-raise critical setup error

def cleanup_test_environment():
    """Removes the test directory."""
    logging.info(f"Cleaning up test environment: {TEST_DIR}")
    try:
        if os.path.exists(TEST_DIR):
            shutil.rmtree(TEST_DIR)
            logging.debug(f"Removed directory: {TEST_DIR}")
    except OSError as e:
        logging.error(f"Failed to clean up test environment '{TEST_DIR}': {e}", exc_info=True)


async def run_task():
    """
    Orchestrates the process of proposing, reviewing, and executing a task.
    """
    logging.info("--- Starting Task Orchestration ---")
    adapter: Optional[GroqAdapter] = None
    plan: Optional[ExecutionPlan] = None
    feedback: Optional[ReviewFeedback] = None

    try:
        # 1. Setup Environment & Initialize Adapter
        initial_context = setup_test_environment()
        adapter = GroqAdapter() # Assumes API key is handled via env var by the adapter
        logging.info("Groq Adapter initialized.")

        # 2. Instantiate Agents
        junior = JuniorEngineer(adapter, JUNIOR_MODEL)
        senior = SeniorEngineer(adapter, SENIOR_MODEL)
        logging.info("Junior and Senior Engineers instantiated.")

        # 3. Define Task
        # Simple test task: Replace 'apple' with 'orange' in the test file
        task_description = f"In the file '{os.path.join(TEST_DIR, 'test_file_sed.txt')}', replace all occurrences of 'apple' with 'orange'."
        context = f"{initial_context} Platform is macOS/BSD like. Ensure commands are compatible."
        logging.info(f"Task defined: {task_description}")

        # 4. Junior Proposes Plan
        logging.info("Requesting plan from Junior Engineer...")
        try:
            plan = await junior.propose_plan(task_description, context)
            logging.info(f"Junior proposed plan: Command='{plan.command}', Description='{plan.description}'")
        except (GroqError, ValueError, Exception) as e:
            logging.error(f"Failed to get plan from Junior: {e}", exc_info=True)
            # Decide how to handle failure - here we stop the process
            return # Exit run_task

        # 5. Senior Reviews Plan
        logging.info("Requesting review from Senior Engineer...")
        try:
            feedback = await senior.review_plan(plan, task_description, context)
            log_level = logging.INFO if feedback.approved else logging.WARNING
            logging.log(log_level, f"Senior review: Approved={feedback.approved}, Reasoning='{feedback.reasoning}'")
        except (GroqError, ValueError, Exception) as e:
            logging.error(f"Failed to get review from Senior: {e}", exc_info=True)
            # Decide how to handle failure - here we stop the process
            return # Exit run_task

        # 6. Execute if Approved
        if feedback and feedback.approved:
            logging.info("Plan approved by Senior. Executing command...")
            try:
                # IMPORTANT: Ensure the command execution context is correct.
                # If commands need to run *inside* TEST_DIR, prepend `cd TEST_DIR && `
                # For this specific sed task, operating on the full path is fine.
                success, stdout, stderr = execute_command(plan.command)
                if success:
                    logging.info(f"Command executed successfully. Output:\n{stdout}")
                    # Optional: Add verification step here if needed
                else:
                    logging.error(f"Command execution failed. Stderr:\n{stderr}")
            except Exception as e:
                logging.error(f"An error occurred during command execution: {e}", exc_info=True)
        elif feedback:
            logging.warning("Plan rejected by Senior. No command executed.")
        else:
            logging.error("Review feedback was not received. No command executed.")

    except Exception as e:
        logging.critical(f"An unexpected error occurred in run_task: {e}", exc_info=True)
    finally:
        # 7. Cleanup
        cleanup_test_environment()
        logging.info("--- Task Orchestration Finished ---")


# --- Main Execution Block ---
if __name__ == "__main__":
    try:
        asyncio.run(run_task())
    except KeyboardInterrupt:
        logging.info("Orchestration interrupted by user.")
    except Exception as e:
        logging.critical(f"Critical error preventing task execution: {e}", exc_info=True)
        # Perform cleanup even if asyncio loop fails
        cleanup_test_environment()
