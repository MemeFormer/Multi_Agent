# src/agents/junior_engineer.py

import json
import logging
from typing import Optional
from groq import GroqError
from pydantic import BaseModel
from pydantic_core import ValidationError # Ensure BaseModel is imported if needed for type hints

# Assuming adapter and models are imported correctly relative to this file's location
from src.adapters.groq_adapter import GroqAdapter
from src.models.execution_plan import ExecutionPlan # Import the Pydantic Class

# Import constants for model ID, temp, tokens
# It's often better practice to pass these during instantiation or get from config,
# but using constants defined elsewhere is okay for now if they are accessible.
# Let's assume they are defined in a central config or passed via main.
# For now, we'll add placeholders - replace with actual import if defined elsewhere
# Or better, accept them in __init__
# from config import JUNIOR_MODEL, JUNIOR_TEMP, JUNIOR_MAX_TOKENS # Example import

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Define constants directly here for clarity in this example
# Ideally, these come from a config file or are passed in
JUNIOR_MODEL_DEFAULT = "meta-llama/llama-4-maverick-17b-128e-instruct"
JUNIOR_TEMP_DEFAULT = 0.1
JUNIOR_MAX_TOKENS_DEFAULT = 2500


class JuniorEngineer:
    """
    Agent responsible for proposing execution plans (commands) based on tasks.
    Communicates using structured ExecutionPlan objects (JSON mode).
    """
    def __init__(
        self,
        adapter: GroqAdapter,
        model_id: str = JUNIOR_MODEL_DEFAULT,
        temperature: float = JUNIOR_TEMP_DEFAULT,
        max_tokens: int = JUNIOR_MAX_TOKENS_DEFAULT
        ):
        """
        Initializes the Junior Engineer.

        Args:
            adapter: An instance of the GroqAdapter.
            model_id: The specific Groq model ID to use.
            temperature: The sampling temperature for the model.
            max_tokens: The maximum tokens for the model response.
        """
        self.adapter = adapter
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"JuniorEngineer initialized with model: {self.model_id}")

    async def propose_plan(self, task_description: str, context: str) -> Optional[ExecutionPlan]:
        """
        Proposes an execution plan (single command) for the given task using JSON mode.

        Args:
            task_description: The goal to achieve.
            context: Relevant information about the environment/state.

        Returns:
            An ExecutionPlan object if successful, None otherwise.
        """
        logger.info(f"Junior Agent ({self.model_id}) starting task: {task_description}")

        # Prompt instructing the model to output JSON conforming to ExecutionPlan
        # Note: TEST_DIR might need to be passed or accessed globally if needed here
        # For simplicity, assuming it's part of the general context if relevant
        system_prompt = """
You are a Junior Developer Agent. Your task is to generate a plan to accomplish the given task.
You MUST output your plan as a valid JSON object conforming EXACTLY to the following Pydantic schema:

```json
{
  "title": "ExecutionPlan",
  "type": "object",
  "properties": {
    "command": {
      "title": "Command",
      "description": "The single, precise, macOS/BSD compatible bash command.",
      "type": "string"
    },
    "description": {
      "title": "Description",
      "description": "A brief explanation of what the command does.",
      "type": "string"
    }
  },
  "required": [
    "command",
    "description"
  ]
}
````


Generate ONLY the JSON object. Do not add any introductory text, comments, or markdown formatting around the JSON. Ensure the command is macOS/BSD compatible (e.g., `sed -i ''`).
"""
        user_prompt = f"""
Task: {task_description}

Context:
{context}

Generate the ExecutionPlan JSON object:
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            logger.debug(f"Junior calling Groq API for JSON. Params: model={self.model_id}, temp={self.temperature}, max_tokens={self.max_tokens}")

            # --- CRITICAL FIX: Pass the CLASS itself ---
            response_plan: ExecutionPlan = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens, # Ensure sufficient tokens for JSON + command
                top_p=1,
                stop=None,
                stream=False,
                json_schema=ExecutionPlan # Pass the ExecutionPlan class
            )

            # The adapter now returns a validated Pydantic object if successful
            if response_plan and isinstance(response_plan, ExecutionPlan):
                 # Optional: Basic validation on returned fields
                 if not response_plan.command:
                      logger.error("Junior proposed plan with empty command field.")
                      return None
                 logger.info(f"Junior proposed plan: Command='{response_plan.command}', Desc='{response_plan.description}'")
                 return response_plan
            else:
                 # This case should ideally be less frequent as adapter handles validation
                 logger.error("Junior Agent chat_completion did not return a valid ExecutionPlan object.")
                 return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            # Catch errors from adapter/validation
            logger.error(f"Junior agent failed during plan proposal: {e}", exc_info=True) # Log traceback for debug
            return None
        except Exception as e:
            logger.error(f"Junior unexpected error during propose_plan: {e}", exc_info=True)
            return None





