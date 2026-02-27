"""
Compact agent prompt for GPT Realtime API.

Kept under ~1500 tokens to fit within the Realtime API's 16K instruction+tools limit.
Covers render signature, return format, available functions, and critical rules.
"""

from .agent_prompt_with_examples import get_vision_docs


def get_realtime_system_prompt(
    system_state: str = "",
    representation_version: str = "stdlib",
    vision_config: dict = None,
    control_mode: str = "default",
    num_pixels: int = 0,
) -> str:
    """
    Get a compact system prompt for the GPT Realtime session.

    Args:
        system_state: Current system state string
        representation_version: State representation version
        vision_config: Vision configuration
        control_mode: LED control mode ('default', 'cobbled_only', 'all')
        num_pixels: Ring LED pixel count (for 'all' mode)

    Returns:
        Compact system prompt string
    """
    vision_docs = get_vision_docs(vision_config)

    if control_mode == "all":
        render_docs = _get_render_docs_all(num_pixels)
    else:
        render_docs = _get_render_docs_default(representation_version)

    return f"""You are a smart light controller. Users speak voice commands. Use tools to configure the lamp, then call done().

{render_docs}

## TOOLS SUMMARY
- createState(name, code, description?) — create a light state
- deleteState(name) — remove a state
- setState(name) — switch to a state
- appendRules(rules) — add transition rules (from, on, to, condition?, action?, priority?, trigger_config?)
- deleteRules(indices?, transition?, from_state?, to_state?, all?) — delete rules
- getStates() — list states
- getRules() — list rules
- setVariable(key, value) / getVariables() — manage variables
- fetchAPI(api, params) — call preset API (weather, stock, crypto, sun, time, etc.)
- remember(key, value) / recall(key) — persistent memory
- done(message) — MUST call when finished

{vision_docs}

## RULES
1. ALWAYS call done() with a short message when finished.
2. Do NOT add rules unless user asks for button/trigger behavior (toggle, click, hold, timer, schedule).
3. Create states before setting them.
4. Keep responses concise — they are spoken aloud via TTS.

## STATE
{system_state}"""


def _get_render_docs_default(representation_version: str) -> str:
    """Render docs for default/cobbled_only mode."""
    return """## RENDER FORMAT
createState code: `def render(prev, t)` returns `((r,g,b), next_ms)`
- prev: previous (r,g,b), t: seconds elapsed
- next_ms > 0: animation, None: static, 0: state_complete event
- Helpers: hsv(h,s,v), rgb(r,g,b), lerp_color, sin, cos, clamp, lerp, random(), getData/setData
- Example: `def render(prev, t): return hsv(t*0.1%1, 1, 1), 30`"""


def _get_render_docs_all(num_pixels: int) -> str:
    """Render docs for 'all' LED mode (cobbled + ring)."""
    return f"""## RENDER FORMAT
createState code: `def render(prev, t)` returns a dict:
  {{"cobbled": (r,g,b), "ring": [(r,g,b)]*NUM_PIXELS, "next_ms": N}}
- prev: previous (r,g,b) of COB, t: seconds elapsed
- NUM_PIXELS = {num_pixels}
- next_ms > 0: animation, None: static, 0: state_complete event
- Helpers: hsv(h,s,v), rgb(r,g,b), lerp_color, sin, cos, clamp, lerp, random(), getData/setData
- Default: ring all black unless user asks for ring/circle/countdown behavior
- Example: `def render(prev, t): return {{"cobbled": (255,0,0), "ring": [(0,0,0)]*NUM_PIXELS, "next_ms": None}}`"""
