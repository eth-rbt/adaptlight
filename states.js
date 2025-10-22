// States - state definitions and their behavior functions
class State {
    constructor(name, description = '', onEnter = null) {
        this.name = name;
        this.description = description;
        this.onEnter = onEnter; // Function to execute when entering this state
    }

    /**
     * Execute the onEnter function for this state
     * @param {*} params - Parameters to pass to the onEnter function
     */
    enter(params = null) {
        if (this.onEnter && typeof this.onEnter === 'function') {
            console.log(`Entering state: ${this.name}`, params ? `with params: ${JSON.stringify(params)}` : '');

            // If params exist, pass them to the onEnter function
            if (params) {
                this.onEnter(params);
            } else {
                this.onEnter();
            }
        }
    }
}

/**
 * States class - manages a collection of states
 */
class States {
    constructor() {
        this.states = [];
    }

    /**
     * Add a state to the collection
     * @param {State} state - The state object to add
     */
    addState(state) {
        if (state instanceof State) {
            this.states.push(state);
            console.log(`State added to collection: ${state.name}`);
        } else {
            console.error('Can only add State objects');
        }
    }

    /**
     * Get all states as an array
     * @returns {Array} Array of State objects
     */
    getStates() {
        return this.states;
    }

    /**
     * Get a list of state names and descriptions
     * @returns {Array} Array of {name, description} objects
     */
    getStateList() {
        return this.states.map(state => ({
            name: state.name,
            description: state.description
        }));
    }

    /**
     * Get a state by name
     * @param {string} name - The state name
     * @returns {State|undefined} The state object or undefined
     */
    getStateByName(name) {
        return this.states.find(state => state.name === name);
    }

    /**
     * Clear all states
     */
    clearStates() {
        this.states = [];
        console.log('All states cleared');
    }

    /**
     * Get formatted state information for OpenAI API calls
     * @returns {string} Formatted string with state names and descriptions
     */
    getStatesForPrompt() {
        if (this.states.length === 0) {
            return 'No states registered.';
        }

        return this.states
            .map(state => `- ${state.name}: ${state.description}`)
            .join('\n');
    }
}

// ===== State Behavior Functions =====

/**
 * Turn light on (pure white light)
 */
function turnLightOn() {
    // Pure white
    updateColorDisplay(255, 255, 255);
}

/**
 * Turn light off
 */
function turnLightOff() {
    // Stop any running animations first
    window.stateMachine.stopInterval();

    // Turn off by setting color to black (0, 0, 0)
    updateColorDisplay(0, 0, 0);
}

/**
 * Update the visual color display (internal function, doesn't stop intervals)
 * @param {number} r - Red value (0-255)
 * @param {number} g - Green value (0-255)
 * @param {number} b - Blue value (0-255)
 */
function updateColorDisplay(r, g, b) {
    // Ensure values are within valid range (0-255)
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));

    // Check if this is the "off" state (all channels at 0)
    if (r === 0 && g === 0 && b === 0) {
        // Light off - clear all styles
        light.style.background = '';
        light.style.boxShadow = '';
    } else {
        // Light on - set the color with gradient for depth and glow effect
        const rgbColor = `rgb(${r}, ${g}, ${b})`;
        const rgbaGlow = `rgba(${r}, ${g}, ${b}, 0.8)`;
        const rgbaGlowOuter = `rgba(${r}, ${g}, ${b}, 0.5)`;

        light.style.background = `radial-gradient(circle, ${rgbColor} 0%, ${rgbColor} 100%)`;
        light.style.boxShadow = `
            0 0 40px ${rgbaGlow},
            0 0 80px ${rgbaGlowOuter},
            inset 0 0 20px rgba(255, 255, 255, 0.3)
        `;
    }

    // Store current color values in state machine data
    if (window.stateMachine) {
        window.stateMachine.setData('color_r', r);
        window.stateMachine.setData('color_g', g);
        window.stateMachine.setData('color_b', b);
    }

    // Send color to Arduino if connected
    if (window.arduinoController && window.arduinoController.isConnected) {
        window.arduinoController.sendColor(r, g, b);
    }
}

