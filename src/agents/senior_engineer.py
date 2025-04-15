# src/agents/senior_engineer.py

import logging
import json # Import json
from typing import Optional
from pydantic import BaseModel, ValidationError # Ensure BaseModel and ValidationError are imported
from groq import GroqError # Import GroqError

from src.adapters.groq_adapter import GroqAdapter
from src.models.execution_plan import ExecutionPlan # Input model
from src.models.review_feedback import ReviewFeedback # Output model

# Import constants or pass via init
# from config import SENIOR_MODEL, SENIOR_TEMP, SENIOR_MAX_TOKENS # Example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Define constants directly here for clarity in this example
SENIOR_MODEL_DEFAULT = "deepseek-r1-distill-qwen-32b"
SENIOR_TEMP_DEFAULT = 0.2
SENIOR_MAX_TOKENS_DEFAULT = 3000 # Keep high for reasoning if included
# Note: TEST_DIR needs to be accessible, maybe from config or passed
TEST_DIR_DEFAULT = "main_test_environment" # Example placeholder

class SeniorEngineer:
    """
    Agent responsible for reviewing proposed execution plans for safety and correctness.
    Communicates using structured ReviewFeedback objects (JSON mode).
    """
    def __init__(
        self,
        adapter: GroqAdapter,
        model_id: str = SENIOR_MODEL_DEFAULT,
        temperature: float = SENIOR_TEMP_DEFAULT,
        max_tokens: int = SENIOR_MAX_TOKENS_DEFAULT,
        test_dir: str = TEST_DIR_DEFAULT # Pass TEST_DIR if needed in prompt
        ):
        """
        Initializes the Senior Engineer.

        Args:
            adapter: An instance of the GroqAdapter.
            model_id: The specific Groq model ID to use.
            temperature: The sampling temperature for the model.
            max_tokens: The maximum tokens for the model response.
            test_dir: The designated safe working directory name.
        """
        self.adapter = adapter
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.test_dir = test_dir # Store test dir for prompt formatting
        logger.info(f"SeniorEngineer initialized with model: {self.model_id}")

    async def review_plan(
        self,
        plan: ExecutionPlan,
        task_description: str,
        context: str,
        # Allow reasoning format control, defaulting to hidden for efficiency
        reasoning_format: str = 'hidden'
        ) -> Optional[ReviewFeedback]:
        """
        Reviews a proposed ExecutionPlan using JSON mode.

        Args:
            plan: The ExecutionPlan object proposed by the Junior agent.
            task_description: The original goal.
            context: Relevant information about the environment/state.
            reasoning_format: 'hidden' (default), 'parsed', or 'raw'. 'parsed' recommended
                              if capturing reasoning in the ReviewFeedback model.

        Returns:
            A ReviewFeedback object if successful, None otherwise.
        """
        if not plan or not isinstance(plan, ExecutionPlan) or not plan.command:
            logger.warning("Senior auto-REJECT: Invalid or empty plan received.")
            # Return a default rejection feedback object
            return ReviewFeedback(approved=False, reasoning="Invalid plan received.")

        logger.info(f"Senior Agent ({self.model_id}) reviewing plan: Command='{plan.command}'")

      
        feedback_schema_str = json.dumps(ReviewFeedback.model_json_schema(), indent=2)

        system_prompt = f"""
You are an extremely strict Senior Developer Agent acting as a security and correctness gatekeeper.
Your ONLY goal is to review the proposed `ExecutionPlan` based on the strict criteria below and output your decision as a valid JSON object conforming EXACTLY to the `ReviewFeedback` schema.
**`ReviewFeedback` Schema:**
    ```json
    {feedback_schema_str}

**Strict Review Criteria:**
1.  **Safety:** The command MUST NOT perform destructive actions outside the designated safe working directory ('{self.test_dir}'). This includes `rm -rf /`, `mv /`, writing outside `{self.test_dir}`, etc. Assume the current working directory is the root project directory. Commands MUST operate ONLY within the `{self.test_dir}` subdirectory. File paths in commands must explicitly start with `{self.test_dir}/` or be relative paths intended to operate within it (e.g., `cd {self.test_dir}; ls`).
2.  **Correctness:** The command must be syntactically valid for a standard Linux shell and plausibly contribute to the original task: "{task_description}".
3.  **Simplicity:** Prefer simple, common commands. Avoid overly complex chains or obscure utilities unless necessary.
4.  **Idempotency (Optional but Preferred):** If possible, the command should be safe to run multiple times without unintended side effects.

**Input:**
*   **Original Task:** {task_description}
*   **Context:** {context}
*   **Proposed Plan (by Junior Agent):**
   
    {{
      "command": "{plan.command}",
      "description": "{plan.description}"
    }}
    ```

**Your Task:**
Review the `command` in the proposed plan. Output ONLY the `ReviewFeedback` JSON object.
If `approved` is `False`, provide a concise `reasoning` string explaining the violation of the criteria.
If `approved` is `True`, the `reasoning` field MUST be omitted or null.
Do NOT add any text before or after the JSON object.
"""
        # Construct messages for the LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Review the proposed plan for task: {task_description}"} # User message can be simple
        ]

        try:
            logger.debug(f"Senior calling Groq API for JSON review. Params: model={self.model_id}, temp={self.temperature}, max_tokens={self.max_tokens}")

            # --- Call adapter with ReviewFeedback schema ---
            response_feedback: Optional[ReviewFeedback] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens, # Ensure sufficient tokens for JSON feedback
                top_p=1,
                stop=None,
                stream=False,
                json_schema=ReviewFeedback # Pass the ReviewFeedback class
            )

            # The adapter now returns a validated Pydantic object or None
            if response_feedback and isinstance(response_feedback, ReviewFeedback):
                if response_feedback.approved:
                    logger.info(f"Senior APPROVED plan: Command='{plan.command}'")
                else:
                    logger.warning(f"Senior REJECTED plan: Command='{plan.command}', Reason='{response_feedback.reasoning}'")
                return response_feedback
            else:
                # This case indicates an issue with the LLM response or adapter validation
                logger.error("Senior Agent chat_completion did not return a valid ReviewFeedback object.")
                # Fallback: Reject the plan if review fails
                return ReviewFeedback(approved=False, reasoning="Review process failed internally.")

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            # Catch errors from adapter/validation/JSON parsing
            logger.error(f"Senior agent failed during plan review: {e}", exc_info=True) # Log traceback for debug
            # Fallback: Reject the plan on error
            return ReviewFeedback(approved=False, reasoning=f"Review process encountered an error: {type(e).__name__}")
        except Exception as e:
            logger.error(f"Senior unexpected error during review_plan: {e}", exc_info=True)
            # Fallback: Reject the plan on unexpected error
            return ReviewFeedback(approved=False, reasoning="An unexpected error occurred during review.")

# Note: The code block starting with 'try:' at line 127 and its contents
# seemed misplaced or duplicated from another agent (Junior?).
# The corrected code above implements the review logic within the `review_plan` method.
# The original block from line 127 to 155 has been removed as it doesn't fit
# the Senior Engineer's `review_plan` function.