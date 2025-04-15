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
PLANNER_MODEL = "deepseek-r1-distill-qwen-32b" # Use Deepseek for planning
EXECUTOR_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct" # Maverick designated for execution (but not called in v3.0)

# --- Main Orchestration ---
async def main():
    """
    Runs the Word Game prototype: Planner plans, Executor simulates execution.
    """
    logging.info("--- Starting Prototype V3.0: Word Game ---")

    try:
        adapter = GroqAdapter()
        logging.info("Groq Adapter initialized.")

        planner = PlannerAgent(adapter, model_id=PLANNER_MODEL)
        # Executor is initialized but won't call its designated LLM in this version
        executor = ExecutorAgent(adapter, model_id=EXECUTOR_MODEL)
        logging.info("Planner and Executor Agents initialized.")

    except ValueError as e:
         logging.error(f"Failed to initialize components: {e}")
         return
    except Exception as e:
        logging.error(f"Unexpected initialization error: {e}", exc_info=True)
        return

    # --- Define Sample Words ---
    sample_words = ["apple", "sky", "Elephant", "rhythm", "Ocean", "banana", "Ice"]
    word_to_test = random.choice(sample_words)
    logging.info(f"Selected word for this run: '{word_to_test}'")

    # --- Workflow ---
    plan: Optional[WordActionPlan] = None
    result: Optional[ExecutionResult] = None

    # 1. Planner creates plan
    logging.info(f"Requesting plan from Planner for '{word_to_test}'...")
    plan = await planner.plan_word_task(word_to_test)

    # 2. Executor executes plan (if valid)
    if plan and isinstance(plan, WordActionPlan):
        logging.info(f"Plan received from Planner. Requesting execution from Executor...")
        result = await executor.execute_word_action(plan)
    elif plan is None:
        logging.error("Planner failed to return a plan. Aborting execution.")
        result = ExecutionResult(status="Failure", message="Planner failed to generate a plan.")
    else: # Should not happen if adapter validation works, but good practice
        logging.error(f"Planner returned unexpected type: {type(plan)}. Aborting.")
        result = ExecutionResult(status="Failure", message="Planner returned invalid plan type.")

    # 3. Log Final Result
    logging.info("--- Word Game Run Finished ---")
    if result:
        logging.info(f"Final Execution Result: Status='{result.status}', Message='{result.message}'")
    else:
        # This case means the executor step wasn't even reached or failed unexpectedly
        logging.error("Execution result not available.")

    print("\n--- Run Summary ---")
    print(f"Input Word: {word_to_test}")
    if plan:
        print(f"Planner Action: Place in '{plan.target_bin}'")
    else:
        print("Planner Action: FAILED")
    if result:
         print(f"Executor Result: {result.status} - {result.message}")
    else:
         print("Executor Result: NOT RUN / FAILED")
    print("-------------------")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Critical error in main word game loop: {e}", exc_info=True)