/**
 * Set light color based on RGB values
 * @param {Object|Array} params - RGB color parameters
 *   Can be: {r: value, g: value, b: value} where values can be numbers or expressions
 */
function setColor(params) {
    let r, g, b;
    window.stateMachine.stopInterval();

    // Get current color for expression context
    const currentR = window.stateMachine.getData('color_r') ?? 255;
    const currentG = window.stateMachine.getData('color_g') ?? 255;
    const currentB = window.stateMachine.getData('color_b') ?? 255;

    // Check if params is an object with r, g, b properties
    if (params && typeof params === 'object' && !Array.isArray(params)) {
        r = params.r ?? currentR;
        g = params.g ?? currentG;
        b = params.b ?? currentB;

        // Evaluate expressions if they are strings
        if (typeof r === 'string') {
            r = evaluateColorExpression(r, currentR, currentG, currentB, 'r');
        }
        if (typeof g === 'string') {
            g = evaluateColorExpression(g, currentR, currentG, currentB, 'g');
        }
        if (typeof b === 'string') {
            b = evaluateColorExpression(b, currentR, currentG, currentB, 'b');
        }
    } else if (Array.isArray(params)) {
        // If params is an array like [255, 0, 0]
        [r, g, b] = params;
    } else if (arguments.length === 3) {
        // Legacy support: setColor(r, g, b)
        r = arguments[0];
        g = arguments[1];
        b = arguments[2];
    }

    // Default to current values if still not provided
    r = r ?? currentR;
    g = g ?? currentG;
    b = b ?? currentB;

    // Update the display
    updateColorDisplay(r, g, b);
    console.log(`Light color set to: rgb(${r}, ${g}, ${b})`);
}

/**
 * Evaluate a color expression
 * @param {string} expr - The expression string
 * @param {number} currentR - Current red value
 * @param {number} currentG - Current green value
 * @param {number} currentB - Current blue value
 * @param {string} channel - Which channel this is for ('r', 'g', or 'b') - used for error fallback
 * @returns {number} The evaluated result
 */
function evaluateColorExpression(expr, currentR, currentG, currentB, channel = 'r') {
    // Whitelist of allowed Math functions
    const safeMath = {
        sin: Math.sin,
        cos: Math.cos,
        tan: Math.tan,
        abs: Math.abs,
        min: Math.min,
        max: Math.max,
        floor: Math.floor,
        ceil: Math.ceil,
        round: Math.round,
        sqrt: Math.sqrt,
        pow: Math.pow,
        PI: Math.PI,
        E: Math.E
    };

    // Random function
    const random = () => Math.floor(Math.random() * 256);

    // Current color object
    const current = {
        r: currentR,
        g: currentG,
        b: currentB
    };

    try {
        const fn = new Function(
            'current',
            'random',
            'safeMath',
            `
            const { sin, cos, tan, abs, min, max, floor, ceil, round, sqrt, pow, PI, E } = safeMath;
            const { r, g, b } = current;  // Also expose r, g, b directly for convenience
            return ${expr};
            `
        );
        return fn(current, random, safeMath);
    } catch (error) {
        console.error(`Color expression evaluation error for ${channel} channel ("${expr}"):`, error.message);
        // Return appropriate current value based on channel
        const fallback = channel === 'r' ? currentR : channel === 'g' ? currentG : currentB;
        console.log(`Using fallback value: ${fallback}`);
        return fallback;
    }
}

/**
 * Start an expression-based animation
 * @param {Object} params - Animation parameters with expressions
 *   Format: { r: "expression", g: "expression", b: "expression", speed: 50 }
 *   Available variables: r, g, b (current values), t (time in ms), frame (frame counter)
 *   Available functions: sin, cos, abs, min, max, floor, ceil, round, sqrt, pow, PI
 */
