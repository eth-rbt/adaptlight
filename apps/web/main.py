"""
AdaptLight Web Application

Flask-based web interface using the SMgenerator library.
"""

import os
import sys
from pathlib import Path

# Add parent directories to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env file from root directory
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

import yaml
from flask import Flask, request, jsonify, send_from_directory
from brain import SMgenerator

# Add web app directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))
import supabase_client


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / 'config.yaml'

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Expand environment variables
    def expand_env(obj):
        if isinstance(obj, str) and obj.startswith('${') and obj.endswith('}'):
            env_var = obj[2:-1]
            return os.environ.get(env_var, '')
        elif isinstance(obj, dict):
            return {k: expand_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env(item) for item in obj]
        return obj

    return expand_env(config)


def load_eval_cases() -> list:
    """Load eval cases from apps/eval/cases/cases.txt."""
    cases_path = ROOT_DIR / 'apps' / 'eval' / 'cases' / 'cases.txt'
    if not cases_path.exists():
        return []

    with open(cases_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines()]

    return [line for line in lines if line]


def create_app(config_path: str = None) -> Flask:
    """Create and configure the Flask application."""
    config = load_config(config_path)

    # Get representation version from config
    representation_version = config.get('representation', {}).get('version', 'stdlib')

    # Debug: confirm env loading (do not print secret values)
    env_anthropic = os.environ.get('ANTHROPIC_API_KEY', '')
    env_openai = os.environ.get('OPENAI_API_KEY', '')
    print(f"[env] cwd={os.getcwd()}")
    print(f"[env] .env path={ROOT_DIR / '.env'} exists={os.path.exists(ROOT_DIR / '.env')}")
    print(f"[env] ANTHROPIC_API_KEY loaded={bool(env_anthropic)} length={len(env_anthropic)}")
    print(f"[env] OPENAI_API_KEY loaded={bool(env_openai)} length={len(env_openai)}")

    # Trim whitespace from API keys to avoid hidden trailing spaces
    if isinstance(config.get('anthropic', {}).get('api_key'), str):
        config['anthropic']['api_key'] = config['anthropic']['api_key'].strip()
    if isinstance(config.get('openai', {}).get('api_key'), str):
        config['openai']['api_key'] = config['openai']['api_key'].strip()
    if isinstance(config.get('supabase', {}).get('url'), str):
        config['supabase']['url'] = config['supabase']['url'].strip()
    if isinstance(config.get('supabase', {}).get('anon_key'), str):
        config['supabase']['anon_key'] = config['supabase']['anon_key'].strip()

    # Initialize SMgenerator
    smgen_config = {
        'mode': config['brain']['mode'],
        'model': config['brain']['model'],
        'prompt_variant': config['brain']['prompt_variant'],
        'max_turns': config['brain'].get('max_turns', 10),
        'verbose': config['brain'].get('verbose', False),
        'anthropic_api_key': config['anthropic']['api_key'],
        'openai_api_key': config['openai']['api_key'],
        'storage_dir': config.get('storage', {}).get('dir', 'data/storage'),
        'representation_version': representation_version,
    }
    smgen = SMgenerator(smgen_config)

    # Create Flask app
    app = Flask(__name__, static_folder='static')
    app.config['smgen'] = smgen

    # ─────────────────────────────────────────────────────────────
    # Routes
    # ─────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        """Serve the main page."""
        response = send_from_directory('static', 'index.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/eval')
    def eval_page():
        """Serve the eval page."""
        response = send_from_directory('static', 'eval.html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/static/<path:path>')
    def serve_static(path):
        """Serve static files."""
        response = send_from_directory('static', path)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/api/process', methods=['POST'])
    def process():
        """Process user input text."""
        data = request.get_json()
        text = data.get('text', '')
        user_id = data.get('user_id', 'anonymous')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        try:
            result = smgen.process(text)

            # Get full state machine snapshot (all states and rules)
            details = smgen.get_details()

            # Log command session with full snapshot to Supabase
            session_id = supabase_client.log_command_session(
                user_id=user_id,
                command=text,
                response_message=result.message,
                success=result.success,
                current_state=result.state.get('name') if result.state else None,
                current_state_data=result.state,
                all_states=details.get('states', []),
                all_rules=details.get('rules', []),
                tool_calls=result.tool_calls,
                agent_steps=result.agent_steps,
                timing_ms=result.timing.get('total_ms') if result.timing else None,
                run_id=result.run_id
            )

            return jsonify({
                'success': result.success,
                'state': result.state,
                'message': result.message,
                'tool_calls': result.tool_calls,
                'timing': result.timing,
                'run_id': result.run_id,
                'agent_steps': result.agent_steps,
                'session_id': session_id,  # For feedback submission
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/trigger', methods=['POST'])
    def trigger():
        """Trigger a state machine event (button presses - not logged)."""
        data = request.get_json()
        event = data.get('event', 'button_click')

        try:
            state = smgen.trigger(event)
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/state', methods=['GET'])
    def get_state():
        """Get current state."""
        try:
            state = smgen.get_state()
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/summary', methods=['GET'])
    def get_summary():
        """Get SMgenerator summary."""
        try:
            summary = smgen.get_summary()
            return jsonify({
                'success': True,
                'summary': summary,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/details', methods=['GET'])
    def get_details():
        """Get detailed states and rules."""
        try:
            details = smgen.get_details()
            return jsonify({
                'success': True,
                **details,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/reset', methods=['POST'])
    def reset():
        """Reset the state machine generator (not logged)."""
        try:
            smgen.reset()
            state = smgen.get_state()
            return jsonify({
                'success': True,
                'state': state,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/eval/cases', methods=['GET'])
    def get_eval_cases():
        """Return evaluation cases from cases.txt."""
        cases = load_eval_cases()
        return jsonify({
            'success': True,
            'cases': cases,
        })

    @app.route('/api/eval/process', methods=['POST'])
    def eval_process():
        """Process eval input text with a chosen implementation (stubbed)."""
        data = request.get_json()
        text = data.get('text', '')
        implementation = data.get('implementation', 'state_machine')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        try:
            result = smgen.process(text)

            return jsonify({
                'success': result.success,
                'state': result.state,
                'message': result.message,
                'tool_calls': result.tool_calls,
                'timing': result.timing,
                'run_id': result.run_id,
                'implementation': implementation,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'implementation': implementation,
            }), 500

    @app.route('/api/feedback', methods=['POST'])
    def submit_feedback():
        """Submit feedback for a command session."""
        data = request.get_json()
        session_id = data.get('session_id')
        feedback = data.get('feedback', '')
        rating = data.get('rating')  # Optional 1-5

        if not session_id:
            return jsonify({'error': 'No session_id provided'}), 400

        if not feedback:
            return jsonify({'error': 'No feedback provided'}), 400

        try:
            success = supabase_client.submit_feedback(
                session_id=session_id,
                feedback=feedback,
                rating=rating
            )
            return jsonify({
                'success': success,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/quick-feedback', methods=['POST'])
    def submit_quick_feedback():
        """Submit quick feedback (worked/didn't work) for a command session."""
        data = request.get_json()
        session_id = data.get('session_id')
        worked = data.get('worked')

        if not session_id:
            return jsonify({'error': 'No session_id provided'}), 400

        if worked is None:
            return jsonify({'error': 'No worked value provided'}), 400

        try:
            success = supabase_client.submit_quick_feedback(
                session_id=session_id,
                worked=worked
            )
            return jsonify({
                'success': success,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/history', methods=['GET'])
    def get_history():
        """Get command sessions for a user."""
        user_id = request.args.get('user_id', 'anonymous')
        limit = request.args.get('limit', 50, type=int)

        try:
            sessions = supabase_client.get_user_sessions(user_id, limit)
            return jsonify({
                'success': True,
                'sessions': sessions,
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e),
            }), 500

    @app.route('/api/config', methods=['GET'])
    def get_config():
        """Get frontend-relevant config (representation version)."""
        return jsonify({
            'success': True,
            'representation_version': representation_version,
        })

    return app


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='AdaptLight Web Server')
    parser.add_argument('--config', '-c', help='Path to config file')
    parser.add_argument('--port', '-p', type=int, default=3000, help='Port to listen on')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    app = create_app(args.config)

    print("=" * 60)
    print("AdaptLight Web Server")
    print("=" * 60)
    print(f"Running on http://{args.host}:{args.port}")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
