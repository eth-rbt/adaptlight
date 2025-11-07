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

    def __init__(self, name: str, description: str = '', on_enter=None):
        """
        Initialize a state.

        Args:
            name: Unique identifier for this state
            description: Human-readable description for AI parsing
            on_enter: Callable to execute when entering this state
        """
        self.name = name
        self.description = description
        self.on_enter = on_enter

    def enter(self, params=None):
        """
        Execute the onEnter function for this state.

        Args:
            params: Optional parameters to pass to the onEnter function
        """
        if self.on_enter and callable(self.on_enter):
            print(f"Entering state: {self.name}" +
                  (f" with params: {params}" if params else ""))

            if params:
                self.on_enter(params)
            else:
                self.on_enter()


class States:
    """Manages a collection of states."""

    def __init__(self):
        """Initialize empty state collection."""
        self.states = []

    def add_state(self, state: State):
        """Add a state to the collection."""
        if isinstance(state, State):
            self.states.append(state)
            print(f"State added to collection: {state.name}")
        else:
            raise TypeError("Can only add State objects")

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

    def clear_states(self):
        """Clear all states."""
        self.states = []
        print("All states cleared")

    def get_states_for_prompt(self):
        """
        Get formatted state information for OpenAI API calls.

        Returns:
            Formatted string with state names and descriptions
        """
        if not self.states:
            return "No states registered."

        return '\n'.join(f"- {s.name}: {s.description}" for s in self.states)