function startAnimation(params) {
    // Stop any existing animation
    window.stateMachine.stopInterval();

    if (!params || typeof params !== 'object') {
        console.error('Animation requires parameters object with r, g, b expressions and speed');
        return;
    }

    const speed = params.speed || 50;
    const rExpr = params.r || "r";
    const gExpr = params.g || "g";
    const bExpr = params.b || "b";

    console.log(`Starting expression-based animation:`, { r: rExpr, g: gExpr, b: bExpr, speed });

    // Create safe evaluation functions for each channel
    let rFn, gFn, bFn;
    try {
        rFn = createSafeExpressionFunction(rExpr);
        gFn = createSafeExpressionFunction(gExpr);
        bFn = createSafeExpressionFunction(bExpr);
    } catch (error) {
        console.error('Failed to create animation functions:', error);
        return;
    }

    // Animation state
    let frame = 0;
    const startTime = Date.now();

    // Get or initialize color state
    let r = window.stateMachine.getData('color_r') || 255;
    let g = window.stateMachine.getData('color_g') || 0;
    let b = window.stateMachine.getData('color_b') || 0;

    // Animation update function
    const animationFn = () => {
        const t = Date.now() - startTime;

        try {
            // Evaluate expressions with current context
            const newR = rFn({ r, g, b, t, frame });
            const newG = gFn({ r, g, b, t, frame });
            const newB = bFn({ r, g, b, t, frame });

            // Clamp values to 0-255
            r = Math.max(0, Math.min(255, Math.floor(newR)));
            g = Math.max(0, Math.min(255, Math.floor(newG)));
            b = Math.max(0, Math.min(255, Math.floor(newB)));

            // Update the display (don't use setColor as it would stop the interval!)
            updateColorDisplay(r, g, b);

            frame++;
        } catch (error) {
            console.error('Animation frame error:', error);
            window.stateMachine.stopInterval();
        }
    };

    // Start the interval
    window.stateMachine.startInterval(animationFn, speed);
}

/**
 * Create a safe expression evaluation function
 * @param {string} expr - The expression string
 * @returns {Function} A function that evaluates the expression with given context
 */
function createSafeExpressionFunction(expr) {
    // Whitelist of allowed Math functions
    const safeMath = {
        sin: Math.sin,
        cos: Math.cos,
        tan: Math.tan,
        abs: Math.abs,
        min: Math.min,
        max: Math.max,
        floor: Math.floor,
        ceil: Math.ceil,
        round: Math.round,
        sqrt: Math.sqrt,
        pow: Math.pow,
        PI: Math.PI,
        E: Math.E
    };

    // Create a function that evaluates the expression with controlled scope
    // Available variables: r, g, b, t, frame
    const fn = new Function(
        'context',
        'safeMath',
        `
        const { r, g, b, t, frame } = context;
        const { sin, cos, tan, abs, min, max, floor, ceil, round, sqrt, pow, PI, E } = safeMath;
        return ${expr};
        `
    );

    // Return wrapper that passes safeMath
    return (context) => fn(context, safeMath);
}

// ===== State Registration =====

/**
 * Register default states with the state machine
 */
function initializeDefaultStates() {
    const defaultStates = [
        new State('off', 'turn light off, no extra parameters', turnLightOff),
        new State('on', 'turn light on, no extra parameters', turnLightOn),
        new State('color', 'display a custom color. Parameters: {r: value, g: value, b: value} where values can be numbers or expressions. Expression variables: r, g, b (current RGB values), random() (returns 0-255). Functions: sin, cos, abs, min, max, floor, ceil, round, sqrt, pow, PI. Examples: {r: 255, g: 0, b: 0} or {r: "random()", g: "random()", b: "random()"} or {r: "r + 10", g: "g", b: "b"} or {r: "b", g: "r", b: "g"}', setColor),
        new State('animation', 'play an animated light pattern using expressions. Parameters: {r: "expr", g: "expr", b: "expr", speed: 50}. Variables: r,g,b (current RGB), t (time in ms), frame (frame count). Functions: sin, cos, abs, min, max, floor, ceil, round, sqrt, pow, PI. Example: {r: "abs(sin(t/1000)) * 255", g: "abs(cos(t/1000)) * 255", b: "128", speed: 50}', startAnimation)
    ];

    for (const state of defaultStates) {
        window.stateMachine.registerState(state.name, state.description, state.onEnter);
    }

    console.log('Default states initialized:', defaultStates.length);
}
