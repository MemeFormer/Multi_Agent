# prototype_v3.0_wordgame.py
# Desc: Tests the Planner (Senior) -> Executor (Junior) architecture
#       using a simple "Word Game" and JSON communication.
#       Planner uses LLM (Deepseek), Executor simulates action (no LLM call).

import asyncio
import logging
import os
import random
from typing import Optional # To pick random words

# Import necessary components from src
from src.adapters.groq_adapter import GroqAdapter
from src.agents.planner_agent import PlannerAgent
from src.agents.executor_agent import ExecutorAgent
from src.models.word_action_plan import WordActionPlan
from src.models.execution_result import ExecutionResult
from src.models.check_plan import CheckPlan # Added for Phase 2
from src.models.check_result import CheckResult # Added for Phase 2

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
# Adjust log levels for agents/adapter if needed
logging.getLogger("src.adapters.groq_adapter").setLevel(logging.INFO)
logging.getLogger("src.agents.planner_agent").setLevel(logging.INFO)
logging.getLogger("src.agents.executor_agent").setLevel(logging.INFO)


# --- Model Selection (Explicit for New Roles) ---
PLANNER_MODEL = "deepseek-r1-distill-llama-70b" # Use the *new* Deepseek model for planning
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # Maverick designated for execution (but not called in v3.0)

# --- Main Orchestration ---
async def main():
    """
    Runs the Word Game prototype (Phase 2):
    Orchestrates a check-then-add workflow for multiple words.
    Planner plans checks and conditional adds, Executor executes them.
    """
    logging.info("--- Starting Prototype V3.0: Word Game (Phase 2) ---")

    try:
        adapter = GroqAdapter()
        logging.info("Groq Adapter initialized.")

        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL)
        # Executor now manages state (bins)
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL)
        logging.info("Planner and Executor Agents initialized.")

    except ValueError as e:
         logging.error(f"Failed to initialize components: {e}")
         return
    except Exception as e:
        logging.error(f"Unexpected initialization error: {e}", exc_info=True)
        return

    # --- Define Sample Words (with duplicates) ---
    sample_words = ["apple", "sky", "Elephant", "rhythm", "Ocean", "banana", "Ice", "apple", "sky"]
    logging.info(f"Processing words: {sample_words}")

    # --- Phase 2 Workflow: Check-Then-Add Loop ---
    for word_to_test in sample_words:
        logging.info(f"\n--- Processing Word: '{word_to_test}' ---")
        check_plan: Optional[CheckPlan] = None
        check_result: Optional[CheckResult] = None
        final_add_plan: Optional[WordActionPlan] = None
        execution_result: Optional[ExecutionResult] = None
        word_status = "Failed - Unknown Error" # Default status

        try:
            # 1. Plan Check
            logging.info("Requesting check plan from Planner...")
            check_plan = await planner.plan_check_task(word_to_test)

            if not check_plan or not isinstance(check_plan, CheckPlan):
                logging.error("Planner failed to create a valid check plan.")
                word_status = "Failed - Check Plan Generation"
                continue # Skip to next word

            # 2. Execute Check
            logging.info("Check plan received. Requesting check execution from Executor...")
            check_result = await executor.execute_check(check_plan)

            if not check_result or not isinstance(check_result, CheckResult):
                logging.error("Executor failed to return a valid check result.")
                word_status = "Failed - Check Execution"
                continue # Skip to next word

            # 3. Plan Final Add
            logging.info(f"Check result: '{check_result.status}'. Requesting final plan from Planner...")
            final_add_plan = await planner.plan_final_add_task(word_to_test, check_result)

            if check_result.status == "Present":
                 logging.info("Word already present. Add plan correctly skipped by Planner.")
                 word_status = "Skipped - Duplicate"
                 # No need to continue, just won't execute add below

            elif not final_add_plan and check_result.status == "Not Present":
                 logging.warning("Planner failed to create final add plan even though word was not present.")
                 word_status = "Failed - Final Plan Generation"
                 # No need to continue, just won't execute add below

            elif final_add_plan and isinstance(final_add_plan, WordActionPlan):
                 logging.info("Final add plan received.")
                 word_status = "Pending Execution" # Tentative status

            else: # Handle unexpected case where plan is not None but not WordActionPlan
                 logging.error(f"Planner returned unexpected type for final add plan: {type(final_add_plan)}")
                 word_status = "Failed - Invalid Final Plan Type"


            # 4. Execute Add (only if a valid plan exists)
            if final_add_plan and isinstance(final_add_plan, WordActionPlan):
                logging.info("Requesting add execution from Executor...")
                execution_result = await executor.execute_add(final_add_plan)
                if execution_result and execution_result.status == "Success":
                    logging.info("Executor successfully added the word.")
                    word_status = "Added Successfully"
                else:
                    logging.error(f"Executor failed to execute the add action. Result: {execution_result}")
                    word_status = "Failed - Add Execution"
            elif word_status == "Pending Execution": # If plan was expected but not generated correctly
                 word_status = "Failed - Add Plan Missing"
            elif word_status == "Skipped - Duplicate":
                 logging.info("Add execution skipped because word was already present.")
            else: # Other failure cases from planning steps
                 logging.info(f"Add execution skipped due to previous failure: {word_status}")


        except Exception as e:
            logging.error(f"Unexpected error processing word '{word_to_test}': {e}", exc_info=True)
            word_status = "Failed - Unexpected Error"
        finally:
             logging.info(f"--- Finished Processing Word: '{word_to_test}'. Status: {word_status} ---")


    # --- Final Summary ---
    logging.info("\n--- Word Game Phase 3 Finished ---")
    if executor and hasattr(executor, 'data_dir') and hasattr(executor, 'bin_files'):
        logging.info(f"Check the output files in the '{executor.data_dir}' directory:")
        for bin_name, file_path in executor.bin_files.items():
            logging.info(f"- {bin_name}: {file_path}")
    else:
        logging.warning("Executor object not available or file paths not initialized for final summary.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Critical error in main word game loop: {e}", exc_info=True)
