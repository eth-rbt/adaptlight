/**
 * State class - represents a single state with a name, description, and onEnter function
 */

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
     * If a rule with the same state1 and transition exists, it will be replaced
     * @param {Array|Object|Rule} rule - Can be:
     *   - Legacy array: [state1, action, state2]
     *   - Object: {state1, state1Param, transition, state2, state2Param}
     *   - Rule instance
     */
    addRule(rule) {
        let ruleObj;

        if (rule instanceof Rule) {
            // Already a Rule instance
            ruleObj = rule;
        } else if (Array.isArray(rule) && rule.length === 3) {
            // Legacy format: [state1, action, state2]
            ruleObj = new Rule(rule[0], null, rule[1], rule[2], null);
        } else if (typeof rule === 'object' && rule.state1 && rule.transition && rule.state2) {
            // New object format
            ruleObj = new Rule(
                rule.state1,
                rule.state1Param,
                rule.transition,
                rule.state2,
                rule.state2Param
            );
        } else {
            console.error('Invalid rule format. Expected [state1, action, state2] or {state1, state1Param, transition, state2, state2Param}');
            return;
        }

        // Check if a rule with the same state1 and transition already exists
        const existingIndex = this.rules.findIndex(r =>
            r.state1 === ruleObj.state1 && r.transition === ruleObj.transition
        );

        if (existingIndex !== -1) {
            // Replace the existing rule
            this.rules[existingIndex] = ruleObj;
            console.log('Rule replaced:', ruleObj.toObject());
        } else {
            // Add new rule
            this.rules.push(ruleObj);
            console.log('Rule added:', ruleObj.toObject());
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
     * Set the current state with optional parameters
     * @param {string} stateName - The new state name
     * @param {*} params - Optional parameters to pass to the state's onEnter function
     *                     Can be a parameter generator name (string) or actual parameter value
     */
    setState(stateName, params = null) {
        this.currentState = stateName;
        console.log('State changed to:', stateName);

        // Check if params is a parameter generator name
        let actualParams = params;
        if (typeof params === 'string' && window.paramGenerators) {
            const generator = window.paramGenerators.getGenerator(params);
            if (generator) {
                actualParams = generator.generate();
                console.log(`Parameter generator "${params}" executed, result:`, actualParams);
            }
        }

        // Execute the onEnter function for this state if it exists
        const stateObject = this.getStateObject(stateName);
        if (stateObject) {
            stateObject.enter(actualParams);
        }
    }

    /**
     * Execute a transition based on an action
     * @param {string} action - The action to execute
     * @returns {boolean} True if transition was executed, false otherwise
     */
    executeTransition(action) {
        const matchingRule = this.rules.find(rule => {
            return rule.matches(this.currentState, action);
        });

        if (matchingRule) {
            console.log(`Transition: state ${matchingRule.state1} --[${matchingRule.transition}]--> state ${matchingRule.state2}`);

            // Pass state2Param to the setState function
            this.setState(matchingRule.state2, matchingRule.state2Param);
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
