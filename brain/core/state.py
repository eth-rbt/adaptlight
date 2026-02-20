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
                 code=None, description: str = '', audio_reactive=None, volume_reactive=None,
                 vision_reactive=None, api_reactive=None):
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
            audio_reactive: Optional dict to enable mic-audio LLM watcher behavior.
                           Example:
                           {"enabled": true, "prompt": "Detect clapping", "model": "gpt-4o-mini",
                            "interval_ms": 3000, "event": "audio_clap_detected"}
            volume_reactive: Optional dict to enable mic-volume watcher behavior.
                           Example:
                           {"enabled": true, "interval_ms": 100, "smoothing_alpha": 0.35}
            vision_reactive: Optional dict to enable camera/VLM-reactive behavior.
                            Example:
                            {
                                "enabled": true,
                                "prompt": "Detect hand wave. Reply JSON only.",
                                "model": "gpt-4o-mini",
                                "interval_ms": 700,
                                "event": "vision_hand_wave"
                            }
            api_reactive: Optional dict to enable API-reactive behavior. Example:
                         {
                             "enabled": true,
                             "api": "weather",           # Preset API name
                             "url": "https://...",       # OR custom URL (overrides api)
                             "method": "GET",            # HTTP method for custom URL
                             "headers": {},              # Custom headers
                             "params": {"location": "SF"},
                             "interval_ms": 60000,
                             "key": "weather",           # Writes to state_data[key]
                             "event": "weather_updated"  # Optional event for rules
                         }
        """
        self.name = name
        self.r = r
        self.g = g
        self.b = b
        self.speed = speed
        self.code = code
        self.audio_reactive = audio_reactive or {}
        self.volume_reactive = volume_reactive or {}
        self.vision_reactive = vision_reactive or {}
        self.api_reactive = api_reactive or {}
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

        # Add audio-reactive hint for the AI
        if self.audio_reactive.get('enabled'):
            audio = self.audio_reactive
            prompt = audio.get('prompt')
            interval_ms = audio.get('interval_ms')
            event = audio.get('event')
            base += " | audio-reactive enabled"
            if interval_ms is not None:
                base += f", interval_ms={interval_ms}"
            if event:
                base += f", event={event}"
            if prompt:
                prompt_preview = str(prompt).strip().replace('\n', ' ')
                if len(prompt_preview) > 80:
                    prompt_preview = prompt_preview[:77] + "..."
                base += f", prompt='{prompt_preview}'"

        # Add volume-reactive hint for the AI
        if self.volume_reactive.get('enabled'):
            volume = self.volume_reactive
            interval_ms = volume.get('interval_ms')
            smoothing = volume.get('smoothing_alpha')
            base += " | volume-reactive enabled"
            if interval_ms is not None:
                base += f", interval_ms={interval_ms}"
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

        # Add api-reactive hint for the AI
        if self.api_reactive.get('enabled'):
            api = self.api_reactive
            api_name = api.get('api')
            url = api.get('url')
            interval_ms = api.get('interval_ms')
            key = api.get('key')
            event = api.get('event')
            base += " | api-reactive enabled"
            if api_name:
                base += f", api={api_name}"
            if url:
                base += f", url={url[:50]}..." if len(url) > 50 else f", url={url}"
            if interval_ms is not None:
                base += f", interval_ms={interval_ms}"
            if key:
                base += f", key={key}"
            if event:
                base += f", event={event}"

        return base

    def get_params(self):
        """Get state parameters as a dictionary."""
        return {
            'r': self.r,
            'g': self.g,
            'b': self.b,
            'speed': self.speed,
            'code': self.code,
            'audio_reactive': self.audio_reactive,
            'volume_reactive': self.volume_reactive,
            'vision_reactive': self.vision_reactive,
            'api_reactive': self.api_reactive,
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
            if s.audio_reactive.get('enabled'):
                audio = s.audio_reactive
                params += ", audio_reactive={enabled: True"
                if audio.get('model') is not None:
                    params += f", model: {audio.get('model')}"
                if audio.get('interval_ms') is not None:
                    params += f", interval_ms: {audio.get('interval_ms')}"
                if audio.get('event') is not None:
                    params += f", event: {audio.get('event')}"
                if audio.get('prompt') is not None:
                    prompt = str(audio.get('prompt')).strip().replace('\n', ' ')
                    if len(prompt) > 60:
                        prompt = prompt[:57] + "..."
                    params += f", prompt: {prompt}"
                params += "}"

            if s.volume_reactive.get('enabled'):
                volume = s.volume_reactive
                params += ", volume_reactive={enabled: True"
                if volume.get('interval_ms') is not None:
                    params += f", interval_ms: {volume.get('interval_ms')}"
                if volume.get('smoothing_alpha') is not None:
                    params += f", smoothing_alpha: {volume.get('smoothing_alpha')}"
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

            if s.api_reactive.get('enabled'):
                api = s.api_reactive
                params += ", api_reactive={enabled: True"
                if api.get('api') is not None:
                    params += f", api: {api.get('api')}"
                if api.get('url') is not None:
                    url = api.get('url')
                    params += f", url: {url[:40]}..." if len(url) > 40 else f", url: {url}"
                if api.get('interval_ms') is not None:
                    params += f", interval_ms: {api.get('interval_ms')}"
                if api.get('key') is not None:
                    params += f", key: {api.get('key')}"
                if api.get('event') is not None:
                    params += f", event: {api.get('event')}"
                params += "}"

            desc = s.description if s.description else "No description"
            lines.append(f"- {s.name}: {params} | {desc}")

        return '\n'.join(lines)
