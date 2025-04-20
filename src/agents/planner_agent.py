# src/agents/planner_agent.py

import logging
import json
from typing import Optional
from groq import GroqError
from pydantic import ValidationError

from src.adapters.groq_adapter import GroqAdapter
from src.models.word_action_plan import WordActionPlan
from src.models.check_plan import CheckPlan
from src.models.check_result import CheckResult
from src.models.read_file_plan import ReadFilePlan # <-- Added for Phase 5
from src.models.write_file_plan import WriteFilePlan # <-- Added for Phase 6
from src.models.apply_patch_plan import ApplyPatchPlan # <-- Added for Phase 9
from groq.types.chat.chat_completion import ChatCompletion


# Configure logging
# Consider moving basicConfig to the main script entry point if not already done
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__) # Get logger instance

class PlannerAgent:
    """
    Agent responsible for analyzing input and creating structured plans.
    Handles word game logic (check, conditional add) and file reading planning.
    """
    def __init__(self, adapter: GroqAdapter, model_id: str, temperature: float = 0.2, max_tokens: int = 500):
        """
        Initializes the Planner Agent.

        Args:
            adapter: Instance of GroqAdapter.
            model_id: The LLM model ID to use for planning (e.g., deepseek-r1-distill-llama-70b).
            temperature: Sampling temperature.
            max_tokens: Max tokens for the plan generation.
        """
        self.adapter = adapter
        self.model_id = model_id
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"PlannerAgent initialized with model: {self.model_id}")

    # --- Word Game Methods (Phase 2 logic) ---

    async def plan_check_task(self, word: str) -> Optional[CheckPlan]:
        """
        Plans a task to check which bin a word belongs to based on its first letter.

        Args:
            word: The input word to check.

        Returns:
            A CheckPlan object if successful, None otherwise.
        """
        logger.info(f"Planner Agent ({self.model_id}) planning check for word: '{word}'")

        try:
            check_plan_schema_str = json.dumps(CheckPlan.model_json_schema(), indent=2)
        except Exception as e:
            logger.error(f"Failed to generate CheckPlan JSON schema: {e}", exc_info=True)
            return None

        system_prompt = f"""
You are a meticulous Planner Agent. Your task is to analyze the given input word and create a plan to CHECK which bin it belongs to based on its first letter.

**Rule:**
- If the word starts with a vowel (A, E, I, O, U, case-insensitive), the `bin_name` to check is "Vowel Bin".
- If the word starts with a consonant, the `bin_name` to check is "Consonant Bin".

Your plan MUST instruct the Executor to perform a "check_bin" action.

You MUST output your plan as a valid JSON object conforming EXACTLY to the following `CheckPlan` schema. Include the original word and the determined `bin_name`.

**`CheckPlan` Schema:**
```json
{check_plan_schema_str}
```

Generate ONLY the JSON object. Do not add introductory text, comments, or markdown formatting around the JSON.
"""
        user_prompt = f"""
Input Word: "{word}"

Generate the CheckPlan JSON object:
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response_plan: Optional[CheckPlan] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_schema=CheckPlan
            )

            if response_plan and isinstance(response_plan, CheckPlan):
                logger.info(f"Planner proposed check plan: Word='{response_plan.word}', Action='{response_plan.action}', Bin='{response_plan.bin_name}'")
                # Optional validation: Ensure word matches if needed
                return response_plan
            else:
                logger.error("Planner chat_completion did not return a valid CheckPlan object.")
                return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Planner agent failed during check plan proposal: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Planner unexpected error during plan_check_task: {e}", exc_info=True)
            return None

    async def plan_final_add_task(self, word: str, check_result: CheckResult) -> Optional[WordActionPlan]:
        """
        Plans the final action (adding the word) based on the result of a prior check.

        Args:
            word: The original word being processed.
            check_result: The result from the execute_check action.

        Returns:
            A WordActionPlan to add the word if it wasn't present, otherwise None.
        """
        logger.info(f"Planner Agent ({self.model_id}) planning final action for word: '{word}' based on check result: {check_result.status}")

        if check_result.status == "Present":
            logger.info(f"Word '{word}' already present in '{check_result.bin_checked}'. No add plan needed.")
            return None # Correctly skip planning if already present

        # Only proceed to LLM if check_result status is "Not Present"
        try:
            word_action_plan_schema_str = json.dumps(WordActionPlan.model_json_schema(), indent=2)
        except Exception as e:
            logger.error(f"Failed to generate WordActionPlan JSON schema: {e}", exc_info=True)
            return None

        system_prompt = f"""
