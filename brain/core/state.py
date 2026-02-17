"""
State class definitions for AdaptLight state machine.

This module contains:
- State: Represents a single state with name, description, and parameters
- States: Collection manager for all available states

States have behavior parameters that define what happens when entering that state.
The actual execution of state behavior is handled by the app (not the brain).
"""


class State:
    """Represents a single state in the state machine."""

    def __init__(self, name: str, r=None, g=None, b=None, speed=None,
                 code=None, description: str = '', voice_reactive=None, vision_reactive=None):
        """
        Initialize a state with unified parameters.

        Args:
            name: Unique identifier for this state
            r: Red value (0-255) or expression string (for original mode)
            g: Green value (0-255) or expression string (for original mode)
            b: Blue value (0-255) or expression string (for original mode)
            speed: Animation speed in milliseconds (None for static states, for original mode)
            code: Python code defining render(prev, t) function (for pure_python/stdlib modes)
                  The function should return ((r, g, b), next_ms) where:
                  - next_ms > 0: call again in next_ms milliseconds
                  - next_ms = None: static, no more updates
                  - next_ms = 0: state complete, triggers state_complete transition
            description: Human-readable description for AI parsing
            voice_reactive: Optional dict to enable mic-reactive brightness. Example:
                           {"enabled": true, "color": [0,255,0], "smoothing_alpha": 0.6,
                            "min_amplitude": 100, "max_amplitude": 5000}
                        vision_reactive: Optional dict to enable camera/VLM-reactive behavior.
                                                        Example:
                                                        {
                                                            "enabled": true,
                                                            "prompt": "Detect hand wave. Reply JSON only.",
                                                            "model": "gpt-4o-mini",
                                                            "interval_ms": 700,
                                                            "event": "vision_hand_wave"
                                                        }
        """
        self.name = name
        self.r = r
        self.g = g
        self.b = b
        self.speed = speed
        self.code = code
        self.voice_reactive = voice_reactive or {}
        self.vision_reactive = vision_reactive or {}
        self.description = description or self._generate_description()

        # Callback for state entry - set by the app
        self._on_enter_callback = None

    def _generate_description(self):
        """Generate a default description based on state parameters."""
        base = ""
        if self.code is not None:
            base = f"Code-based state with render function"
        elif self.speed is not None:
            base = f"Animation state with r={self.r}, g={self.g}, b={self.b}, speed={self.speed}ms"
        else:
            base = f"Static color state with r={self.r}, g={self.g}, b={self.b}"

        # Add voice-reactive hint for the AI
        if self.voice_reactive.get('enabled'):
            vr = self.voice_reactive
            color = vr.get('color')
            smoothing = vr.get('smoothing_alpha')
            base += " | voice-reactive brightness enabled"
            if color:
                base += f" (base color {color})"
            if smoothing is not None:
                base += f", smoothing_alpha={smoothing}"

        # Add vision-reactive hint for the AI
        if self.vision_reactive.get('enabled'):
            vis = self.vision_reactive
            prompt = vis.get('prompt')
            interval_ms = vis.get('interval_ms')
            event = vis.get('event')
            base += " | vision-reactive enabled"
            if interval_ms is not None:
                base += f", interval_ms={interval_ms}"
            if event:
                base += f", event={event}"
            if prompt:
                prompt_preview = str(prompt).strip().replace('\n', ' ')
                if len(prompt_preview) > 80:
                    prompt_preview = prompt_preview[:77] + "..."
                base += f", prompt='{prompt_preview}'"

        return base

    def get_params(self):
        """Get state parameters as a dictionary."""
        return {
            'r': self.r,
            'g': self.g,
            'b': self.b,
            'speed': self.speed,
            'code': self.code,
            'voice_reactive': self.voice_reactive,
            'vision_reactive': self.vision_reactive,
            'state_name': self.name
        }

    def enter(self, params=None):
        """
        Execute state behavior when entering this state.

        The actual execution is delegated to the app via callback.
        If no callback is set, this is a no-op (useful for testing).

        Args:
            params: Optional parameters to override state defaults
        """
        # Use provided params or fall back to state defaults
        if params is None:
            params = self.get_params()

        print(f"Entering state: {self.name}" +
              (f" with params: {params}" if params else ""))

        # Call the callback if set (app-specific behavior)
        if self._on_enter_callback:
            self._on_enter_callback(params)

    def set_on_enter_callback(self, callback):
        """
        Set the callback for state entry.

        This should be set by the app to handle hardware-specific behavior.

        Args:
            callback: Function that takes state params dict
        """
        self._on_enter_callback = callback


class States:
    """Manages a collection of states."""

    def __init__(self):
        """Initialize empty state collection."""
        self.states = []
        self._on_enter_callback = None

    def set_on_enter_callback(self, callback):
        """
        Set the callback for state entry on all states.

        Args:
            callback: Function that takes state params dict
        """
        self._on_enter_callback = callback
        # Apply to existing states
        for state in self.states:
            state.set_on_enter_callback(callback)

    def add_state(self, state: State):
        """
        Add a state to the collection.

        If a state with the same name already exists, it will be replaced/overwritten.
        """
        if not isinstance(state, State):
            raise TypeError("Can only add State objects")

        # Apply callback if set
        if self._on_enter_callback:
            state.set_on_enter_callback(self._on_enter_callback)

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
            if s.code is not None:
                params = "code=<render function>"
            else:
                params = f"r={s.r}, g={s.g}, b={s.b}, speed={s.speed}"
            if s.voice_reactive.get('enabled'):
                vr = s.voice_reactive
                params += f", voice_reactive={{enabled: True"
                if vr.get('color') is not None:
                    params += f", color: {vr.get('color')}"
                if vr.get('smoothing_alpha') is not None:
                    params += f", smoothing_alpha: {vr.get('smoothing_alpha')}"
                if vr.get('min_amplitude') is not None:
                    params += f", min_amplitude: {vr.get('min_amplitude')}"
                if vr.get('max_amplitude') is not None:
                    params += f", max_amplitude: {vr.get('max_amplitude')}"
                params += "}"

            if s.vision_reactive.get('enabled'):
                vis = s.vision_reactive
                params += ", vision_reactive={enabled: True"
                if vis.get('model') is not None:
                    params += f", model: {vis.get('model')}"
                if vis.get('interval_ms') is not None:
                    params += f", interval_ms: {vis.get('interval_ms')}"
                if vis.get('event') is not None:
                    params += f", event: {vis.get('event')}"
                if vis.get('prompt') is not None:
                    prompt = str(vis.get('prompt')).strip().replace('\n', ' ')
                    if len(prompt) > 60:
                        prompt = prompt[:57] + "..."
                    params += f", prompt: {prompt}"
                params += "}"
            desc = s.description if s.description else "No description"
            lines.append(f"- {s.name}: {params} | {desc}")

        return '\n'.join(lines)
