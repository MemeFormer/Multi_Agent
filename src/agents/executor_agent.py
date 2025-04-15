# src/agents/executor_agent.py

import logging
import asyncio
from typing import Optional

# Import the plan and result models
from src.models.word_action_plan import WordActionPlan
from src.models.execution_result import ExecutionResult
# Import adapter, though it's not used for LLM calls in v3.0
from src.adapters.groq_adapter import GroqAdapter

# Configure logging for this agent
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

class ExecutorAgent:
    """
    Agent responsible for executing specific actions based on a received plan.
    In v3.0, simulates placing a word in a bin. Does NOT call LLM for execution.
    """
    def __init__(self, adapter: GroqAdapter, model_id: str):
        """
        Initializes the Executor Agent.

        Args:
            adapter: Instance of GroqAdapter (kept for future use).
            model_id: The LLM model ID designated for execution tasks (e.g., Maverick).
                      Not used for LLM calls in v3.0.
        """
        self.adapter = adapter
        self.model_id = model_id # Store for potential future use
        logger.info(f"ExecutorAgent initialized (designated model: {self.model_id}, not used for v3.0 execution)")

    async def execute_word_action(self, plan: WordActionPlan) -> ExecutionResult:
        """
        Simulates executing the action defined in the WordActionPlan.

        Args:
            plan: The WordActionPlan received from the Planner.

        Returns:
            An ExecutionResult object indicating success or failure.
        """
        if not plan or not isinstance(plan, WordActionPlan):
            logger.error("Executor received invalid plan.")
            return ExecutionResult(status="Failure", message="Invalid plan object received.")

        logger.info(f"Executor Agent received plan: Process '{plan.word_to_process}', Target Bin='{plan.target_bin}'")

        try:
            # --- Simulate the Action ---
            # In a real scenario, this is where file I/O, API calls, or commands would run.
            # For v3.0, we just log the simulated action.
            logger.info(f"Simulating action: Placing '{plan.word_to_process}' into '{plan.target_bin}'...")
            await asyncio.sleep(0.1) # Simulate a tiny bit of work

            # --- Report Success ---
            message = f"Successfully placed '{plan.word_to_process}' into '{plan.target_bin}'."
            logger.info(message)
            return ExecutionResult(status="Success", message=message)

        except Exception as e:
            # Catch any unexpected errors during the simulated execution
            error_message = f"Error during simulated execution for word '{plan.word_to_process}': {e}"
            logger.error(error_message, exc_info=True)
            return ExecutionResult(status="Failure", message=error_message)