"""
State class definitions for AdaptLight state machine.

This module is a port of states.js and contains:
- State: Represents a single state with name, description, and onEnter behavior
- States: Collection manager for all available states

States have behavior functions that execute when entering that state.
For example: 'on' state turns LEDs on, 'color' state sets RGB values.
"""


class State:
    """Represents a single state in the state machine."""

    def __init__(self, name: str, r=None, g=None, b=None, speed=None, description: str = ''):
        """
        Initialize a state with unified parameters.

        Args:
            name: Unique identifier for this state
            r: Red value (0-255) or expression string
            g: Green value (0-255) or expression string
            b: Blue value (0-255) or expression string
            speed: Animation speed in milliseconds (None for static states)
            description: Human-readable description for AI parsing
        """
        self.name = name
        self.r = r
        self.g = g
        self.b = b
        self.speed = speed
        self.description = description or self._generate_description()

    def _generate_description(self):
        """Generate a default description based on state parameters."""
        if self.speed is not None:
            return f"Animation state with r={self.r}, g={self.g}, b={self.b}, speed={self.speed}ms"
        else:
            return f"Static color state with r={self.r}, g={self.g}, b={self.b}"

    def enter(self, params=None):
        """
        Execute state behavior when entering this state.

        Args:
            params: Optional parameters to override state defaults
        """
        # Import here to avoid circular dependency
        from states.light_states import execute_unified_state

        # Use provided params or fall back to state defaults
        if params is None:
            params = {
                'r': self.r,
                'g': self.g,
                'b': self.b,
                'speed': self.speed
            }

        print(f"Entering state: {self.name}" +
              (f" with params: {params}" if params else ""))

        execute_unified_state(params)


class States:
    """Manages a collection of states."""

    def __init__(self):
        """Initialize empty state collection."""
        self.states = []

    def add_state(self, state: State):
        """
        Add a state to the collection.

        If a state with the same name already exists, it will be replaced/overwritten.
        """
        if not isinstance(state, State):
            raise TypeError("Can only add State objects")

        # Check if state with this name already exists
        for i, existing_state in enumerate(self.states):
            if existing_state.name == state.name:
                # Replace/overwrite the existing state
                self.states[i] = state
                print(f"State replaced: {state.name}")
                return

        # State doesn't exist, add it
        self.states.append(state)
        print(f"State added to collection: {state.name}")

    def get_states(self):
        """Get all states as a list."""
        return self.states

    def get_state_list(self):
        """Get list of state names and descriptions."""
        return [{'name': s.name, 'description': s.description}
                for s in self.states]

    def get_state_by_name(self, name: str):
        """Get a state by its name."""
        for state in self.states:
            if state.name == name:
                return state
        return None

    def delete_state(self, name: str) -> bool:
        """
        Delete a state by its name.

        Args:
            name: Name of the state to delete

        Returns:
            True if state was deleted, False if not found
        """
        for i, state in enumerate(self.states):
            if state.name == name:
                deleted = self.states.pop(i)
                print(f"State deleted: {deleted.name}")
                return True
        print(f"State not found: {name}")
        return False

    def clear_states(self):
        """Clear all states."""
        self.states = []
        print("All states cleared")

    def get_states_for_prompt(self):
        """
        Get formatted state information for OpenAI API calls.

        Returns:
            Formatted string with state names, parameters, and descriptions
        """
        if not self.states:
            return "No states registered."

        lines = []
        for s in self.states:
            params = f"r={s.r}, g={s.g}, b={s.b}, speed={s.speed}"
            desc = s.description if s.description else "No description"
            lines.append(f"- {s.name}: {params} | {desc}")

        return '\n'.join(lines)
