"""
State machine implementation for AdaptLight.

This module is a port of statemachine.js and contains:
- StateMachine: Main state machine class that manages rules, states, and transitions

The state machine:
1. Stores rules (state transitions with conditions)
2. Executes transitions based on events
3. Manages state data and intervals
4. Evaluates conditions and actions safely
5. Manages state rendering via StateExecutor
"""

import threading
from typing import Any, Callable, Optional, List
from .state import State, States
from .rule import Rule
from .state_executor import StateExecutor


class StateMachine:
    """Main state machine for managing light behavior."""

    def __init__(self, debug=False, default_rules=True, representation_version="stdlib"):
        """Initialize the state machine.

        Args:
            debug: Enable debug output (FPS timing)
            default_rules: If True, add default on/off toggle rules
            representation_version: State representation version ("original", "pure_python", "stdlib")
        """
        self.rules: List[Rule] = []
        self.current_state = 'off'
        self.current_state_params = None
        self.states = States()
        self.state_data = {}
        self.interval = None
        self.interval_callback = None
        self.active_timers = {}  # {rule_id: Timer object} for time-based rules
        self.rule_id_counter = 0  # Unique ID for each rule
        self.pipeline_executor = None  # Set by tool_registry to enable pipeline execution
        self.debug = debug  # Enable debug output (FPS timing)

        # State rendering
        self.representation_version = representation_version
        self.state_executor = StateExecutor(representation_version)
        self.state_executor.set_on_state_complete(self._on_state_complete)
        # Wire up getData/setData so render code can access shared state_data
        self.state_executor.set_data_accessors(
            get_fn=lambda key, default=None: self.state_data.get(key, default),
            set_fn=self._set_data_from_renderer
        )
        self.render_timer = None  # Timer for next render call
        self._on_render_callback = None  # Callback for RGB updates

    def _set_data_from_renderer(self, key, value):
        """Set data from renderer code - returns value for chaining."""
        self.state_data[key] = value
        return value

        # Add default rules
        if default_rules:
            self._setup_default_rules()

    def _setup_default_rules(self):
        """Set up default state transition rules."""
        # Create default 'on' state (white light)
        on_state = State('on', r=255, g=255, b=255, description='Light on (white)')
        self.states.add_state(on_state)

        # Default on/off toggle rule
        self.add_rule({
            'state1': 'off',
            'transition': 'button_click',
            'state2': 'on'
        })
        self.add_rule({
            'state1': 'on',
            'transition': 'button_click',
            'state2': 'off'
        })
        print("Default rules loaded: button_click toggles on/off")

    def register_state(self, name: str, description: str = '', on_enter: Callable = None):
        """
        Register a state with its description and onEnter function.

        Args:
            name: The name of the state
            description: Description of what this state does
            on_enter: Function to execute when entering this state

        Returns:
            The created State object
        """
        state = State(name, description, on_enter)
        self.states.add_state(state)
        print(f"State registered: {name}")
        return state

    def get_state_object(self, name: str) -> Optional[State]:
        """Get a state by name."""
        return self.states.get_state_by_name(name)

    def get_state_list(self):
        """Get a list of all state names and descriptions."""
        return self.states.get_state_list()

    def add_rule(self, rule):
        """
        Add a new rule to the state machine.

        If a rule with the same state1, transition, and condition exists,
        it will be replaced.

        Args:
            rule: Can be a Rule instance, dict, or legacy [state1, action, state2] array
                  Dict format supports: state1, transition, state2, condition, action,
                  trigger_config, priority, enabled
                  Also supports 'from'/'on'/'to' aliases for state1/transition/state2
        """
        # Convert to Rule object if needed
        if isinstance(rule, Rule):
            rule_obj = rule
        elif isinstance(rule, dict):
            # Support both old format (state1/transition/state2) and new format (from/on/to)
            state1 = rule.get('state1') or rule.get('from')
            transition = rule.get('transition') or rule.get('on')
            state2 = rule.get('state2') or rule.get('to')

            rule_obj = Rule(
                state1,
                transition,
                state2,
                rule.get('condition'),
                rule.get('action'),
                rule.get('trigger_config'),
                rule.get('priority', 0),
                rule.get('enabled', True),
                rule.get('pipeline')
            )
        elif isinstance(rule, list) and len(rule) == 3:
            # Legacy format: [state1, action, state2]
            rule_obj = Rule(rule[0], rule[1], rule[2], None, None, None)
        else:
            raise ValueError("Invalid rule format")

        # Assign unique ID
        rule_obj.id = self.rule_id_counter
        self.rule_id_counter += 1

        # Check if rule already exists
        existing_index = None
        for i, r in enumerate(self.rules):
            if (r.state1 == rule_obj.state1 and
                r.transition == rule_obj.transition and
                r.condition == rule_obj.condition):
                existing_index = i
                break

        if existing_index is not None:
            # Cancel timer for old rule if it exists
            old_rule = self.rules[existing_index]
            self._cancel_timer(old_rule.id)

            self.rules[existing_index] = rule_obj
            print(f"Rule replaced: {rule_obj}")
        else:
            self.rules.append(rule_obj)
            print(f"Rule added: {rule_obj}")

        # Schedule timer if this is a time-based rule
        if rule_obj.transition in ['timer', 'interval', 'schedule']:
            self._schedule_rule(rule_obj)

    def get_rules(self) -> List[Rule]:
        """Get all rules."""
        return self.rules

    def clear_rules(self):
        """Clear all rules and cancel all timers."""
        # Cancel all active timers
        for rule_id, timer in list(self.active_timers.items()):
            timer.cancel()
        self.active_timers = {}

        self.rules = []
        print("All rules cleared and timers cancelled")

    def remove_rule(self, index: int):
        """Remove a specific rule by index."""
        if 0 <= index < len(self.rules):
            removed = self.rules.pop(index)
            # Cancel any active timer for this rule
            if hasattr(removed, 'id'):
                self._cancel_timer(removed.id)
            print(f"Rule removed: {removed}")

    def _cancel_timer(self, rule_id: int):
        """Cancel an active timer for a rule."""
        if rule_id in self.active_timers:
            self.active_timers[rule_id].cancel()
            del self.active_timers[rule_id]
            print(f"Timer cancelled for rule {rule_id}")

    def _schedule_rule(self, rule: Rule):
        """Schedule a time-based rule (timer, interval, or schedule)."""
        import threading

        if rule.transition == 'timer':
            self._schedule_timer(rule)
        elif rule.transition == 'interval':
            self._schedule_interval(rule)
        elif rule.transition == 'schedule':
            self._schedule_time_of_day(rule)

    def _schedule_timer(self, rule: Rule):
        """Schedule a one-time timer."""
        import threading

        config = rule.trigger_config or {}
        delay_ms = config.get('delay_ms', 1000)
        auto_cleanup = config.get('auto_cleanup', False)
        delay_seconds = delay_ms / 1000.0

        def fire_once():
            print("\n" + "="*70)
            print("⏰ TIMER FIRED")
            print("="*70)
            print(f"Rule [{rule.id}]: {rule.state1} --[timer]--> {rule.state2} (delay: {delay_ms}ms)")

            # Execute the transition
            old_state = self.current_state
            if self.current_state == rule.state1 or rule.state1 == '*':
                if self.evaluate_rule_expression(rule.condition, 'condition'):
                    if rule.action:
                        self.evaluate_rule_expression(rule.action, 'action')
                    self.set_state(rule.state2)
                    print(f"State changed: {old_state} → {self.current_state}")
                else:
                    print(f"Condition not met, state remains: {self.current_state}")
            else:
                print(f"State mismatch (expected {rule.state1}, got {self.current_state}), transition skipped")

            # Auto-cleanup if configured
            if auto_cleanup and rule in self.rules:
                self.rules.remove(rule)
                print(f"Rule auto-removed")

            # Remove from active timers
            if rule.id in self.active_timers:
                del self.active_timers[rule.id]

            print("="*70)
            print("➤ ", end='', flush=True)

        timer = threading.Timer(delay_seconds, fire_once)
        timer.start()
        self.active_timers[rule.id] = timer
        print(f"Timer scheduled: {delay_ms}ms for rule {rule.id}")

    def _schedule_interval(self, rule: Rule):
        """Schedule a recurring interval."""
        import threading

        config = rule.trigger_config or {}
        delay_ms = config.get('delay_ms', 1000)
        repeat = config.get('repeat', True)
        interval_seconds = delay_ms / 1000.0

        def fire_repeatedly():
            print("\n" + "="*70)
            print("🔄 INTERVAL FIRED")
            print("="*70)
            print(f"Rule [{rule.id}]: {rule.state1} --[interval]--> {rule.state2} (every {delay_ms}ms)")

            # Execute the transition
            old_state = self.current_state
            if self.current_state == rule.state1 or rule.state1 == '*':
                if self.evaluate_rule_expression(rule.condition, 'condition'):
                    if rule.action:
                        self.evaluate_rule_expression(rule.action, 'action')
                    self.set_state(rule.state2)
                    print(f"State changed: {old_state} → {self.current_state}")
                else:
                    print(f"Condition not met, state remains: {self.current_state}")
            else:
                print(f"State mismatch (expected {rule.state1}, got {self.current_state}), transition skipped")

            # Reschedule if rule still exists and repeat is enabled
            if rule in self.rules and repeat:
                timer = threading.Timer(interval_seconds, fire_repeatedly)
                timer.start()
                self.active_timers[rule.id] = timer
                print(f"Interval will fire again in {delay_ms}ms")
            else:
                # Remove from active timers if not repeating
                if rule.id in self.active_timers:
                    del self.active_timers[rule.id]
                print(f"Interval stopped")

            print("="*70)
            print("➤ ", end='', flush=True)

        timer = threading.Timer(interval_seconds, fire_repeatedly)
        timer.start()
        self.active_timers[rule.id] = timer
        print(f"Interval scheduled: every {delay_ms}ms for rule {rule.id}")

    def _schedule_time_of_day(self, rule: Rule):
        """Schedule a rule to fire at a specific time of day."""
        import threading
        from datetime import datetime, timedelta

        config = rule.trigger_config or {}
        target_hour = config.get('hour', 0)
        target_minute = config.get('minute', 0)
        repeat_daily = config.get('repeat_daily', False)

        def calculate_next_occurrence():
            """Calculate seconds until next occurrence."""
            now = datetime.now()
            target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            # If target time has passed today, schedule for tomorrow
            if target <= now:
                target += timedelta(days=1)

            return (target - now).total_seconds()

        def fire_scheduled():
            from datetime import datetime
            now = datetime.now()

            print("\n" + "="*70)
            print("📅 SCHEDULE FIRED")
            print("="*70)
            print(f"Rule [{rule.id}]: {rule.state1} --[schedule]--> {rule.state2}")
            print(f"Scheduled time: {target_hour:02d}:{target_minute:02d}, Current time: {now.strftime('%H:%M:%S')}")

            # Execute the transition
            old_state = self.current_state
            if self.current_state == rule.state1 or rule.state1 == '*':
                if self.evaluate_rule_expression(rule.condition, 'condition'):
                    if rule.action:
                        self.evaluate_rule_expression(rule.action, 'action')
                    self.set_state(rule.state2)
                    print(f"State changed: {old_state} → {self.current_state}")
                else:
                    print(f"Condition not met, state remains: {self.current_state}")
            else:
                print(f"State mismatch (expected {rule.state1}, got {self.current_state}), transition skipped")

            # If repeat_daily, reschedule for tomorrow
            if rule in self.rules and repeat_daily:
                delay = calculate_next_occurrence()
                timer = threading.Timer(delay, fire_scheduled)
                timer.start()
                self.active_timers[rule.id] = timer
                print(f"Rescheduled for tomorrow at {target_hour:02d}:{target_minute:02d} (in {delay/3600:.1f} hours)")
            else:
                # One-time schedule, remove rule and timer
                if rule in self.rules:
                    self.rules.remove(rule)
                    print(f"One-time schedule completed, rule removed")
                if rule.id in self.active_timers:
                    del self.active_timers[rule.id]

            print("="*70)
            print("➤ ", end='', flush=True)

        # Schedule first occurrence
        delay = calculate_next_occurrence()
        timer = threading.Timer(delay, fire_scheduled)
        timer.start()
        self.active_timers[rule.id] = timer
        print(f"Schedule set: {target_hour:02d}:{target_minute:02d} ({'daily' if repeat_daily else 'once'}), firing in {delay:.0f}s")

    def set_on_render_callback(self, callback):
        """
        Set callback for RGB updates during rendering.

        Args:
            callback: Function that takes (r, g, b) tuple
        """
        self._on_render_callback = callback
        self.state_executor.set_on_rgb_update(callback)

    def _on_state_complete(self):
        """Called when renderer returns next_ms=0, signaling state completion."""
        print(f"State '{self.current_state}' completed, firing state_complete transition")
        self.execute_transition("state_complete")

    def _schedule_render(self, delay_ms: int):
        """
        Schedule next render call.

        Args:
            delay_ms: Delay in milliseconds before next render
        """
        self._cancel_render()

        if delay_ms and delay_ms > 0:
            self.render_timer = threading.Timer(
                delay_ms / 1000.0,
                self._do_render
            )
            self.render_timer.daemon = True
            self.render_timer.start()

    def _do_render(self):
        """Execute render and schedule next if needed."""
        result = self.state_executor.render()
        if result:
            rgb, next_ms = result
            # Schedule next render if animation continues
            if next_ms and next_ms > 0:
                self._schedule_render(next_ms)

    def _cancel_render(self):
        """Cancel any pending render timer."""
        if self.render_timer:
            self.render_timer.cancel()
            self.render_timer = None

    def set_state(self, state_name: str, params=None):
        """
        Set the current state with optional parameters.

        Args:
            state_name: The new state name
            params: Optional parameters to pass to the state's onEnter function
        """
        # Cancel any pending renders from previous state
        self._cancel_render()

        self.current_state = state_name
        self.current_state_params = params
        print(f"State changed to: {state_name}")

        # Execute the onEnter function for this state if it exists
        state_object = self.get_state_object(state_name)
        if state_object:
            # Initialize executor with new state
            prev_rgb = self.state_executor.get_current_rgb()
            self.state_executor.enter_state(state_object, prev_rgb)

            # Do initial render and schedule next if needed
            self._do_render()

            # Execute onEnter callback (for app-specific behavior)
            state_object.enter(params)

    def evaluate_rule_expression(self, expr: str, expr_type: str = 'condition'):
        """
        Evaluate a condition or action expression safely.

        Args:
            expr: The expression to evaluate
            expr_type: 'condition' or 'action'

        Returns:
            Result of evaluation (boolean for conditions, None for actions)
        """
        if not expr:
            return True if expr_type == 'condition' else None

        import math
        from datetime import datetime

        # State data access functions
        def getData(key, default=None):
            return self.state_data.get(key, default)

        def setData(key, value):
            self.state_data[key] = value
            return value

        def getTime():
            now = datetime.now()
            return {
                'hour': now.hour,
                'minute': now.minute,
                'second': now.second,
                'weekday': now.weekday(),
                'is_weekend': now.weekday() >= 5
            }

        # Safe evaluation context
        safe_context = {
            '__builtins__': {},
            'getData': getData,
            'setData': setData,
            'getTime': getTime,
            'None': None,
            'True': True,
            'False': False,
            # Math functions
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'int': int,
            'float': float,
            'str': str,
            'len': len,
            # Math module
            'sin': math.sin,
            'cos': math.cos,
            'floor': math.floor,
            'ceil': math.ceil,
        }

        try:
            result = eval(expr, safe_context, {})
            if expr_type == 'condition':
                return bool(result)
            return result
        except Exception as e:
            print(f"Expression evaluation error ({expr_type}): {expr} -> {e}")
            return True if expr_type == 'condition' else None

    def execute_transition(self, action: str) -> bool:
        """
        Execute a transition based on an action.

        Rules are evaluated in priority order (highest first).
        First matching rule with a passing condition wins.

        Args:
            action: The action/transition to execute

        Returns:
            True if transition was executed, False otherwise
        """
        # Find all matching rules (state + transition match, enabled only)
        candidate_rules = [r for r in self.rules if r.matches(self.current_state, action)]

        # Sort by priority (highest first)
        candidate_rules.sort(key=lambda r: r.priority, reverse=True)

        # Find first rule whose condition is true
        matching_rule = None
        for rule in candidate_rules:
            if not rule.condition:
                matching_rule = rule
                break
            if self.evaluate_rule_expression(rule.condition, 'condition'):
                matching_rule = rule
                break

        if matching_rule:
            print(f"Transition: {matching_rule}")

            # Execute action if present (before state transition)
            if matching_rule.action:
                print(f"Executing action: {matching_rule.action}")
                self.evaluate_rule_expression(matching_rule.action, 'action')

            # Execute pipeline if present
            if matching_rule.pipeline and self.pipeline_executor:
                print(f"Executing pipeline: {matching_rule.pipeline}")
                self._execute_pipeline(matching_rule.pipeline)

            # Transition to new state (if state2 is set)
            if matching_rule.state2:
                self.set_state(matching_rule.state2)
            return True
        else:
            if candidate_rules:
                print(f"Rules found for action '{action}' in state {self.current_state}, "
                      f"but no conditions matched")
            else:
                print(f"No transition found for action '{action}' in state {self.current_state}")
            return False

    def _execute_pipeline(self, pipeline_name: str):
        """Execute a pipeline by name."""
        if not self.pipeline_executor:
            print(f"No pipeline executor configured, cannot run: {pipeline_name}")
            return

        from .pipeline_registry import get_pipeline_registry
        registry = get_pipeline_registry()
        pipeline = registry.get(pipeline_name)

        if not pipeline:
            print(f"Pipeline not found: {pipeline_name}")
            return

        # Execute in a thread to avoid blocking
        import threading

        def run_pipeline():
            try:
                self.pipeline_executor.execute(pipeline)
            except Exception as e:
                print(f"Pipeline execution error: {e}")

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

    def get_state(self) -> str:
        """Get the current state."""
        return self.current_state

    def get_state_params(self):
        """Get the current state parameters."""
        return self.current_state_params

    def set_data(self, key: str, value: Any):
        """Set state data."""
        self.state_data[key] = value

    def get_data(self, key: str, default=None) -> Any:
        """Get state data."""
        return self.state_data.get(key, default)

    def get_time(self):
        """
        Get current time information.

        Returns:
            Dict with hour, minute, second, day_of_week (0=Monday), timestamp
        """
        from datetime import datetime
        now = datetime.now()
        return {
            'hour': now.hour,
            'minute': now.minute,
            'second': now.second,
            'day_of_week': now.weekday(),  # 0=Monday
            'timestamp': now.timestamp()
        }

    def clear_data(self):
        """Clear all state data."""
        self.state_data = {}

    def stop_interval(self):
        """Stop the current interval if running."""
        if self.interval:
            # Signal the thread to stop by setting interval to None
            interval_thread = self.interval
            self.interval = None
            self.interval_callback = None
            # Wait briefly for thread to finish
            if interval_thread.is_alive():
                interval_thread.join(timeout=0.5)
            print("State machine interval stopped")

    def start_interval(self, callback: Callable, interval_ms: int = 100, debug: bool = False):
        """
        Start an interval for state machine execution.

        Args:
            callback: Function to execute on each interval
            interval_ms: Interval in milliseconds
            debug: Enable debug output (FPS timing)
        """
        import threading
        import time

        self.stop_interval()

        self.interval_callback = callback
        self.interval_ms = interval_ms

        def interval_loop():
            """Run the callback in a loop until stopped."""
            start_time = time.time()
            update_count = 0

            while self.interval is not None:
                try:
                    self.interval_callback()
                    update_count += 1

                    # Debug timing output
                    if debug and update_count % 50 == 0:
                        elapsed = time.time() - start_time
                        avg_interval = elapsed / update_count * 1000
                        fps = update_count / elapsed if elapsed > 0 else 0
                        print(f"[STATE_ANIM] Updates: {update_count}, Avg interval: {avg_interval:.1f}ms, Target: {interval_ms}ms, FPS: {fps:.1f}")

                except Exception as e:
                    print(f"Interval callback error: {e}")
                    break

                # Sleep for the interval duration
                if self.interval is not None:
                    time.sleep(interval_ms / 1000.0)

        # Start the interval thread
        self.interval = threading.Thread(target=interval_loop, daemon=True)
        self.interval.start()
        print(f"State machine interval started ({interval_ms}ms)")

    def reset(self, restore_defaults=True):
        """Reset the state machine to initial state.

        Args:
            restore_defaults: If True, clear all rules/states and restore defaults
        """
        self.stop_interval()
        self._cancel_render()  # Cancel any pending render
        self.current_state = 'off'
        self.current_state_params = None
        self.state_data = {}

        # Cancel all timers
        for rule_id, timer in list(self.active_timers.items()):
            timer.cancel()
        self.active_timers = {}

        if restore_defaults:
            # Clear existing rules and states
            self.rules = []
            self.states = States()
            self.rule_id_counter = 0
            # Re-add default rules
            self._setup_default_rules()

        print("State machine reset")

    def get_current_rgb(self):
        """Get the current RGB values from the state executor."""
        return self.state_executor.get_current_rgb()

    def get_summary(self):
        """Get a summary of the state machine."""
        return {
            'rules_count': len(self.rules),
            'current_state': self.current_state,
            'current_rgb': self.state_executor.get_current_rgb(),
            'state_data': dict(self.state_data),
            'is_running': self.interval is not None,
            'representation_version': self.representation_version
        }