You are a meticulous Planner Agent. You received the result of a check for a word in its target bin. Your task is to create a final plan to ADD the word to the bin **only if** the check result indicates the word was "Not Present".

**Input Information:**
- Original Word: "{word}"
- Bin Checked: "{check_result.bin_checked}"
- Check Result Status: "{check_result.status}"

**Rule:**
- **If** `Check Result Status` is "Not Present", create a plan to add the `Original Word` to the `Bin Checked`. The plan MUST be a JSON object conforming to the `WordActionPlan` schema.
- **If** `Check Result Status` is "Present", DO NOT generate a plan. Output nothing.

**`WordActionPlan` Schema (Only generate if status is "Not Present"):**
```json
{word_action_plan_schema_str}
```

Generate ONLY the `WordActionPlan` JSON object IF the word was "Not Present". Otherwise, provide no output.
"""
        user_prompt = f"""
Check Result Details:
Word: {check_result.word}
Bin Checked: {check_result.bin_checked}
Status: {check_result.status}

Generate the WordActionPlan JSON object for adding the word if and only if the status was "Not Present":
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response_plan: Optional[WordActionPlan] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_schema=WordActionPlan
            )

            if response_plan and isinstance(response_plan, WordActionPlan):
                # Optional validation
                if response_plan.word_to_process == word and response_plan.target_bin == check_result.bin_checked:
                     logger.info(f"Planner proposed final add plan: Word='{response_plan.word_to_process}', Target Bin='{response_plan.target_bin}'")
                     return response_plan
                else:
                     logger.warning(f"Planner generated add plan with mismatched details: Plan={response_plan}. Discarding.")
                     return None
            elif response_plan is None:
                logger.info("Planner returned no add plan (expected if word was present or LLM output was empty/invalid).")
                return None
            else:
                 logger.error(f"Planner chat_completion returned unexpected type: {type(response_plan)}")
                 return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Planner agent failed during final add plan proposal: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Planner unexpected error during plan_final_add_task: {e}", exc_info=True)
            return None

    # --- File Reading Methods (Phase 5) ---

    async def plan_read_file_task(self, file_path_to_read: str) -> Optional[ReadFilePlan]:
        """
        Plans a task to read the content of a specified file.

        Args:
            file_path_to_read: The path to the file to be read.

        Returns:
            A ReadFilePlan object if successful, None otherwise.
        """
        logger.info(f"Planner Agent ({self.model_id}) planning file read for: '{file_path_to_read}'")

        # --- REMOVED schema generation block ---

        # --- Use simplified prompts ---
        system_prompt = """
You are a Planner Agent. Your task is to create a JSON plan for the Executor Agent to read the content of a specified file.
The plan MUST use the action "read_file".
The JSON object you output MUST contain the fields 'action' (with value 'read_file') and 'file_path' (with the specified file path).
Generate ONLY the JSON object instance.
"""
        user_prompt = f"""
Create the JSON plan to read the file: "{file_path_to_read}"
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # The rest of the try/except block calling adapter.chat_completion remains the same
        try:
            response_plan: Optional[ReadFilePlan] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens, # Adjust if needed
                json_schema=ReadFilePlan
            )

            if response_plan and isinstance(response_plan, ReadFilePlan):
                 # Optional validation
                 if response_plan.file_path != file_path_to_read:
                      logger.warning(f"Planner returned plan for different file path: '{response_plan.file_path}' instead of '{file_path_to_read}'. Using returned path.")
                      # Decide how to handle this - for now, proceed with the path the LLM returned
                 logger.info(f"Planner proposed read file plan: Path='{response_plan.file_path}', Action='{response_plan.action}'")
                 return response_plan
            else:
                logger.error("Planner chat_completion did not return a valid ReadFilePlan object.")
                return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Planner agent failed during read file plan proposal: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Planner unexpected error during plan_read_file_task: {e}", exc_info=True)
            return None

    async def plan_write_file_task(self, file_path: str, content: str) -> Optional[WriteFilePlan]:
        """ Plans a task to write content to a specified file. """
        logger.info(f"Planner Agent ({self.model_id}) planning file write for: '{file_path}'")
        # Be cautious about logging large content strings
        content_preview = content[:100].replace('\n', '\\n') + ('...' if len(content) > 100 else '')
        logger.debug(f"Content preview for plan: '{content_preview}'")

        # Use simplified prompt structure (no schema in text)
        system_prompt = """
