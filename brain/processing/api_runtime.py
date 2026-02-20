"""
API Runtime for AdaptLight.

Polls APIs based on state's api_reactive configuration and writes results
to state_data. Can emit events for rule transitions.

Supports:
- Preset APIs (weather, stock, crypto, etc.)
- Custom URLs with configurable method/headers
"""

import threading
import time
import requests
from typing import TYPE_CHECKING, Optional, Dict, Any

if TYPE_CHECKING:
    from brain import SMgenerator


class APIRuntime:
    """Runtime for API-reactive state behavior."""

    def __init__(self, smgen: "SMgenerator", api_executor=None, config: dict = None):
        """
        Initialize API runtime.

        Args:
            smgen: SMgenerator instance for state machine access
            api_executor: Optional APIExecutor for preset APIs
            config: Optional configuration dict
        """
        self.smgen = smgen
        self.state_machine = smgen.state_machine
        self.api_executor = api_executor
        self.config = config or {}

        self.enabled = self.config.get('enabled', True)
        self.default_interval_ms = max(1000, int(self.config.get('default_interval_ms', 30000)))
        self.min_interval_ms = max(1000, int(self.config.get('min_interval_ms', 1000)))
        self.timeout = float(self.config.get('timeout', 15.0))
        self.default_cooldown_ms = int(self.config.get('cooldown_ms', 1000))

        self._lock = threading.Lock()
        self._last_fetch_ms: Dict[str, int] = {}  # key -> last fetch timestamp
        self._last_event_ms: Dict[str, int] = {}  # event -> last emit timestamp
        self._cache: Dict[str, Any] = {}  # key -> cached result

    def tick(self) -> dict:
        """
        Called periodically to check if any API fetches are due.

        Returns:
            Dict with fetched data and emitted events
        """
        if not self.enabled:
            return {'success': False, 'reason': 'api runtime disabled'}

        # Get active API watchers from current state
        watchers = self._get_active_watchers()
        if not watchers:
            return {'success': True, 'processed': False, 'reason': 'no_active_api_watchers'}

        now_ms = int(time.time() * 1000)
        fetched = []
        emitted_events = []

        for watcher in watchers:
            watcher_key = watcher.get('key', watcher.get('api', 'default'))
            interval_ms = max(self.min_interval_ms, int(watcher.get('interval_ms', self.default_interval_ms)))

            # Check if fetch is due
            with self._lock:
                last_fetch = self._last_fetch_ms.get(watcher_key, 0)

            if last_fetch and (now_ms - last_fetch) < interval_ms:
                continue  # Not due yet

            # Perform fetch
            result = self._fetch(watcher)

            if result.get('success'):
                data = result.get('data', {})

                # Add metadata
                data['_timestamp'] = now_ms
                data['_source'] = 'api_reactive'

                # Write to state_data
                self.state_machine.set_data(watcher_key, data)
                print(f"[api_runtime] wrote to state_data['{watcher_key}']: {data}")

                fetched.append(watcher_key)

                # Update last fetch time
                with self._lock:
                    self._last_fetch_ms[watcher_key] = now_ms

                # Emit event if configured
                event_name = watcher.get('event')
                if event_name:
                    # Check cooldown
                    cooldown_ms = int(watcher.get('cooldown_ms', self.default_cooldown_ms))
                    with self._lock:
                        last_event = self._last_event_ms.get(event_name, 0)
                        can_emit = (now_ms - last_event) >= cooldown_ms

                    if can_emit:
                        # Add api_ prefix if not present
                        if not event_name.startswith('api_'):
                            event_name = f"api_{event_name}"

                        self.smgen.trigger(event_name)
                        emitted_events.append(event_name)

                        with self._lock:
                            self._last_event_ms[event_name] = now_ms
            else:
                print(f"[api_runtime] fetch failed for '{watcher_key}': {result.get('error')}")

        return {
            'success': True,
            'processed': len(fetched) > 0,
            'fetched': fetched,
            'emitted_events': emitted_events,
            'state': self.smgen.get_state(),
        }

    def _get_active_watchers(self) -> list:
        """
        Get active API watchers from current state and rules.

        Returns list of watcher configs with:
        - api, url, method, headers, params
        - interval_ms, key, event, cooldown_ms
        """
        watchers = []
        current_state = self.state_machine.get_state()

        # State-level api_reactive
        state = self.smgen.get_state() or {}
        api_config = state.get('api_reactive') or {}

        if api_config.get('enabled'):
            watchers.append({
                'source': 'state',
                'api': api_config.get('api'),
                'url': api_config.get('url'),
                'method': str(api_config.get('method', 'GET')).upper(),
                'headers': api_config.get('headers', {}),
                'params': api_config.get('params', {}),
                'interval_ms': api_config.get('interval_ms', self.default_interval_ms),
                'key': api_config.get('key', api_config.get('api', 'api_data')),
                'event': api_config.get('event'),
                'cooldown_ms': api_config.get('cooldown_ms', self.default_cooldown_ms),
            })

        # Rule-level api_reactive via trigger_config
        for idx, rule in enumerate(self.state_machine.get_rules()):
            if not rule.enabled:
                continue
            if not self._state_match(rule.state1, current_state):
                continue

            config = rule.trigger_config or {}
            api_config = config.get('api') if isinstance(config, dict) else None

            if not isinstance(api_config, dict) or not api_config.get('enabled'):
                continue

            # Get event name for rules
            event_name = api_config.get('event') or rule.transition

            watchers.append({
                'source': f'rule:{idx}',
                'api': api_config.get('api'),
                'url': api_config.get('url'),
                'method': str(api_config.get('method', 'GET')).upper(),
                'headers': api_config.get('headers', {}),
                'params': api_config.get('params', {}),
                'interval_ms': api_config.get('interval_ms', self.default_interval_ms),
                'key': api_config.get('key', api_config.get('api', 'api_data')),
                'event': event_name,
                'cooldown_ms': api_config.get('cooldown_ms', self.default_cooldown_ms),
            })

        return watchers

    @staticmethod
    def _state_match(rule_state: str, current_state: str) -> bool:
        """Check if rule state matches current state (with wildcard support)."""
        if rule_state == '*':
            return True
        if isinstance(rule_state, str) and rule_state.endswith('/*'):
            prefix = rule_state[:-2]
            return current_state.startswith(prefix + '/')
        return rule_state == current_state

    def _fetch(self, watcher: dict) -> dict:
        """
        Perform API fetch.

        Supports:
        - Preset APIs via api_executor
        - Custom URLs via direct HTTP request
        """
        api_name = watcher.get('api')
        url = watcher.get('url')
        params = watcher.get('params', {})

        # Option 1: Use preset API
        if api_name and self.api_executor:
            try:
                result = self.api_executor.execute(api_name, params)
                return result
            except Exception as e:
                return {'success': False, 'error': str(e)}

        # Option 2: Custom URL
        if url:
            return self._fetch_url(
                url=url,
                method=watcher.get('method', 'GET'),
                headers=watcher.get('headers', {}),
                params=params,
            )

        return {'success': False, 'error': 'No api or url specified'}

    def _fetch_url(self, url: str, method: str = 'GET', headers: dict = None,
                   params: dict = None) -> dict:
        """
        Fetch from custom URL.

        Args:
            url: Full URL to fetch
            method: HTTP method (GET, POST, etc.)
            headers: Optional headers dict
            params: Optional params (query params for GET, body for POST)

        Returns:
            Dict with success, data/error
        """
        headers = headers or {}
        params = params or {}

        # Add default User-Agent if not specified
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'AdaptLight/1.0'

        try:
            if method == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            elif method == 'POST':
                response = requests.post(url, json=params, headers=headers, timeout=self.timeout)
            elif method == 'PUT':
                response = requests.put(url, json=params, headers=headers, timeout=self.timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=self.timeout)
            else:
                return {'success': False, 'error': f'Unsupported method: {method}'}

            response.raise_for_status()

            # Try to parse as JSON
            try:
                data = response.json()
            except Exception:
                data = {'text': response.text}

            return {'success': True, 'data': data}

        except requests.exceptions.Timeout:
            return {'success': False, 'error': f'Timeout after {self.timeout}s'}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_cached(self, key: str) -> Optional[dict]:
        """Get cached API result by key."""
        with self._lock:
            return self._cache.get(key)

    def clear_cache(self, key: str = None):
        """Clear cache for a specific key or all keys."""
        with self._lock:
            if key:
                self._cache.pop(key, None)
                self._last_fetch_ms.pop(key, None)
            else:
                self._cache.clear()
                self._last_fetch_ms.clear()

    def force_fetch(self, key: str) -> dict:
        """Force immediate fetch for a specific watcher key."""
        watchers = self._get_active_watchers()
        for watcher in watchers:
            if watcher.get('key') == key:
                with self._lock:
                    self._last_fetch_ms.pop(key, None)  # Clear last fetch time
                return self.tick()  # Will fetch immediately
        return {'success': False, 'error': f'No watcher found for key: {key}'}
