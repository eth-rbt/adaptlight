"""
Event logger for AdaptLight.

Logs three types of events:
1. Voice commands - user speech input and parsed rules
2. Button events - physical button interactions
3. State changes - lamp state transitions

All events are logged with timestamps in JSON format.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


class EventLogger:
    """Unified event logging for voice, button, and state changes."""

    def __init__(self, log_dir='data/logs'):
        """
        Initialize event logger.

        Args:
            log_dir: Base directory for log files
        """
        self.log_dir = Path(log_dir)

        # Create log subdirectories
        self.voice_log_dir = self.log_dir / 'voice_commands'
        self.button_log_dir = self.log_dir / 'button_events'
        self.state_log_dir = self.log_dir / 'state_changes'

        for log_dir in [self.voice_log_dir, self.button_log_dir, self.state_log_dir]:
            log_dir.mkdir(parents=True, exist_ok=True)

        print(f"EventLogger initialized: {self.log_dir}")

    def log_voice_command(self, text: str, parsed_rules: list = None, state_before: str = None, state_after: str = None, state_params: dict = None):
        """
        Log a voice command event.

        Args:
            text: The voice command text
            parsed_rules: List of rules parsed from the command
            state_before: State before command execution
            state_after: State after command execution
            state_params: Parameters of the resulting state
        """
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': 'voice_command',
            'text': text,
            'parsed_rules': parsed_rules or [],
            'state_before': state_before,
            'state_after': state_after,
            'state_params': state_params
        }

        self._write_log(self.voice_log_dir, event)
        print(f"Logged voice command: {text} (state: {state_before} -> {state_after})")

    def log_button_event(self, event_type: str, state_before: str = None, state_after: str = None, state_params: dict = None):
        """
        Log a button event.

        Args:
            event_type: Type of button event (button_click, button_hold, etc.)
            state_before: State before button event
            state_after: State after button event
            state_params: Parameters of the resulting state
        """
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': 'button_event',
            'event': event_type,
            'state_before': state_before,
            'state_after': state_after,
            'state_params': state_params
        }

        self._write_log(self.button_log_dir, event)
        print(f"Logged button event: {event_type} (state: {state_before} -> {state_after})")

    def log_state_change(self, from_state: str, to_state: str, params=None):
        """
        Log a state change event.

        Args:
            from_state: Previous state
            to_state: New state
            params: Optional parameters passed to new state
        """
        event = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': 'state_change',
            'from': from_state,
            'to': to_state,
            'params': params
        }

        self._write_log(self.state_log_dir, event)
        print(f"Logged state change: {from_state} -> {to_state}")

    def _write_log(self, log_dir: Path, event: dict):
        """
        Write a log event to a daily JSONL file.

        Args:
            log_dir: Directory to write log to
            event: Event dictionary to log
        """
        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create daily log file
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        log_file = log_dir / f'log-{date_str}.jsonl'

        # Append to file
        with open(log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

    def get_log_files(self, log_type='all', start_date=None, end_date=None):
        """
        Get list of log files.

        Args:
            log_type: 'voice', 'button', 'state', or 'all'
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of log file paths
        """
        log_files = []

        if log_type in ['voice', 'all']:
            log_files.extend(self.voice_log_dir.glob('log-*.jsonl'))
        if log_type in ['button', 'all']:
            log_files.extend(self.button_log_dir.glob('log-*.jsonl'))
        if log_type in ['state', 'all']:
            log_files.extend(self.state_log_dir.glob('log-*.jsonl'))

        # TODO: Apply date filters if provided
        return sorted(log_files)

    def read_log_file(self, log_file_path):
        """
        Read and parse a log file.

        Args:
            log_file_path: Path to log file

        Returns:
            List of log events
        """
        events = []
        with open(log_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        print(f"Warning: Failed to parse log line: {line}")
        return events