You are a Planner Agent. Create a JSON plan for the Executor Agent to write provided content to a specified file, overwriting existing content.
The plan MUST use the action "write_file".
The JSON object you output MUST contain the fields 'action', 'file_path', and 'content'.
Generate ONLY the JSON object instance.
"""
        # Pass content in the user prompt. Be mindful of token limits for very large content.
        # For extremely large content, a different approach (e.g., passing a reference or using streaming)
        # might be needed in a real application, but this works for moderate content.
        user_prompt = f"""
Create the JSON plan to write the following content to the file "{file_path}":

Content:
{content}
"""
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        try:
            response_plan: Optional[WriteFilePlan] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens, # May need increasing if content is large
                json_schema=WriteFilePlan
            )

            if response_plan and isinstance(response_plan, WriteFilePlan):
                 # Optional validation: Check file_path and maybe content hash/preview?
                 if response_plan.file_path != file_path:
                      logger.warning(f"Planner returned plan for different file path: '{response_plan.file_path}' instead of '{file_path}'. Using returned path.")
                 # Add a check for content match (or preview match) if desired
                 # if response_plan.content != content:
                 #     logger.warning(f"Planner returned plan with different content.")
                 logger.info(f"Planner proposed write file plan: Path='{response_plan.file_path}', Action='{response_plan.action}'")
                 return response_plan
            else:
                logger.error("Planner chat_completion did not return a valid WriteFilePlan object.")
                return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Planner agent failed during write file plan proposal: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Planner unexpected error during plan_write_file_task: {e}", exc_info=True)
            return None

    async def plan_modify_file_task(self, file_path: str, original_content: str) -> Optional[WriteFilePlan]:
        """
        Plans a task to modify file content (e.g., appending a line) and
        outputs a WriteFilePlan with the *entire new* content.
        """
        logger.info(f"Planner Agent ({self.model_id}) planning file modification for: '{file_path}'")
        # Preview only the first 100 characters to avoid excessive logging
        content_preview = original_content[:100].replace('\n', '\\n') + ('...' if len(original_content) > 100 else '')
        logger.debug(f"Original content preview for modification plan: '{content_preview}'")

        # --- Generate line-numbered context for the prompt ---
        lines_list = original_content.splitlines()
        lines_dict = {i + 1: line for i, line in enumerate(lines_list)}
        # Create a string representation for the prompt
        line_numbered_content_for_prompt = "\n".join(f"{ln}: {line}" for ln, line in lines_dict.items())
        last_line_number = len(lines_dict) if lines_dict else 0
        # --- End line-numbered context generation ---

        system_prompt = f"""
You are a Planner Agent specializing in file modifications.
Your task is to take the provided original file content (shown with line numbers) and modify it by appending the exact line "-- Modified by Planner (v8) --" *after the last line* (line {last_line_number}).
Then, create a JSON plan for the Executor Agent to write the *entire modified content* back to the original file path.
The plan MUST use the action "write_file".
The JSON object you output MUST contain 'action', 'file_path', and 'content' (the full modified text).
Generate ONLY the JSON object instance.
"""

        user_prompt = f"""
File Path: "{file_path}"
Last Line Number: {last_line_number}

Original Content (with line numbers for reference):
{line_numbered_content_for_prompt}

