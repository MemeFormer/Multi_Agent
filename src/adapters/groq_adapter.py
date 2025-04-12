# src/adapters/groq_adapter.py

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Type
from groq import AsyncGroq, GroqError
from pydantic import BaseModel, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GroqAdapter:
    """
    An asynchronous adapter to interact with the Groq API.

    Handles standard chat completions, streaming, JSON mode enforcement,
    tool usage, and response prefilling based on provided parameters.
    """
    def __init__(self, api_key: Optional[str] = None, default_model: str = "llama3-70b-8192"):
        """
        Initializes the AsyncGroq client.

        Args:
            api_key: Groq API key. Defaults to reading from the
                     GROQ_API_KEY environment variable.
            default_model: The default Groq model to use if not specified per call.
                           Consider using newer models like 'llama-3.3-70b-versatile'
                           if available and suitable.
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set or passed.")

        # Consider making the default model configurable (e.g., via config/models.json)
        self.default_model = default_model
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            logger.info(f"GroqAdapter initialized with default model: {self.default_model}")
        except Exception as e:
            logger.error(f"Failed to initialize AsyncGroq client: {e}", exc_info=True)
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048, # Renamed for clarity
        top_p: float = 1.0,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        json_schema: Optional[Type[BaseModel]] = None, # Pass Pydantic model for JSON mode
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict]] = None, # "auto", "none", {"type": "function", ...}
        prefill_content: Optional[str] = None
    ) -> Union[AsyncGenerator[str, None], Any, BaseModel]:
        """
        Makes an asynchronous call to the Groq Chat Completions API with options.

        Args:
            messages: Conversation history.
            model: Specific model override.
            temperature: Sampling temperature.
            max_tokens: Max tokens for the completion.
            top_p: Nucleus sampling parameter.
            stop: Stop sequence(s).
            stream: If True, returns an async generator yielding content chunks.
            json_schema: If provided, enables JSON mode using this Pydantic model's schema.
                         Forces stream=False. Returns a validated Pydantic model instance.
            tools: List of tool definitions for the model.
            tool_choice: Controls how/if tools are used.
            prefill_content: String to prefill the assistant's response.

        Returns:
            - If stream=True: An async generator yielding response content strings.
            - If json_schema is provided: A validated Pydantic model instance.
            - Otherwise (default, non-streaming, no JSON): The full Groq chat completion response object
              (which might contain text content or tool calls).

        Raises:
            ValueError: For invalid parameter combinations or validation errors.
            GroqError: For API-related errors.
        """
        selected_model = model or self.default_model
        effective_messages = list(messages) # Copy to avoid modifying the original list

        api_params: Dict[str, Any] = {
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stop": stop,
        }

        # --- Parameter Handling & Validation ---

        # Handle Prefilling: Add an assistant message with the prefill content
        if prefill_content:
            effective_messages.append({"role": "assistant", "content": prefill_content})
            logger.info(f"Prefilling assistant message starting with: '{prefill_content[:50]}...'")
            # Automatically add common stop sequence for prefilled code/JSON if not set
            if stop is None and (prefill_content.strip().endswith("```python") or prefill_content.strip().endswith("```json")):
                api_params["stop"] = "```"
                logger.info("Automatically setting stop sequence to '```' due to prefill format.")

        # Handle JSON Mode
        if json_schema:
            if stream:
                raise ValueError("Streaming (stream=True) is not supported with JSON mode (json_schema provided).")
            if tools:
                 raise ValueError("Tool use (tools provided) cannot be combined with JSON mode (json_schema provided) in a single call.")

            api_params["response_format"] = {"type": "json_object"}
            # Inject schema into system prompt for better adherence (Groq recommendation)
            schema_str = json.dumps(json_schema.model_json_schema(), indent=2)
            schema_prompt = f"You MUST output valid JSON conforming to this schema:\n```json\n{schema_str}\n```"
            found_system = False
            for i, msg in enumerate(effective_messages):
                if msg["role"] == "system":
                    effective_messages[i]["content"] = f"{msg['content']}\n\n{schema_prompt}"
                    found_system = True
                    break
            if not found_system:
                effective_messages.insert(0, {"role": "system", "content": schema_prompt})
            logger.info(f"JSON mode enabled. Expecting output conforming to '{json_schema.__name__}'.")
            api_params["stream"] = False # Explicitly set stream to False for JSON mode

        # Handle Tool Use
        elif tools:
            if stream:
                logger.warning("Streaming with tool use. The stream *may* contain tool call details incrementally.")
                # While technically possible, parsing streamed tool calls can be complex.
                # Non-streaming is generally recommended for easier tool call handling.
            api_params["tools"] = tools
            api_params["tool_choice"] = tool_choice or "auto" # Default to auto if tools are present
            api_params["stream"] = stream # Respect user's stream preference
            logger.info(f"Tool use enabled with tool_choice='{api_params['tool_choice']}'.")

        # Handle standard streaming / non-streaming
        else:
            api_params["stream"] = stream

        # Final parameters for the API call
        api_params["messages"] = effective_messages

        logger.debug(f"Calling Groq API: Model='{selected_model}', Stream={api_params['stream']}, JSONMode={bool(json_schema)}, Tools={bool(tools)}")

        # --- API Call Execution ---
        try:
            completion = await self.client.chat.completions.create(**api_params)

            # --- Response Handling ---
            if api_params.get("stream"):
                logger.info("Streaming response...")
                return self._handle_stream(completion)
            elif json_schema:
                logger.info("Processing JSON mode response...")
                response_content = completion.choices[0].message.content
                return self._validate_json_response(response_content, json_schema)
            else:
                # Return the raw response object for standard non-streaming calls
                # (could contain text or tool_calls)
                logger.info("Returning non-streamed response object.")
                if completion.choices[0].finish_reason == "tool_calls":
                     logger.info(f"Response contains tool calls: {completion.choices[0].message.tool_calls}")
                return completion

        except GroqError as e:
            logger.error(f"Groq API error: {e.status_code} - {e.message}", exc_info=True)
            raise
        except ValidationError as e:
            logger.error(f"JSON validation failed: {e}", exc_info=True)
            # Include raw content in the error for debugging
            raw_content = completion.choices[0].message.content if 'completion' in locals() else "N/A"
            raise ValueError(f"LLM output failed Pydantic validation for {json_schema.__name__}. Errors: {e}. Raw response: '{raw_content}'") from e
        except json.JSONDecodeError as e:
             logger.error(f"Failed to decode JSON response: {e}", exc_info=True)
             raw_content = completion.choices[0].message.content if 'completion' in locals() else "N/A"
             raise ValueError(f"LLM response was not valid JSON. Error: {e}. Raw response: '{raw_content}'") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during Groq API call: {e}", exc_info=True)
            raise

    async def _handle_stream(self, stream_completion) -> AsyncGenerator[str, None]:
        """Helper to process the async stream."""
        async for chunk in stream_completion:
            delta = chunk.choices[0].delta
            content = delta.content if delta else None
            # You could add logic here to detect/yield tool call chunks if needed,
            # but for simplicity, we'll just yield content deltas.
            if content:
                yield content
        logger.info("Stream finished.")

    def _validate_json_response(self, response_content: str, json_schema: Type[BaseModel]) -> BaseModel:
        """Helper to validate and parse JSON response against a Pydantic model."""
        try:
            logger.debug(f"Raw JSON received for validation:\n{response_content}")
            validated_data = json_schema.model_validate_json(response_content)
            logger.info(f"Successfully validated JSON response against '{json_schema.__name__}'.")
            return validated_data
        except (ValidationError, json.JSONDecodeError) as e:
            # Errors are caught and re-raised in the main method with more context
            raise e


# --- Example Usage (within the adapter file for testing) ---
async def _run_adapter_examples():
    # Assume GROQ_API_KEY is set in the environment
    if not os.getenv("GROQ_API_KEY"):
         print("SKIP: Set GROQ_API_KEY environment variable to run examples.")
         return

    adapter = GroqAdapter(default_model="llama3-70b-8192") # Or 'llama-3.3-70b-versatile'

    # 1. Basic Streaming
    print("\n--- Example 1: Basic Streaming ---")
    try:
        stream_gen = await adapter.chat_completion(
            messages=[{"role": "user", "content": "Tell me a short story about a brave llama."}],
            stream=True, max_tokens=100
        )
        async for chunk in stream_gen:
            print(chunk, end="", flush=True)
        print("\n--------------------\n")
    except Exception as e: print(f"ERROR: {e}")

    # 2. Prefilling Code (Streaming)
    print("\n--- Example 2: Prefilling Python Code (Streaming) ---")
    try:
        code_gen = await adapter.chat_completion(
            messages=[{"role": "user", "content": "Write a Python func for factorial."}],
            stream=True, prefill_content="```python\n", max_tokens=150
            # stop="```" # stop should be auto-added by adapter
        )
        print("```python") # Prefill content isn't streamed, print manually
        async for chunk in code_gen:
            print(chunk, end="", flush=True)
        print("\n```" if not code_gen else "") # Add closing only if stream ended
        print("--------------------\n")
    except Exception as e: print(f"ERROR: {e}")


    # 3. JSON Mode
    print("\n--- Example 3: JSON Mode ---")
    class RecipeInfo(BaseModel):
        recipe_name: str
        prep_time_minutes: int
        ingredients: List[str]

    try:
        recipe_data: RecipeInfo = await adapter.chat_completion(
            messages=[{"role": "user", "content": "Give me a simple pancake recipe."}],
            json_schema=RecipeInfo,
            temperature=0.1 # Lower temp for predictable JSON
        )
        print(f"Validated Recipe Data (Pydantic Object): {recipe_data}")
        print(f"Ingredients: {recipe_data.ingredients}")
        print("--------------------\n")
    except Exception as e: print(f"ERROR: {e}")


    # 4. Tool Use (First Call - Checking if tool is requested)
    print("\n--- Example 4: Tool Use (First Call) ---")
    weather_tool = {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "fahrenheit"}
                },
                "required": ["location"]
            }
        }
    }
    try:
        tool_call_response = await adapter.chat_completion(
            messages=[{"role": "user", "content": "What's the weather like in London?"}],
            tools=[weather_tool],
            tool_choice="auto",
            stream=False # Easier to handle tool calls non-streamed
        )

        message = tool_call_response.choices[0].message
        if message.tool_calls:
            print("Model requested tool call(s):")
            for tc in message.tool_calls:
                print(f"  ID: {tc.id}, Function: {tc.function.name}, Args: {tc.function.arguments}")
            print("--> Next step: Execute the function(s) and send results back in a new API call.")
        else:
            print(f"Model answered directly: {message.content}")
        print("--------------------\n")
    except Exception as e: print(f"ERROR: {e}")


if __name__ == "__main__":
    # Set logger level to DEBUG for more verbose output during testing
    # logging.getLogger(__name__).setLevel(logging.DEBUG)
    asyncio.run(_run_adapter_examples())