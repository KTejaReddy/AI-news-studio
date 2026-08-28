"""TimelineHistory for managing undo/redo stack state snapshots.
"""

from typing import Any, Dict, List, Optional
import copy


class TimelineHistory:
    """Manages project history stacks enabling structural undo and redo operations."""

    def __init__(self, max_depth: int = 50) -> None:
        """Initialize TimelineHistory.

        Args:
            max_depth: Maximum undo states allowed in stack to cap memory.
        """
        self.max_depth = max_depth
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []

    def push_state(self, state_dict: Dict[str, Any]) -> None:
        """Push a snapshot of the current timeline state to history.

        Args:
            state_dict: Serialized JSON dictionary of current tracks and clips.
        """
        # Deep copy to isolate state modification leaks
        snapshot = copy.deepcopy(state_dict)
        self.undo_stack.append(snapshot)
        
        # Limit stack depth
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)

        # Clear redo stack on new action
        self.redo_stack.clear()

    def undo(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Pop the last historical state and store the current state in the redo stack.

        Args:
            current_state: Serialized dictionary of the active state.

        Returns:
            The previous state dictionary or None if undo stack is empty.
        """
        if not self.undo_stack:
            return None

        # Push current to redo
        self.redo_stack.append(copy.deepcopy(current_state))
        if len(self.redo_stack) > self.max_depth:
            self.redo_stack.pop(0)

        # Pop from undo
        previous_state = self.undo_stack.pop()
        return previous_state

    def redo(self, current_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Retrieve the next state from the redo stack and push the current state to the undo stack.

        Args:
            current_state: Serialized dictionary of the active state.

        Returns:
            The redone state dictionary or None if redo stack is empty.
        """
        if not self.redo_stack:
            return None

        # Push current to undo
        self.undo_stack.append(copy.deepcopy(current_state))
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)

        # Pop from redo
        next_state = self.redo_stack.pop()
        return next_state

    def clear(self) -> None:
        """Reset the history stacks."""
        self.undo_stack.clear()
        self.redo_stack.clear()
