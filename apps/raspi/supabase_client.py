"""
Supabase client for storing command sessions.

Stores each voice command along with the full state machine snapshot
(all states, all rules) after processing.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Supabase client instance
_client = None


def get_client():
    """Get or create Supabase client."""
    global _client

    if _client is not None:
        return _client

    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_ANON_KEY')

    if not url or not key:
        print("Warning: SUPABASE_URL or SUPABASE_ANON_KEY not set. Database logging disabled.")
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        print("Supabase client initialized")
        return _client
    except Exception as e:
        print(f"Failed to initialize Supabase: {e}")
        return None


def log_command_session(
    user_id: str,
    command: str,
    response_message: str,
    success: bool,
    current_state: str,
    current_state_data: Dict[str, Any],
    all_states: List[Dict[str, Any]],
    all_rules: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]] = None,
    agent_steps: List[Dict[str, Any]] = None,
    timing_ms: float = None,
    run_id: str = None,
    source: str = "raspi"
) -> Optional[str]:
    """
    Log a command session with full state machine snapshot.

    Args:
        user_id: User identifier
        command: The command text
        response_message: Response message from the agent
        success: Whether the command succeeded
        current_state: Current state name after command
        current_state_data: Current state full data
        all_states: List of all states after command
        all_rules: List of all rules after command
        tool_calls: List of tool calls made
        agent_steps: List of agent execution steps
        timing_ms: Total processing time
        run_id: Unique run identifier
        source: Source of command ("raspi" or "web")

    Returns:
        Session ID (UUID) or None if failed
    """
    client = get_client()
    if not client:
        return None

    try:
        record = {
            'user_id': user_id,
            'command': command,
            'response_message': response_message,
            'success': success,
            'current_state': current_state,
            'current_state_data': current_state_data,
            'all_states': all_states or [],
            'all_rules': all_rules or [],
            'tool_calls': tool_calls or [],
            'agent_steps': agent_steps or [],
            'timing_ms': timing_ms,
            'run_id': run_id,
            'source': source,
            'created_at': datetime.now(timezone.utc).isoformat()
        }

        result = client.table('command_sessions').insert(record).execute()

        if result.data:
            session_id = result.data[0].get('id')
            print(f"Logged command session: {session_id}")
            return session_id
        return None
    except Exception as e:
        print(f"Failed to log command session: {e}")
        return None


def submit_quick_feedback(
    session_id: str,
    worked: bool
) -> bool:
    """
    Submit quick feedback (worked/didn't work) for a command session.

    Args:
        session_id: The session UUID to update
        worked: True if the result worked as expected, False otherwise

    Returns:
        True if successful
    """
    client = get_client()
    if not client:
        return False

    try:
        update_data = {
            'worked': worked,
            'quick_feedback_at': datetime.now(timezone.utc).isoformat()
        }

        client.table('command_sessions').update(update_data).eq('id', session_id).execute()
        print(f"Quick feedback submitted for session: {session_id} - worked: {worked}")
        return True
    except Exception as e:
        print(f"Failed to submit quick feedback: {e}")
        return False
