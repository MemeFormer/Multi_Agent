# src/agents/planner_agent.py

import logging
import json
from typing import Optional
from groq import GroqError
from pydantic import ValidationError

from src.adapters.groq_adapter import GroqAdapter
from src.models.word_action_plan import WordActionPlan

# Configure logging for this agent
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

class PlannerAgent:
    """
    Agent responsible for analyzing input and creating structured plans.
    In v3.0, analyzes a word and decides which 'bin' it belongs to.
    """
    def __init__(self, adapter: GroqAdapter, model_id: str, temperature: float = 0.2, max_tokens: int = 500):
        """
        Initializes the Planner Agent.

        Args:
            adapter: Instance of GroqAdapter.
            model_id: The LLM model ID to use for planning (e.g., Deepseek).
            temperature: Sampling temperature.
            max_tokens: Max tokens for the plan generation.
        """
        self.adapter = adapter
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"PlannerAgent initialized with model: {self.model_id}")

    async def plan_word_task(self, word: str) -> Optional[WordActionPlan]:
            """
            Analyzes a word and generates a WordActionPlan using JSON mode.
    
            Args:
                word: The input word to analyze.
    
            Returns:
                A WordActionPlan object if successful, None otherwise.
            """
            logger.info(f"Planner Agent ({self.model_id}) planning for word: '{word}'")
    
            # Generate the schema string for the prompt
            plan_schema_str = json.dumps(WordActionPlan.model_json_schema(), indent=2)
    
            system_prompt = f"""
    You are a meticulous Planner Agent. Your task is to analyze the given input word and create a plan for where it should be categorized based on its first letter.
    
    **Rule:**
    - If the word starts with a vowel (A, E, I, O, U, case-insensitive), the `target_bin` is "Vowel Bin".
    - If the word starts with a consonant (any other letter), the `target_bin` is "Consonant Bin".
    
    You MUST output your plan as a valid JSON object conforming EXACTLY to the following `WordActionPlan` schema. Include the original word in `word_to_process`. You can optionally add brief reasoning.
    
    **`WordActionPlan` Schema:**
    ```json
    {{plan_schema_str}} # Note: Use f-string interpolation correctly here if needed, or pass as variable
    
    Generate ONLY the JSON object. Do not add introductory text, comments, or markdown formatting around the JSON.
    """
            user_prompt = f"""
    Input Word: "{word}"
    Generate the WordActionPlan JSON object:
    """
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            # --- TRY block starts here, indented within the method ---
            try:
                logger.debug(f"Planner calling Groq API for JSON plan. Params: model={self.model_id}, temp={self.temperature}, max_tokens={self.max_tokens}")
                response_plan: WordActionPlan = await self.adapter.chat_completion(
                    model=self.model_id,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=1,
                    stop=None,
                    stream=False,
                    json_schema=WordActionPlan # Pass the Pydantic class for validation
                )
                # --- This block executes only if the await call above SUCCEEDS, indented within TRY ---
                if response_plan and isinstance(response_plan, WordActionPlan):
                    # Optional: Add specific validation if needed, e.g., check if word matches
                    if response_plan.word_to_process.lower() != word.lower():
                        logger.warning(f"Planner returned plan for '{response_plan.word_to_process}' but input was '{word}'. Using returned word.")
                        # Decide whether to proceed or fail here. For now, let's proceed.
                    logger.info(f"Planner proposed plan: Word='{response_plan.word_to_process}', Target Bin='{response_plan.target_bin}', Reasoning='{response_plan.reasoning}'")
                    return response_plan
                else:
                    # This else corresponds to the "if response_plan and isinstance..." check
                    logger.error("Planner chat_completion did not return a valid WordActionPlan object.")
                    return None
            # --- EXCEPT blocks aligned with TRY ---
            except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
                logger.error(f"Planner agent failed during plan proposal: {e}", exc_info=True)
                return None
            except Exception as e:
                logger.error(f"Planner unexpected error during plan_word_task: {e}", exc_info=True)
                return None
