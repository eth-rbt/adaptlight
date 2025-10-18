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
 * Turn light on (yellow/white light)
 */
function turnLightOn() {
    isLightOn = true;
    light.classList.add('on');
}

/**
 * Turn light off
 */
function turnLightOff() {
    isLightOn = false;
    light.classList.remove('on');
    light.style.background = ''; // Reset background
    light.style.boxShadow = ''; // Reset box shadow
}

/**
 * Set light color based on RGB values
 * @param {Object|Array} params - RGB color parameters
 */
function setColor(params) {
    let r, g, b;

    // Check if params is an object with r, g, b properties
    if (params && typeof params === 'object') {
        r = params.r ?? params[0];
        g = params.g ?? params[1];
        b = params.b ?? params[2];
    } else if (Array.isArray(params)) {
        // If params is an array like [255, 0, 0]
        [r, g, b] = params;
    } else if (arguments.length === 3) {
        // Legacy support: setColor(r, g, b)
        r = arguments[0];
        g = arguments[1];
        b = arguments[2];
    }

    // Get RGB values from state machine data if still not provided
    r = r ?? window.stateMachine.getData('color_r') ?? 255;
    g = g ?? window.stateMachine.getData('color_g') ?? 255;
    b = b ?? window.stateMachine.getData('color_b') ?? 255;

    // Ensure values are within valid range (0-255)
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));

    // Turn the light on if it's not already
    isLightOn = true;
    light.classList.add('on');

    // Set the color with gradient for depth and glow effect
    const rgbColor = `rgb(${r}, ${g}, ${b})`;
    const rgbaGlow = `rgba(${r}, ${g}, ${b}, 0.8)`;
    const rgbaGlowOuter = `rgba(${r}, ${g}, ${b}, 0.5)`;

    light.style.background = `radial-gradient(circle, ${rgbColor} 0%, ${rgbColor} 100%)`;
    light.style.boxShadow = `
        0 0 40px ${rgbaGlow},
        0 0 80px ${rgbaGlowOuter},
        inset 0 0 20px rgba(255, 255, 255, 0.3)
    `;

    // Store current color values in state machine data for parameter generators
    if (window.stateMachine) {
        window.stateMachine.setData('color_r', r);
        window.stateMachine.setData('color_g', g);
        window.stateMachine.setData('color_b', b);
    }

    console.log(`Light color set to: rgb(${r}, ${g}, ${b})`);
}

// ===== State Registration =====

/**
 * Register default states with the state machine
 */
function initializeDefaultStates() {
    const defaultStates = [
        new State('off', 'turn light off, no extra parameters', turnLightOff),
        new State('on', 'turn light on, no extra parameters', turnLightOn),
        new State('color', 'display a custom color base on RGB values, put in (r,g,b) as extra parameters', setColor)
    ];

    for (const state of defaultStates) {
        window.stateMachine.registerState(state.name, state.description, state.onEnter);
    }

    console.log('Default states initialized:', defaultStates.length);
}
