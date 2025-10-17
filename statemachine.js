/**
 * State class - represents a single state with a name, description, and onEnter function
 */
class State {
    constructor(name, description = '', onEnter = null) {
        this.name = name;
        this.description = description;
        this.onEnter = onEnter; // Function to execute when entering this state
    }

    /**
     * Execute the onEnter function for this state
     */
    enter() {
        if (this.onEnter && typeof this.onEnter === 'function') {
            console.log(`Entering state: ${this.name}`);
            this.onEnter();
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

/**
 * StateMachine class for managing state logic
 * Stores rules as [state1, action, state2] arrays
 * Where state1 is current state, action is the trigger, state2 is next state
 */
class StateMachine {
    constructor() {
        this.rules = [];
        this.currentState = 'off'; // Current state (string name)
        this.states = new States(); // States collection
        this.stateData = {};
        this.interval = null;

        // Add default rules
        this.addRule(['off', 'button_press', 'on']); // from off, button press goes to on
        this.addRule(['on', 'button_press', 'off']); // from on, button press goes to off
    }

    /**
     * Register a state with its description and onEnter function
     * @param {string} name - The name of the state
     * @param {string} description - Description of what this state does
     * @param {Function} onEnter - Function to execute when entering this state
     */
    registerState(name, description = '', onEnter = null) {
        const state = new State(name, description, onEnter);
        this.states.addState(state);
        console.log(`State registered: ${name}`);
        return state;
    }

    /**
     * Get a state by name
     * @param {string} name - The state name
     * @returns {State} The state object, or undefined if not found
     */
    getStateObject(name) {
        return this.states.getStateByName(name);
    }

    /**
     * Get a list of all state names and descriptions
     * @returns {Array} Array of {name, description} objects
     */
    getStateList() {
        return this.states.getStateList();
    }

    /**
     * Add a new rule to the state machine
     * @param {Array} rule - [state1, action, state2]
     */
    addRule(rule) {
        if (Array.isArray(rule) && rule.length === 3) {
            this.rules.push({
                state1: rule[0],
                action: rule[1],
                state2: rule[2],
                timestamp: new Date().toISOString()
            });
            console.log('Rule added:', rule);
        } else {
            console.error('Invalid rule format. Expected [state1, action, state2]');
        }
    }

    /**
     * Get all rules
     * @returns {Array} All stored rules
     */
    getRules() {
        return this.rules;
    }

    /**
     * Clear all rules
     */
    clearRules() {
        this.rules = [];
        console.log('All rules cleared');
    }

    /**
     * Remove a specific rule by index
     * @param {number} index - Index of the rule to remove
     */
    removeRule(index) {
        if (index >= 0 && index < this.rules.length) {
            const removed = this.rules.splice(index, 1);
            console.log('Rule removed:', removed[0]);
        }
    }

    /**
     * Set the current state
     * @param {string} stateName - The new state name
     */
    setState(stateName) {
        this.currentState = stateName;
        console.log('State changed to:', stateName);

        // Execute the onEnter function for this state if it exists
        const stateObject = this.getStateObject(stateName);
        if (stateObject) {
            stateObject.enter();
        }
    }

    /**
     * Execute a transition based on an action
     * @param {string} action - The action to execute
     * @returns {boolean} True if transition was executed, false otherwise
     */
    executeTransition(action) {
        const matchingRule = this.rules.find(rule => {
            return rule.state1 === this.currentState && rule.action === action;
        });

        if (matchingRule) {
            console.log(`Transition: state ${matchingRule.state1} --[${action}]--> state ${matchingRule.state2}`);
            this.setState(matchingRule.state2);
            return true;
        } else {
            console.log(`No transition found for action "${action}" in state ${this.currentState}`);
            return false;
        }
    }

    /**
     * Get the current state
     * @returns {string} Current state
     */
    getState() {
        return this.currentState;
    }

    /**
     * Set state data
     * @param {string} key - Data key
     * @param {*} value - Data value
     */
    setData(key, value) {
        this.stateData[key] = value;
    }

    /**
     * Get state data
     * @param {string} key - Data key
     * @returns {*} Data value
     */
    getData(key) {
        return this.stateData[key];
    }

    /**
     * Clear all state data
     */
    clearData() {
        this.stateData = {};
    }

    /**
     * Stop the current interval if running
     */
    stopInterval() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
            console.log('State machine interval stopped');
        }
    }

    /**
     * Start an interval for state machine execution
     * @param {Function} callback - Function to execute on each interval
     * @param {number} intervalMs - Interval in milliseconds
     */
    startInterval(callback, intervalMs = 100) {
        this.stopInterval();
        this.interval = setInterval(callback, intervalMs);
        console.log(`State machine interval started (${intervalMs}ms)`);
    }

    /**
     * Reset the state machine to initial state
     */
    reset() {
        this.stopInterval();
        this.currentState = 'off';
        this.stateData = {};
        console.log('State machine reset');
    }

    /**
     * Get a summary of the state machine
     * @returns {Object} Summary object
     */
    getSummary() {
        return {
            rulesCount: this.rules.length,
            currentState: this.currentState,
            stateData: { ...this.stateData },
            isRunning: this.interval !== null
        };
    }
}

// Create global instance
window.stateMachine = new StateMachine();
