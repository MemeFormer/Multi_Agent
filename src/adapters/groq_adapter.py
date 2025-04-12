# src/adapters/groq_adapter.py
# VERSION WITH EXAMPLE CODE REMOVED

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
    tool usage, response prefilling, and reasoning format control based on provided parameters.
    """
    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None): # Removed default model value
        """
        Initializes the AsyncGroq client.
        Args:
            api_key: Groq API key. Defaults to reading from the
                     GROQ_API_KEY environment variable.
            default_model: A default Groq model ID. This is stored but typically
                           overridden by the 'model' parameter in chat_completion.
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable not set or passed.")

        self.default_model = default_model # Store default if provided
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            # Log if a default was provided during init, but emphasize it's usually overridden
            log_msg = "GroqAdapter initialized."
            if self.default_model:
                log_msg += f" (Default model set to: {self.default_model}, often overridden by specific calls)"
            logger.info(log_msg)
        except Exception as e:
            logger.error(f"Failed to initialize AsyncGroq client: {e}", exc_info=True)
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None, # Model should always be provided by the caller (agent)
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        top_p: float = 1.0,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        json_schema: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict]] = None,
        prefill_content: Optional[str] = None,
        reasoning_format: Optional[str] = None
    ) -> Union[AsyncGenerator[str, None], Any, BaseModel]:
        """
        Makes an asynchronous call to the Groq Chat Completions API with options.
        Args:
            messages: Conversation history.
            model: Specific model ID to use for this call (REQUIRED).
            # ... other args ...
            reasoning_format: Controls reasoning output ('parsed', 'raw', 'hidden').

        Returns:
            # ... return types ...
        Raises:
            ValueError: For invalid parameter combinations, missing model, or validation errors.
            GroqError: For API-related errors.
        """
        # CRITICAL: Ensure a model is explicitly passed for every call
        selected_model = model
        if not selected_model:
             # Raise error immediately if no model specified for the call
             raise ValueError("The 'model' parameter is required for chat_completion calls.")

        effective_messages = list(messages) # Copy
        api_params: Dict[str, Any] = {
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stop": stop,
        }

        # --- Parameter Handling & Validation ---
        using_json_mode = bool(json_schema)
        using_tools = bool(tools)

        if prefill_content:
            # ... (prefill logic remains the same) ...
            effective_messages.append({"role": "assistant", "content": prefill_content})
            logger.info(f"Prefilling assistant message starting with: '{prefill_content[:50]}...'")
            if stop is None and (prefill_content.strip().endswith("```python") or prefill_content.strip().endswith("```json")):
                api_params["stop"] = "```"
                logger.info("Automatically setting stop sequence to '```' due to prefill format.")


        if reasoning_format:
            # ... (reasoning_format logic remains the same) ...
            if reasoning_format not in ["parsed", "raw", "hidden"]:
                 logger.warning(f"Invalid reasoning_format value '{reasoning_format}'. Ignoring. Valid options: 'parsed', 'raw', 'hidden'.")
            else:
                if reasoning_format == "raw" and (using_json_mode or using_tools):
                     raise ValueError("reasoning_format cannot be 'raw' when using JSON mode or tools. Use 'parsed' or 'hidden'.")
                api_params["reasoning_format"] = reasoning_format
                logger.info(f"Setting reasoning_format to '{reasoning_format}'.")

        if using_json_mode:
            # ... (JSON mode logic remains the same) ...
            if stream:
                raise ValueError("Streaming (stream=True) is not supported with JSON mode (json_schema provided).")
            if using_tools:
                 raise ValueError("Tool use (tools provided) cannot be combined with JSON mode (json_schema provided) in a single call.")
            api_params["response_format"] = {"type": "json_object"}
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
            api_params["stream"] = False

        elif using_tools:
            # ... (Tool use logic remains the same) ...
            if stream:
                logger.warning("Streaming with tool use. Parsing streamed tool calls can be complex.")
            api_params["tools"] = tools
            api_params["tool_choice"] = tool_choice or "auto"
            api_params["stream"] = stream
            logger.info(f"Tool use enabled with tool_choice='{api_params['tool_choice']}'.")

        else:
             if "stream" not in api_params:
                 api_params["stream"] = stream

        api_params["messages"] = effective_messages
        logger.debug(f"Calling Groq API: Params={api_params}")

        # --- API Call Execution & Response Handling ---
        try:
            completion = await self.client.chat.completions.create(**api_params)
            is_streaming = api_params.get("stream", False)

            if is_streaming:
                logger.info("Streaming response...")
                return self._handle_stream(completion)
            elif using_json_mode:
                logger.info("Processing JSON mode response...")
                if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                    response_content = completion.choices[0].message.content
                    return self._validate_json_response(response_content, json_schema)
                else:
                    logger.error("JSON mode response missing content.")
                    raise ValueError("Received response suitable for JSON mode, but content was missing.")
            else:
                logger.info("Returning non-streamed response object.")
                if completion.choices and completion.choices[0].message and completion.choices[0].message.tool_calls:
                     logger.info(f"Response contains tool calls: {completion.choices[0].message.tool_calls}")
                if completion.choices and completion.choices[0].finish_reason:
                     logger.info(f"Finish reason: {completion.choices[0].finish_reason}")
                return completion

        # --- Error Handling ---
        # ... (Error handling remains the same) ...
        except GroqError as e:
            logger.error(f"Groq API error: {e.status_code} - {e.message}", exc_info=True)
            is_streaming_error_context = api_params.get("stream", False) # Use final stream value for context
            logger.error(f"Failed API call details (limited): Model='{selected_model}', Stream={is_streaming_error_context}, JSONMode={using_json_mode}, Tools={using_tools}")
            raise
        except ValidationError as e:
            logger.error(f"JSON validation failed: {e}", exc_info=True)
            raw_content = "N/A"
            if 'completion' in locals() and completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                 raw_content = completion.choices[0].message.content
            raise ValueError(f"LLM output failed Pydantic validation for {json_schema.__name__}. Errors: {e}. Raw response: '{raw_content}'") from e
        except json.JSONDecodeError as e:
             logger.error(f"Failed to decode JSON response: {e}", exc_info=True)
             raw_content = "N/A"
             if 'completion' in locals() and completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                  raw_content = completion.choices[0].message.content
             raise ValueError(f"LLM response was not valid JSON. Error: {e}. Raw response: '{raw_content}'") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during Groq API call: {e}", exc_info=True)
            raise


    async def _handle_stream(self, stream_completion) -> AsyncGenerator[str, None]:
        # ... (Stream handling remains the same) ...
        try:
             async for chunk in stream_completion:
                 if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                     yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error during stream processing: {e}", exc_info=True)
            raise
        finally:
             logger.info("Stream processing finished or encountered an error.")


    def _validate_json_response(self, response_content: str, json_schema: Type[BaseModel]) -> BaseModel:
         # ... (JSON validation remains the same) ...
        try:
            logger.debug(f"Raw JSON received for validation:\n{response_content}")
            validated_data = json_schema.model_validate_json(response_content)
            logger.info(f"Successfully validated JSON response against '{json_schema.__name__}'.")
            return validated_data
        except (ValidationError, json.JSONDecodeError) as e:
            raise e

# --- NO EXAMPLE CODE BELOW THIS LINE ---
# The _run_adapter_examples function and the
# if __name__ == "__main__": block have been completely removed.