Modify the content by appending the exact line "-- Modified by Planner (v8) --" after line {last_line_number}.
Create the JSON plan (WriteFilePlan) containing the full modified content:
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response_plan: Optional[WriteFilePlan] = await self.adapter.chat_completion(
                model=self.model_id,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                json_schema=WriteFilePlan
            )

            if response_plan and isinstance(response_plan, WriteFilePlan):
                if response_plan.file_path != file_path:
                    logger.warning(
                        f"Planner returned plan for different file path: '{response_plan.file_path}' "
                        f"instead of '{file_path}'. Using returned path."
                    )
                logger.info(f"Planner proposed modified write plan for: '{response_plan.file_path}'")
                # Debug preview of the modified content
                modified_content_preview = response_plan.content[:100].replace('\n', '\\n') \
                    + ('...' if len(response_plan.content) > 100 else '')
                logger.debug(f"Modified content preview in plan: '{modified_content_preview}'")
                return response_plan

            logger.error("Planner chat_completion did not return a valid WriteFilePlan for modification.")
            return None

        except (GroqError, ValueError, ValidationError, json.JSONDecodeError) as e:
            logger.error(f"Planner agent failed during modify file plan proposal: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Planner unexpected error during plan_modify_file_task: {e}", exc_info=True)
            return None

    # --- Patching Methods (Phase 9) ---

    async def plan_apply_patch_task(
        self,
        file_path: str,
        original_content: str,
        modification_request: str, # The user's request, e.g., "Refactor function X", "Add a print statement"
        # Optional: Add lines_dict: Optional[Dict[int, str]] = None if useful for prompt context
    ) -> Optional[ApplyPatchPlan]:
        """
        Plans a task to generate a V4A diff patch based on a modification request.

        Args:
            file_path: The path to the file to be modified.
            original_content: The original content of the file.
            modification_request: The user's request describing the desired change.

        Returns:
            An ApplyPatchPlan object containing the generated patch content if successful, None otherwise.
        """
        logger.info(f"Planner Agent ({self.model_id}) planning apply patch task for: '{file_path}'")
        logger.debug(f"Modification request: '{modification_request}'")

        system_prompt = """
You are an expert, meticulous software developer AI assistant. Your task is to generate a precise V4A diff patch to modify a given file based on a user request.

**Workflow:**
1.  Deeply understand the modification request.
2.  Carefully analyze the provided original code content.
3.  Identify the exact lines and context needing change.
4.  Generate a V4A format patch containing ONLY the necessary changes.

**V4A Diff Format Rules:**
- Start the entire patch with `*** Begin Patch`.
- End the entire patch with `*** End Patch`.
- Specify the file operation: `*** Update File: [path/to/file]`. Use the provided file path.
- For each change block:
    - Use `@@ ClassOrFunction` markers ONLY if needed to disambiguate context within the file. Often, no `@@` marker is needed if the context lines are unique.
    - Provide exactly 3 lines of unchanged context before the change (unless at file start or near previous change).
    - Mark lines to be removed with `- ` (minus sign followed by a space).
    - Mark lines to be added with `+ ` (plus sign followed by a space).
    - Provide exactly 3 lines of unchanged context after the change (unless at file end or near next change).
    - Do NOT duplicate context lines between adjacent change blocks.
- Ensure correct indentation for all lines (+, -, context).

**CRITICAL Constraint:**
- **DO NOT** use standard unified diff hunk headers like `@@ -x,y +a,b @@`. Only use `@@ ClassOrFunction` if *absolutely necessary* for context, otherwise rely on the 3 context lines.

**Example:**
If the original content is:
```
Line 1: A
Line 2: B
Line 3: C
Line 4: D
```
And the request is "Insert 'Line 2.5: New' between Line 2 and Line 3", the correct V4A patch is:
```
*** Begin Patch
*** Update File: [path/to/file]
 Line 1: A
 Line 2: B
+Line 2.5: New
 Line 3: C
 Line 4: D
*** End Patch
```
(Note: No `@@` marker was needed here as the context was sufficient)

**Your Task:**
Generate ONLY the V4A patch string based on the user request and original content, starting with `*** Begin Patch` and ending with `*** End Patch`.
**Do NOT include any reasoning, <think> tags, or any other text outside the patch markers.**
"""

        user_prompt = f"""
    File Path: "{file_path}"

    Modification Request: "{modification_request}"

    Original Content:
    """

   
        messages = [{"role": "system", "content": system_prompt}, 
                    {"role": "user", "content": user_prompt}]

        try:
            # Get the completion object from the adapter (no json_schema specified)
            # Add 'from groq.types.chat.chat_completion import ChatCompletion' at the top if needed
            completion_object: Optional['ChatCompletion'] = await self.adapter.chat_completion( # Type hint might need import
                model=self.model_id, messages=messages, temperature=0.0, max_tokens=self.max_tokens # <--- Use self.max_tokens
                # NO json_schema parameter here
            )

            if not completion_object:
                logger.error("Planner received no response object from adapter.")
                return None

            # --- Extract the string content from the completion object ---
            raw_patch_content: Optional[str] = None
            try:
                 if completion_object.choices and completion_object.choices[0].message and completion_object.choices[0].message.content:
                     raw_patch_content = completion_object.choices[0].message.content
                     logger.info("Successfully extracted text content from LLM response.")
                     logger.debug(f"Raw patch content received from LLM:\n---\n{raw_patch_content}\n---")
                 else:
                     logger.error(f"Could not extract message content from completion object structure: {completion_object}")
                     return None
            except AttributeError as e:
                 logger.error(f"Error accessing content in completion object: {e}. Object: {completion_object}")
                 return None
            # ---------------------------------------------------------------

            if not raw_patch_content:
                # This case means content was extracted but is empty
                logger.error("Planner received empty patch content string from LLM.")
                return None

            # --- Line-based validation and extraction ---
            logger.debug(f"Attempting line-based validation of raw patch content:\n{raw_patch_content[:500]}...")
            start_marker = "*** Begin Patch"
            end_marker = "*** End Patch"
            validated_patch_content: Optional[str] = None
            patch_lines: List[str] = [] # Need from typing import List
            in_patch_block = False

            lines = raw_patch_content.splitlines() # Split into lines

            for line in lines:
                stripped_line = line.strip() # Use stripped line for marker checks

                if stripped_line == start_marker:
                    if in_patch_block:
                        logger.warning(f"Found nested '{start_marker}'? Ignoring previous.")
                        patch_lines = [] # Restart if nested start found
                    in_patch_block = True
                    patch_lines.append(line) # Add original line (with whitespace)
                    continue # Move to next line

                if in_patch_block:
                    patch_lines.append(line) # Add original line
                    if stripped_line == end_marker:
                        # Found the end marker, potentially the end of the patch
                        # Check if any non-whitespace comes *after* this line?
                        # For simplicity now, we'll assume this is the correct end.
                        break # Stop processing lines once end marker is found

            # After loop, check if we found a valid block
            if not patch_lines or patch_lines[-1].strip() != end_marker:
                logger.error(f"Could not extract a valid block ending with '{end_marker}'. Last few lines processed: {lines[-5:]}")
                return None # Failed to find valid block
            else:
                # Join the extracted lines back together
                validated_patch_content = "\n".join(patch_lines)
                logger.debug(f"Extracted Patch Content (line-based):\n{validated_patch_content}")
            # --- End Line-based validation ---

            # Basic check: Ensure the file path mentioned in the patch matches the input
            # This check now runs on the potentially valid 'validated_patch_content'
            expected_update_line = f"*** Update File: {file_path}"
            if expected_update_line not in validated_patch_content:
                 # Also check for Add/Delete if those were possibilities based on request
                 expected_add_line = f"*** Add File: {file_path}"
                 expected_delete_line = f"*** Delete File: {file_path}"
                 if not any(marker in validated_patch_content for marker in [expected_add_line, expected_delete_line]):
                      logger.warning(f"Patch content does not seem to reference the correct file path '{file_path}'. Patch:\n{validated_patch_content}")
                      # Decide whether to proceed or fail. Let's fail for now.
                      # return None # Or maybe proceed cautiously?

            # Create the plan object
            plan = ApplyPatchPlan(
                action="apply_patch",
                patch_content=validated_patch_content,
                reasoning=f"Apply patch to '{file_path}' based on request: {modification_request}" # Add simple reasoning
            )
            logger.info(f"Planner proposed apply patch plan for: '{file_path}'")
            return plan

        except (GroqError, ValueError) as e: # Catch API errors or value errors during processing
            logger.error(f"Planner agent failed during apply patch plan proposal: {e}", exc_info=True)
            return None
        except Exception as e: # Catch unexpected errors
            logger.error(f"Planner unexpected error during plan_apply_patch_task: {e}", exc_info=True)
            return None


    # --- Deprecated Methods ---

    async def _plan_word_task_deprecated(self, word: str) -> Optional[WordActionPlan]:

        """
        DEPRECATED: Original single-step word planning. Not used in Phase 2+.
        """
        logger.warning("Called deprecated method _plan_word_task_deprecated")
        # Implementation removed or commented out
        return None
