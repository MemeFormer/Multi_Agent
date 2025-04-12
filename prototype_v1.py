import asyncio
import subprocess
import os
import logging
from src.adapters.groq_adapter import GroqAdapter # Assuming adapter is here

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
TEST_FILENAME = "test_file.txt"
INITIAL_CONTENT = "hello world, hello there."
TASK_DESCRIPTION = f"Using a bash command (like sed), replace all occurrences of the word 'hello' with 'goodbye' in the file named '{TEST_FILENAME}'."

# --- Helper Functions ---

def setup_test_file():
    """Creates the initial test file."""
    try:
        with open(TEST_FILENAME, "w") as f:
            f.write(INITIAL_CONTENT)
        logging.info(f"Created test file '{TEST_FILENAME}' with initial content.")
    except IOError as e:
        logging.error(f"Error creating test file: {e}", exc_info=True)
        raise

def read_test_file():
    """Reads the content of the test file."""
    try:
        with open(TEST_FILENAME, "r") as f:
            content = f.read()
        logging.info(f"Current content of '{TEST_FILENAME}': '{content}'")
        return content
    except IOError as e:
        logging.error(f"Error reading test file: {e}", exc_info=True)
        return f"Error reading file: {e}"

def execute_command(command: str) -> bool:
    """Executes the approved bash command."""
    logging.info(f"Attempting to execute command: {command}")
    try:
        # Using shell=True is necessary for pipelines, redirects etc.
        # Be cautious with it in production - ensure commands are validated.
        result = subprocess.run(
            command,
            shell=True,
            check=True, # Raises CalledProcessError on non-zero exit code
            capture_output=True, # Capture stdout/stderr
            text=True # Decode stdout/stderr as text
        )
        logging.info(f"Command executed successfully. STDOUT:\n{result.stdout}")
        if result.stderr:
             logging.warning(f"Command STDERR:\n{result.stderr}")
        return True
    except FileNotFoundError:
         logging.error(f"Error: Command not found (invalid command or PATH issue?) - Command: '{command}'")
         return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with exit code {e.returncode}. Command: '{command}'")
        logging.error(f"STDERR:\n{e.stderr}")
        logging.error(f"STDOUT:\n{e.stdout}")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during command execution: {e}", exc_info=True)
        return False

# --- Simulated Agent Functions ---

async def junior_propose_plan(adapter: GroqAdapter, task: str) -> str | None:
    """Simulates Junior agent proposing a bash command plan."""
    logging.info("Junior Agent: Proposing execution plan...")
    prompt = f"""
    Given the following task, generate ONLY the single, precise bash command needed to accomplish it.
    Do not include explanations, just the command itself.
    Use standard tools like 'sed'. Assume the file is in the current directory.

    Task: {task}

    Bash Command:
    """
    messages = [{"role": "user", "content": prompt}]

    try:
        # Using prefill to encourage just the command output
        response_gen = await adapter.chat_completion(
            messages=messages,
            temperature=0.1, # Low temp for predictable command generation
            max_tokens=100,
            stream=True, # Stream to get output faster / potentially stop early
            prefill_content="", # No specific prefill needed here if prompt is clear
            # stop=["\n"] # Optional: Try stopping at the first newline
        )

        proposed_command = ""
        async for chunk in response_gen:
             proposed_command += chunk
        proposed_command = proposed_command.strip() # Clean up whitespace

        # Basic validation - ensure it's not empty and looks like a command
        if not proposed_command or ' ' not in proposed_command:
             logging.error(f"Junior Agent: LLM generated invalid/empty command: '{proposed_command}'")
             return None

        logging.info(f"Junior Agent: Proposed command: `{proposed_command}`")
        return proposed_command
    except Exception as e:
        logging.error(f"Junior Agent: Error during plan proposal: {e}", exc_info=True)
        return None

async def senior_review_plan(adapter: GroqAdapter, command: str, task: str) -> tuple[bool, str]:
    """Simulates Senior agent reviewing the command."""
    logging.info(f"Senior Agent: Reviewing command: `{command}`")
    prompt = f"""
    Review the following bash command intended to accomplish the task described.
    Is the command technically correct, safe for execution in the current directory, and likely to achieve the task?
    Focus on correctness and safety for this specific task and file ('{TEST_FILENAME}').

    Task: {task}
    Proposed Bash Command: `{command}`

    Your Response: Start your response with either "APPROVAL: YES" or "APPROVAL: NO".
    Then, optionally provide a brief justification or suggested correction on the next line.
    Example APPROVAL: YES\nLooks correct for replacing all occurrences with sed -i.
    Example APPROVAL: NO\nThe sed syntax is missing the -i flag for in-place edit or redirection.
    """
    messages = [{"role": "user", "content": prompt}]
    feedback = "No feedback received."
    approved = False

    try:
        response = await adapter.chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=100,
            stream=False # Need full response to parse APPROVAL
        )
        review_text = response.choices[0].message.content.strip()
        logging.info(f"Senior Agent: Raw review response: '{review_text}'")

        # Parse the approval status
        if review_text.upper().startswith("APPROVAL: YES"):
            approved = True
            feedback = review_text[len("APPROVAL: YES"):].strip()
            logging.info(f"Senior Agent: Plan APPROVED. Feedback: {feedback}")
        elif review_text.upper().startswith("APPROVAL: NO"):
            approved = False
            feedback = review_text[len("APPROVAL: NO"):].strip()
            logging.warning(f"Senior Agent: Plan REJECTED. Feedback: {feedback}")
        else:
             logging.warning(f"Senior Agent: Could not parse approval status from response: '{review_text}'")
             feedback = f"Unparsable response: {review_text}"
             approved = False # Default to not approved if unsure

        return approved, feedback
    except Exception as e:
        logging.error(f"Senior Agent: Error during plan review: {e}", exc_info=True)
        return False, f"Error during review: {e}"


# --- Main Orchestration Logic ---

async def main():
    """Runs the prototype workflow."""
    logging.info("--- Starting Prototype V1 ---")
    adapter = GroqAdapter() # Assumes GROQ_API_KEY is set

    # 1. Setup
    setup_test_file()
    read_test_file() # Log initial state

    # 2. Junior Proposes Plan
    proposed_command = await junior_propose_plan(adapter, TASK_DESCRIPTION)

    if not proposed_command:
        logging.error("Workflow failed: Junior could not propose a plan.")
        return

    # 3. Senior Reviews Plan
    is_approved, feedback = await senior_review_plan(adapter, proposed_command, TASK_DESCRIPTION)

    # 4. Execute if Approved
    if is_approved:
        logging.info("Executing approved command...")
        success = execute_command(proposed_command)
        if success:
            logging.info("Command execution reported success.")
        else:
            logging.error("Command execution reported failure.")
    else:
        logging.warning(f"Workflow halted: Plan rejected by Senior Agent. Feedback: {feedback}")

    # 5. Final State
    logging.info("--- Reading final file state ---")
    read_test_file()
    logging.info("--- Prototype V1 Finished ---")

    # Optional: Clean up the test file
    # try:
    #     os.remove(TEST_FILENAME)
    #     logging.info(f"Cleaned up test file '{TEST_FILENAME}'.")
    # except OSError as e:
    #     logging.warning(f"Could not clean up test file: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    