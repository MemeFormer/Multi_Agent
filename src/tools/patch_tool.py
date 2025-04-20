#!/usr/bin/env python3

"""
A self-contained **pure-Python 3.9+** utility for applying human-readable
“pseudo-diff” patch files to a collection of text files.

(Adapted from OpenAI Codex Cookbook example)
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)


# --------------------------------------------------------------------------- #
#  Domain objects
# --------------------------------------------------------------------------- #
class ActionType(str, Enum):
    ADD = "add"
    DELETE = "delete"
    UPDATE = "update"


@dataclass
class FileChange:
    type: ActionType
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    move_path: Optional[str] = None


@dataclass
class Commit:
    changes: Dict[str, FileChange] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
#  Exceptions
# --------------------------------------------------------------------------- #
class DiffError(ValueError):
    """Any problem detected while parsing or applying a patch."""


# --------------------------------------------------------------------------- #
#  Helper dataclasses used while parsing patches
# --------------------------------------------------------------------------- #
@dataclass
class Chunk:
    orig_index: int = -1
    del_lines: List[str] = field(default_factory=list)
    ins_lines: List[str] = field(default_factory=list)


@dataclass
class PatchAction:
    type: ActionType
    new_file: Optional[str] = None
    chunks: List[Chunk] = field(default_factory=list)
    move_path: Optional[str] = None


@dataclass
class Patch:
    actions: Dict[str, PatchAction] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
#  Patch text parser
# --------------------------------------------------------------------------- #
@dataclass
class Parser:
    current_files: Dict[str, str]
    lines: List[str]
    index: int = 0
    patch: Patch = field(default_factory=Patch)
    fuzz: int = 0

    # ------------- low-level helpers -------------------------------------- #
    def _cur_line(self) -> str:
        if self.index >= len(self.lines):
            raise DiffError("Unexpected end of input while parsing patch")
        return self.lines[self.index]

    @staticmethod
    def _norm(line: str) -> str:
        """Strip CR so comparisons work for both LF and CRLF input."""
        return line.rstrip("\r")

    # ------------- scanning convenience ----------------------------------- #
    def is_done(self, prefixes: Optional[Tuple[str, ...]] = None) -> bool:
        if self.index >= len(self.lines):
            return True
        if (
            prefixes
            and len(prefixes) > 0
            and self._norm(self._cur_line()).startswith(prefixes)
        ):
            return True
        return False

    def startswith(self, prefix: Union[str, Tuple[str, ...]]) -> bool:
        return self._norm(self._cur_line()).startswith(prefix)

    def read_str(self, prefix: str) -> str:
        """
        Consume the current line if it starts with *prefix* and return the text
        **after** the prefix. Raises if prefix is empty.
        """
        if prefix == "":
            raise ValueError("read_str() requires a non-empty prefix")
        if self._norm(self._cur_line()).startswith(prefix):
            text = self._cur_line()[len(prefix) :]
            self.index += 1
            return text
        return "" # Return empty string if prefix doesn't match

    def read_line(self) -> str:
        """Return the current raw line and advance."""
        line = self._cur_line()
        self.index += 1
        return line

    # ------------- public entry point -------------------------------------- #
    def parse(self) -> None:
        while not self.is_done(("*** End Patch",)):
            # ---------- UPDATE ---------- #
            path = self.read_str("*** Update File: ")
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate update for file: {path}")
                # Handle optional move_to immediately after Update File line
                move_to = self.read_str("*** Move to: ")
                if path not in self.current_files:
                    raise DiffError(f"Update File Error - missing file: {path}")
                text = self.current_files[path]
                action = self._parse_update_file(text)
                action.move_path = move_to or None # Assign move_path if present
                self.patch.actions[path] = action
                continue

            # ---------- DELETE ---------- #
            path = self.read_str("*** Delete File: ")
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate delete for file: {path}")
                if path not in self.current_files:
                    # Allow deleting non-existent files? Or raise? Raising for now.
                    raise DiffError(f"Delete File Error - missing file: {path}")
                self.patch.actions[path] = PatchAction(type=ActionType.DELETE)
                continue

            # ---------- ADD ---------- #
            path = self.read_str("*** Add File: ")
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Duplicate add for file: {path}")
                if path in self.current_files:
                    # Should Add fail if file exists? Yes, likely intended for new files.
                    raise DiffError(f"Add File Error - file already exists: {path}")
                self.patch.actions[path] = self._parse_add_file()
                continue

            # If none of the above matched, it's an unknown line
            raise DiffError(f"Unknown line while parsing: {self._cur_line()}")

        # This check is removed as the while loop condition handles it.
        # The original code had a check here, but it seems redundant.
        # if not self.startswith("*** End Patch"):
        #     raise DiffError("Missing *** End Patch sentinel")
        # self.index += 1 # consume sentinel - This is handled by the loop exit condition

    # ------------- section parsers ---------------------------------------- #
    def _parse_update_file(self, text: str) -> PatchAction:
        action = PatchAction(type=ActionType.UPDATE)
        lines = text.split("\n")
        index = 0
        while not self.is_done(
            (
                "*** End Patch",
                "*** Update File:",
                "*** Delete File:",
                "*** Add File:",
            )
        ):
            def_str = self.read_str("@@ ")
            section_str = ""
            # Handle the rare case of exactly "@@" on a line
            if not def_str and self._norm(self._cur_line()) == "@@":
                section_str = self.read_line() # Consume the @@ line

            # Find the @@ context in the original file content
            if def_str.strip(): # Prefer matching the text after @@
                found = False
                # Search from current index onwards first
                if def_str not in lines[:index]: # Avoid matching previous sections
                    for i, s in enumerate(lines[index:], index):
                        if s == def_str:
                            index = i + 1 # Start search for context *after* this @@ line
                            found = True
                            break
                # Fuzzy match (strip whitespace) as fallback
                if not found and def_str.strip() not in [s.strip() for s in lines[:index]]:
                    for i, s in enumerate(lines[index:], index):
                        if s.strip() == def_str.strip():
                            index = i + 1
                            self.fuzz += 1
                            found = True
                            break
                # If still not found after search, it's an error
                # This logic assumes @@ must be found if specified.
                if not found:
                     raise DiffError(f"Context marker '@@ {def_str}' not found in original file starting from line {index}")


            # Now parse the actual chunk (+/- lines)
            next_ctx, chunks, end_idx, eof = peek_next_section(self.lines, self.index)

            # Find where this chunk's context applies in the original file
            new_index, fuzz = find_context(lines, next_ctx, index, eof)
            if new_index == -1:
                ctx_txt = "\\n".join(next_ctx)
                raise DiffError(
                    f"Invalid {'EOF ' if eof else ''}context at patch line {self.index} (orig file index {index}):\\nContext not found: {ctx_txt}"
                )
            self.fuzz += fuzz

            # Adjust chunk indices relative to the found context start
            for ch in chunks:
                ch.orig_index += new_index # The chunk's index is relative to the start of its context block
                action.chunks.append(ch)

            # Update main file index and patch parser index
            index = new_index + len(next_ctx) # Where the next search in the original file should start
            self.index = end_idx # Where the next parse in the patch file should start

        return action

    def _parse_add_file(self) -> PatchAction:
        lines: List[str] = []
        # Read until next file marker or end patch
        while not self.is_done(
            ("*** End Patch", "*** Update File:", "*** Delete File:", "*** Add File:")
        ):
            s = self.read_line()
            if not s.startswith("+"): # All lines in an add block must start with '+'
                raise DiffError(f"Invalid Add File line (missing '+'): {s}")
            lines.append(s[1:])  # strip leading '+'
        # Handle potential trailing newline (splitlines removes it, join adds it back consistently)
        return PatchAction(type=ActionType.ADD, new_file="\n".join(lines))


# --------------------------------------------------------------------------- #
#  Helper functions for Patch Parsing
# --------------------------------------------------------------------------- #
def find_context_core(
    lines: List[str], context: List[str], start: int
) -> Tuple[int, int]:
    """Core logic to find the context block, returns start index and fuzz level."""
    if not context: # If context is empty, match immediately at start
        return start, 0

    # Exact match first
    for i in range(start, len(lines) - len(context) + 1):
        if lines[i : i + len(context)] == context:
            return i, 0

    # Match ignoring trailing whitespace
    context_rstrip = [s.rstrip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
        lines_slice_rstrip = [s.rstrip() for s in lines[i : i + len(context)]]
        if lines_slice_rstrip == context_rstrip:
            return i, 1 # Low fuzz level

    # Match ignoring all leading/trailing whitespace
    context_strip = [s.strip() for s in context]
    for i in range(start, len(lines) - len(context) + 1):
         lines_slice_strip = [s.strip() for s in lines[i : i + len(context)]]
         if lines_slice_strip == context_strip:
            return i, 100 # High fuzz level

    return -1, 0 # Not found


def find_context(
    lines: List[str], context: List[str], start: int, eof: bool
) -> Tuple[int, int]:
    """Finds context, handling EOF specially."""
    if eof:
        # If it's the end of the file, try matching near the end first
        search_start_eof = max(start, len(lines) - len(context) - 5) # Search near end
        new_index, fuzz = find_context_core(lines, context, search_start_eof)
        if new_index != -1 and new_index + len(context) == len(lines): # Must match exactly at end
             return new_index, fuzz
        # If not found exactly at end, try searching from original start (high fuzz)
        new_index, fuzz = find_context_core(lines, context, start)
        # Penalize heavily if not at EOF when EOF marker was present
        return new_index, fuzz + 10_000 if new_index != -1 and new_index + len(context) != len(lines) else -1
    # Normal search from start
    return find_context_core(lines, context, start)


def peek_next_section(
    lines: List[str], index: int
) -> Tuple[List[str], List[Chunk], int, bool]:
    """Parses a chunk of context, adds, and deletes from the patch text."""
    context_lines: List[str] = [] # Renamed from 'old' for clarity
    del_lines: List[str] = []
    ins_lines: List[str] = []
    chunks: List[Chunk] = []
    mode = "keep" # Start by assuming context lines
    start_index_of_chunk_context = -1 # Track start line# of current chunk's context

    original_parser_index = index # Keep track of where we started in the patch lines

    while index < len(lines):
        s = lines[index]
        # Check for termination conditions
        if s.startswith(
            (
                "@@", # Start of a new context marker within the same file update
                "*** End Patch",
                "*** Update File:",
                "*** Delete File:",
                "*** Add File:",
                "*** End of File", # Specific marker for end of file context
            )
        ):
            break # Stop parsing this section

        # Basic validation
        if s == "***": # Should not appear within a chunk
            break
        if s.startswith("***"): # Only specific markers allowed unless it's EOF
             if s != "*** End of File":
                 raise DiffError(f"Invalid Line within chunk: {s}")

        current_line_index = index
        index += 1 # Consume the line

        # Determine line type and content
        line_content = s[1:] # Content without the prefix +/-/space
        prefix = s[0] if s else ' ' # Handle empty lines, treat as context

        # Validate prefix
        if prefix not in ['+', '-', ' ']:
             # Treat unexpected as context
             prefix = ' '
             line_content = s # Use the whole line as context

        new_mode = "keep"
        if prefix == '+': new_mode = "add"
        elif prefix == '-': new_mode = "delete"

        # --- Chunk Logic ---
        # If mode changes from add/delete back to keep, finalize the previous chunk
        if new_mode == "keep" and mode != "keep":
            if ins_lines or del_lines:
                if start_index_of_chunk_context == -1:
                     # This should ideally not happen if logic is correct, but safeguard
                     raise DiffError(f"Chunk ending at patch line {current_line_index} has no context start index.")
                chunks.append(
                    Chunk(
                        orig_index=start_index_of_chunk_context, # Index where deletions start
                        del_lines=list(del_lines), # Make copies
                        ins_lines=list(ins_lines),
                    )
                )
            del_lines.clear()
            ins_lines.clear()
            start_index_of_chunk_context = -1 # Reset for next potential chunk

        # Update state based on the new mode
        mode = new_mode
        if mode == "delete":
            if start_index_of_chunk_context == -1: # Start of a new change within the context
                 start_index_of_chunk_context = len(context_lines)
            del_lines.append(line_content)
            context_lines.append(line_content) # Deleted lines are part of the original context being matched
        elif mode == "add":
             if start_index_of_chunk_context == -1: # Start of a new change within the context
                 start_index_of_chunk_context = len(context_lines)
             ins_lines.append(line_content)
             # Added lines are NOT part of the original context_lines
        elif mode == "keep":
            context_lines.append(line_content) # Context lines add to the block to be matched

    # Finalize any pending chunk after loop finishes
    if ins_lines or del_lines:
        if start_index_of_chunk_context == -1:
             # If only additions/deletions exist with no preceding context lines
             start_index_of_chunk_context = 0
        chunks.append(
            Chunk(
                 orig_index=start_index_of_chunk_context,
                 del_lines=list(del_lines),
                 ins_lines=list(ins_lines),
            )
        )

    # Check if the loop terminated because of "*** End of File"
    is_eof = False
    if index < len(lines) and lines[index] == "*** End of File":
        index += 1 # Consume the EOF marker
        is_eof = True

    if index == original_parser_index and not is_eof: # Check if we actually consumed any lines
         # Only raise if it's not just an EOF marker situation and not start of next section
         if not (index < len(lines) and lines[index].startswith(("@@", "***"))):
              raise DiffError(f"Empty or invalid chunk section starting at patch line {original_parser_index}")

    # Return the collected context lines for matching, the chunks of changes, the new parser index, and EOF flag
    return context_lines, chunks, index, is_eof


# --------------------------------------------------------------------------- #
#  Patch → Commit and Commit application
# --------------------------------------------------------------------------- #
def _get_updated_file(text: str, action: PatchAction, path: str) -> str:
    """Applies the chunks from a PatchAction to the original file text."""
    if action.type is not ActionType.UPDATE:
        raise DiffError("_get_updated_file called with non-update action")

    orig_lines = text.split("\n")
    dest_lines: List[str] = []
    orig_file_index = 0 # Tracks position in the original file lines

    # Sort chunks by original index to ensure correct application order
    sorted_chunks = sorted(action.chunks, key=lambda c: c.orig_index)

    for chunk in sorted_chunks:
        # Check if chunk index is valid
        if chunk.orig_index < 0 or chunk.orig_index > len(orig_lines):
            # Allow index == len(orig_lines) only if deleting 0 lines (pure insertion at end)
            if not (chunk.orig_index == len(orig_lines) and not chunk.del_lines):
                raise DiffError(
                    f"{path}: chunk.orig_index {chunk.orig_index} is out of bounds for file length {len(orig_lines)}"
                )

        # Check for overlapping chunks (simple check based on index progression)
        if orig_file_index > chunk.orig_index:
            raise DiffError(
                f"{path}: overlapping or out-of-order chunks detected at original index {chunk.orig_index} (previous index was {orig_file_index})"
            )

        # Add lines from original file before the chunk starts
        dest_lines.extend(orig_lines[orig_file_index : chunk.orig_index])

        # Apply the chunk: skip deleted lines, add inserted lines
        dest_lines.extend(chunk.ins_lines)

        # Advance the original file index past the deleted lines
        num_deleted = len(chunk.del_lines)
        expected_end_index = chunk.orig_index + num_deleted

        # --- Verification: Ensure deleted lines actually match original content ---
        if expected_end_index > len(orig_lines):
             raise DiffError(
                 f"{path}: Deletion range [{chunk.orig_index}:{expected_end_index}] exceeds original file length {len(orig_lines)}."
             )

        original_deleted_section = orig_lines[chunk.orig_index : expected_end_index]
        if original_deleted_section != chunk.del_lines:
             # Attempt fuzzy match (strip whitespace)
             if [l.strip() for l in original_deleted_section] != [dl.strip() for dl in chunk.del_lines]:
                  orig_del_preview = "\\n".join(original_deleted_section[:3]) + ('...' if len(original_deleted_section)>3 else '')
                  chunk_del_preview = "\\n".join(chunk.del_lines[:3]) + ('...' if len(chunk.del_lines)>3 else '')
                  raise DiffError(
                      f"{path}: Mismatch applying chunk at original index {chunk.orig_index}. "
                      f"Expected deletions do not match file content.\n"
                      f"Expected ({len(chunk.del_lines)} lines):\n{chunk_del_preview}\nGot ({len(original_deleted_section)} lines):\n{orig_del_preview}"
                  )
             else:
                  # Log fuzziness if desired, but proceed if stripped content matches
                  pass # Consider adding logging here if fuzziness occurs

        orig_file_index = expected_end_index # Update index past the verified deleted section


    # Add any remaining lines from the original file after the last chunk
    dest_lines.extend(orig_lines[orig_file_index:])

    # Join lines back, ensuring consistent newline handling
    # Note: split() removes trailing newline, join() adds one between lines but not at end.
    # If original text ended with newline, add it back.
    final_content = "\n".join(dest_lines)
    if text.endswith('\n') and not final_content.endswith('\n') and final_content != "":
        final_content += '\n'
    # Handle case where original file was empty and content is added
    elif not text and final_content and not final_content.endswith('\n'):
         # If adding content to an empty file, decide if trailing newline is desired.
         # Let's assume yes for consistency with text files.
         final_content += '\n'


    return final_content


def patch_to_commit(patch: Patch, orig: Dict[str, str]) -> Commit:
    """Converts a parsed Patch object into a Commit object with final changes."""
    commit = Commit()
    for path, action in patch.actions.items():
        if action.type is ActionType.DELETE:
            commit.changes[path] = FileChange(
                type=ActionType.DELETE, old_content=orig.get(path) # Use .get for safety
            )
        elif action.type is ActionType.ADD:
            if action.new_file is None:
                raise DiffError(f"ADD action for {path} has no content")
            commit.changes[path] = FileChange(
                type=ActionType.ADD, new_content=action.new_file
            )
        elif action.type is ActionType.UPDATE:
            if path not in orig:
                 raise DiffError(f"Cannot UPDATE non-existent file: {path}") # Ensure orig exists for update
            new_content = _get_updated_file(orig[path], action, path)
            commit.changes[path] = FileChange(
                type=ActionType.UPDATE,
                old_content=orig[path],
                new_content=new_content,
                move_path=action.move_path, # Propagate move path
            )
    return commit


# --------------------------------------------------------------------------- #
#  User-facing helper functions (intended to be called from outside)
# --------------------------------------------------------------------------- #
def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    """Parses V4A diff text into a Patch object."""
    lines = text.splitlines()  # preserves blank lines, no strip()
    if not lines:
         raise DiffError("Empty patch text provided")

    start_index = -1
    end_index = -1

    for i, line in enumerate(lines):
        norm_line = Parser._norm(line)
        if norm_line.startswith("*** Begin Patch"):
            start_index = i + 1 # Start parsing after the Begin line
            break # Found start

    if start_index == -1:
         # Allow parsing even without Begin sentinel for flexibility?
         # For now, strict requirement.
         raise DiffError("Invalid patch text - missing *** Begin Patch sentinel")

    # Search for End Patch from the end backwards
    for i in range(len(lines) - 1, start_index - 2, -1):
         norm_line = Parser._norm(lines[i])
         if norm_line == "*** End Patch":
              end_index = i # End parsing before the End line
              break # Found end

    if end_index == -1:
         # Allow parsing without End sentinel?
         # For now, strict requirement.
         raise DiffError("Invalid patch text - missing *** End Patch sentinel")

    if start_index > end_index:
         raise DiffError("*** Begin Patch found after *** End Patch")

    # Parse only the lines between the sentinels
    parser = Parser(current_files=orig, lines=lines[start_index:end_index], index=0)
    parser.parse()
    return parser.patch, parser.fuzz


def identify_files_needed(text: str) -> List[str]:
    """Identifies files mentioned for Update or Delete actions in the patch text."""
    lines = text.splitlines()
    needed = set() # Use a set to avoid duplicates
    in_patch_section = False # Track if we are between Begin and End

    for line in lines:
         norm_line = Parser._norm(line)
         if norm_line.startswith("*** Begin Patch"):
             in_patch_section = True
             continue
         if norm_line == "*** End Patch":
             in_patch_section = False
             break # Stop processing after End Patch

         if not in_patch_section:
             continue # Ignore lines outside the patch block

         if norm_line.startswith("*** Update File: "):
              path = norm_line[len("*** Update File: "):].strip()
              if path: needed.add(path)
         elif norm_line.startswith("*** Delete File: "):
              path = norm_line[len("*** Delete File: "):].strip()
              if path: needed.add(path)
         # Ignore Add File, as they shouldn't exist beforehand
    return sorted(list(needed))


def identify_files_added(text: str) -> List[str]:
    """Identifies files mentioned for Add actions in the patch text."""
    lines = text.splitlines()
    added = set()
    in_patch_section = False

    for line in lines:
        norm_line = Parser._norm(line)
        if norm_line.startswith("*** Begin Patch"):
            in_patch_section = True
            continue
        if norm_line == "*** End Patch":
            in_patch_section = False
            break

        if not in_patch_section:
            continue

        if norm_line.startswith("*** Add File: "):
             path = norm_line[len("*** Add File: "):].strip()
             if path: added.add(path)
    return sorted(list(added))


# --------------------------------------------------------------------------- #
#  File-system interaction wrapper (to be used by Executor)
# --------------------------------------------------------------------------- #
def apply_commit(
    commit: Commit,
    write_fn: Callable[[str, str], bool], # Modified to return success bool
    remove_fn: Callable[[str], bool],     # Modified to return success bool
    # exists_fn: Callable[[str], bool] # Optional: Add exists check if needed
) -> Dict[str, str]:
    """
    Applies a Commit object using provided file operation functions.
    Returns a dictionary mapping file paths to status messages ("Added", "Updated", "Deleted", "Moved", "Error: ...").
    """
    results = {}
    target_paths_written = set() # Track targets to avoid conflicts
    moved_sources = set() # Track sources that have been moved

    # Process deletes first to avoid conflicts with moves/adds to the same path
    for path, change in list(commit.changes.items()): # Iterate over a copy
        if change.type is ActionType.DELETE:
            try:
                if remove_fn(path):
                     results[path] = "Deleted"
                     moved_sources.add(path) # Mark as handled (deleted)
                else:
                     # Check if it failed because it didn't exist (which is ok for delete)
                     # This requires an exists_fn or similar logic in remove_fn
                     # Assuming remove_fn returns False on error, True on success or missing_ok
                     results[path] = "Deleted (or already missing)" # Adjust based on remove_fn behavior
                     moved_sources.add(path)
            except Exception as e:
                 results[path] = f"Error: Unexpected exception during delete - {e}"
            # Remove from original dict so it's not processed again
            del commit.changes[path]


    # Process updates and moves
    for path, change in list(commit.changes.items()): # Iterate over a copy
        if change.type is ActionType.UPDATE:
            try:
                if change.new_content is None:
                    results[path] = "Error: UPDATE change has no new content"
                    continue

                target = change.move_path or path

                # Prevent overwriting a file added/updated in the same commit
                if target != path and target in target_paths_written:
                     results[path] = f"Error: Cannot move/update to '{target}', it was modified in the same patch."
                     continue
                # Prevent updating a file that was deleted in the same commit
                if path in moved_sources: # Check if original path was deleted
                     results[path] = f"Error: Cannot update '{path}', it was deleted in the same patch."
                     continue


                # Write the new content to the target path
                if write_fn(target, change.new_content):
                    target_paths_written.add(target)
                    if change.move_path:
                        # If move, remove the original after successful write
                        if path not in moved_sources: # Don't try to remove if already deleted
                            if remove_fn(path):
                                results[path] = f"Moved to {target}"
                                moved_sources.add(path) # Mark original as handled
                            else:
                                # Failed to remove original - problematic state!
                                results[path] = f"Error: Updated at {target}, but failed to remove original {path}"
                        else:
                             results[path] = f"Moved to {target} (original already handled)"
                    else:
                        results[path] = "Updated"
                else:
                     results[path] = f"Error: Failed to write update to {target}"

            except Exception as e:
                 results[path] = f"Error: Unexpected exception during update/move - {e}"
            # Remove from original dict
            if path in commit.changes: del commit.changes[path]


    # Process adds last
    for path, change in commit.changes.items(): # Process remaining (should only be adds)
        if change.type is ActionType.ADD:
            try:
                if change.new_content is None:
                    results[path] = "Error: ADD change has no content"
                    continue
                # Prevent adding a file if the target path was already written/moved to
                if path in target_paths_written:
                    results[path] = f"Error: Cannot add '{path}', path was already written to in the same patch."
                    continue
                # Prevent adding if the path was a source of a move/delete
                if path in moved_sources:
                     results[path] = f"Error: Cannot add '{path}', path was deleted or moved from in the same patch."
                     continue

                # Optional: Check if file already exists?
                # if exists_fn(path):
                #     results[path] = "Error: File to add already exists"
                #     continue

                if write_fn(path, change.new_content):
                     results[path] = "Added"
                     target_paths_written.add(path) # Track added path
                else:
                     results[path] = "Error: Failed to write new file"

            except Exception as e:
                 results[path] = f"Error: Unexpected exception during add - {e}"
        else:
             # Should not happen if logic above is correct
             results[path] = f"Error: Unhandled change type '{change.type}'"


    return results

# Note: Removed main_cli() and if __name__ == "__main__": block
