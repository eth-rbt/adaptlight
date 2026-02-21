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
from flask_cors import CORS
from brain import SMgenerator

# Add web app directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))
import supabase_client


from brain.processing.vision_runtime import VisionRuntime
from brain.processing.api_runtime import APIRuntime
from brain.processing.audio_runtime import AudioRuntime
from brain.processing.volume_runtime import VolumeRuntime
from brain.apis.api_executor import APIExecutor

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
        'vision_config': config.get('vision', {}),  # Pass vision capabilities to agent
    }
    smgen = SMgenerator(smgen_config)

    vision_runtime = VisionRuntime(
        smgen=smgen,
        config=config.get('vision', {}),
        openai_api_key=config.get('openai', {}).get('api_key')
    )

    # Initialize API executor and runtime
    api_executor = APIExecutor(timeout=15.0)
    api_runtime = APIRuntime(
        smgen=smgen,
        api_executor=api_executor,
        config=config.get('api', {})
    )
    audio_runtime = AudioRuntime(
        smgen=smgen,
        config=config.get('audio', {}),
        openai_api_key=config.get('openai', {}).get('api_key')
    )
    volume_runtime = VolumeRuntime(
        smgen=smgen,
        config=config.get('volume', {})
    )

    # Create Flask app
    app = Flask(__name__, static_folder='static')
    CORS(app)  # Enable CORS for all routes
    app.config['smgen'] = smgen
    app.config['vision_runtime'] = vision_runtime
    app.config['api_runtime'] = api_runtime
    app.config['audio_runtime'] = audio_runtime
    app.config['volume_runtime'] = volume_runtime

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
        vision_cfg = config.get('vision', {})
        vision_mode = str(vision_cfg.get('mode', 'polling')).lower()
        if vision_mode not in ('polling', 'realtime'):
            vision_mode = 'polling'

        api_cfg = config.get('api', {})
        audio_cfg = config.get('audio', {})
        volume_cfg = config.get('volume', {})

        return jsonify({
            'success': True,
            'representation_version': representation_version,
            'vision': {
                'enabled': bool(vision_cfg.get('enabled', False)),
                'mode': vision_mode,
                'latest_frame_only': bool(vision_cfg.get('latest_frame_only', True)),
                'interval_ms': max(1000, int(vision_cfg.get('interval_ms', 2000))),
                'max_image_chars': int(vision_cfg.get('max_image_chars', 2_500_000)),
                'cv': {
                    'enabled': bool((vision_cfg.get('cv') or {}).get('enabled', False)),
                    'interval_ms': max(1000, int((vision_cfg.get('cv') or {}).get('interval_ms', 1000))),
                    'detector': str((vision_cfg.get('cv') or {}).get('detector', 'opencv_hog')).lower(),
                },
                'vlm': {
                    'enabled': bool((vision_cfg.get('vlm') or {}).get('enabled', False)),
                    'model': str((vision_cfg.get('vlm') or {}).get('model', 'gpt-4o-mini')),
                    'min_confidence': float((vision_cfg.get('vlm') or {}).get('min_confidence', 0.55)),
                },
            },
            'audio': {
                'enabled': bool(audio_cfg.get('enabled', True)),
                'model': str(audio_cfg.get('model', 'gpt-4o-mini')),
                'interval_ms': max(1000, int(audio_cfg.get('interval_ms', 3000))),
                'cooldown_ms': max(0, int(audio_cfg.get('cooldown_ms', 1500))),
                'allow_fallback_transcript': bool(audio_cfg.get('allow_fallback_transcript', False)),
            },
            'volume': {
                'enabled': bool(volume_cfg.get('enabled', True)),
                'interval_ms': max(30, int(volume_cfg.get('interval_ms', 80))),
                'smoothing_alpha': float(volume_cfg.get('smoothing_alpha', 0.35)),
                'floor': float(volume_cfg.get('floor', 0.0)),
                'ceiling': float(volume_cfg.get('ceiling', 1.0)),
            },
            'api': {
                'enabled': bool(api_cfg.get('enabled', True)),
                'default_interval_ms': max(1000, int(api_cfg.get('default_interval_ms', 30000))),
                'min_interval_ms': max(1000, int(api_cfg.get('min_interval_ms', 1000))),
            },
        })

    @app.route('/api/vision/session/start', methods=['POST'])
    def vision_start_session():
        """Start a vision session for camera frame ingestion."""
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', 'anonymous')
        runtime: VisionRuntime = app.config['vision_runtime']

        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'vision runtime disabled'}), 400

        session = runtime.start_session(user_id=user_id)
        return jsonify({'success': True, **session})

    @app.route('/api/vision/session/stop', methods=['POST'])
    def vision_stop_session():
        """Stop an active vision session."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.stop_session(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/vision/status', methods=['GET'])
    def vision_status():
        """Get current vision session status."""
        session_id = request.args.get('session_id', '')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.get_status(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/vision/frame', methods=['POST'])
    def vision_frame():
        """Analyze a camera frame via OpenAI VLM and trigger transitions."""
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        image_data_url = data.get('image')

        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        if not image_data_url:
            return jsonify({'success': False, 'error': 'image required'}), 400

        runtime: VisionRuntime = app.config['vision_runtime']
        result = runtime.process_frame(session_id=session_id, image_data_url=image_data_url)

        if not result.get('success'):
            if result.get('error') in ('session not found',):
                return jsonify(result), 404
            return jsonify(result), 400

        return jsonify(result)

    # ─────────────────────────────────────────────────────────────
    @app.route('/api/audio/session/start', methods=['POST'])
    def audio_start_session():
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', 'anonymous')
        runtime: AudioRuntime = app.config['audio_runtime']
        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'audio runtime disabled'}), 400
        session = runtime.start_session(user_id=user_id)
        return jsonify({'success': True, **session})

    @app.route('/api/audio/session/stop', methods=['POST'])
    def audio_stop_session():
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        runtime: AudioRuntime = app.config['audio_runtime']
        result = runtime.stop_session(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/audio/status', methods=['GET'])
    def audio_status():
        session_id = request.args.get('session_id', '')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        runtime: AudioRuntime = app.config['audio_runtime']
        result = runtime.get_status(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/audio/chunk', methods=['POST'])
    def audio_chunk():
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        transcript = data.get('transcript')
        chunk_meta = data.get('chunk_meta') or {}
        debug_audio_llm = str(os.environ.get('ADAPTLIGHT_DEBUG_AUDIO_LLM', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        if not transcript:
            return jsonify({'success': False, 'error': 'transcript required'}), 400

        if debug_audio_llm:
            print(f"[audio_chunk] session={session_id} transcript={str(transcript)[:160]!r} chunk_meta={chunk_meta}")

        runtime: AudioRuntime = app.config['audio_runtime']
        result = runtime.process_chunk(session_id=session_id, transcript=transcript, chunk_meta=chunk_meta)

        if debug_audio_llm:
            print(
                f"[audio_chunk] success={result.get('success')} processed={result.get('processed')} "
                f"emitted={result.get('emitted_events')} audio={result.get('audio')}"
            )

        if not result.get('success'):
            if result.get('error') in ('session not found',):
                return jsonify(result), 404
            return jsonify(result), 400
        return jsonify(result)

    @app.route('/api/volume/session/start', methods=['POST'])
    def volume_start_session():
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id', 'anonymous')
        runtime: VolumeRuntime = app.config['volume_runtime']
        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'volume runtime disabled'}), 400
        session = runtime.start_session(user_id=user_id)
        return jsonify({'success': True, **session})

    @app.route('/api/volume/session/stop', methods=['POST'])
    def volume_stop_session():
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        runtime: VolumeRuntime = app.config['volume_runtime']
        result = runtime.stop_session(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/volume/status', methods=['GET'])
    def volume_status():
        session_id = request.args.get('session_id', '')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        runtime: VolumeRuntime = app.config['volume_runtime']
        result = runtime.get_status(session_id)
        if not result.get('success'):
            return jsonify(result), 404
        return jsonify(result)

    @app.route('/api/volume/frame', methods=['POST'])
    def volume_frame():
        data = request.get_json(silent=True) or {}
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'session_id required'}), 400
        runtime: VolumeRuntime = app.config['volume_runtime']
        result = runtime.ingest_frame(
            session_id=session_id,
            level=data.get('level'),
            rms=data.get('rms'),
            peak=data.get('peak'),
            speaking=data.get('speaking'),
        )
        if not result.get('success'):
            if result.get('error') in ('session not found',):
                return jsonify(result), 404
            return jsonify(result), 400
        return jsonify(result)

    # API Reactive Routes
    # ─────────────────────────────────────────────────────────────

    @app.route('/api/api/tick', methods=['POST'])
    def api_tick():
        """Tick the API runtime to check for due fetches."""
        runtime: APIRuntime = app.config['api_runtime']

        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'api runtime disabled'}), 400

        result = runtime.tick()
        return jsonify(result)

    @app.route('/api/api/force', methods=['POST'])
    def api_force_fetch():
        """Force an immediate fetch for a specific key."""
        data = request.get_json(silent=True) or {}
        key = data.get('key')

        if not key:
            return jsonify({'success': False, 'error': 'key required'}), 400

        runtime: APIRuntime = app.config['api_runtime']

        if not runtime.enabled:
            return jsonify({'success': False, 'error': 'api runtime disabled'}), 400

        result = runtime.force_fetch(key)
        return jsonify(result)

    @app.route('/api/api/clear-cache', methods=['POST'])
    def api_clear_cache():
        """Clear API cache for a specific key or all keys."""
        data = request.get_json(silent=True) or {}
        key = data.get('key')  # Optional, clears all if not provided

        runtime: APIRuntime = app.config['api_runtime']
        runtime.clear_cache(key)

        return jsonify({'success': True, 'cleared': key or 'all'})

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
