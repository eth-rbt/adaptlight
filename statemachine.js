/**
 * StateMachine class for managing state logic
 * Stores rules as [activating condition, action, post condition] arrays
 */
class StateMachine {
    constructor() {
        this.rules = [];
        this.currentState = 'idle';
        this.stateData = {};
        this.interval = null;
    }

    /**
     * Add a new rule to the state machine
     * @param {Array} rule - [activating condition, action, post condition]
     */
    addRule(rule) {
        if (Array.isArray(rule) && rule.length === 3) {
            this.rules.push({
                activatingCondition: rule[0],
                action: rule[1],
                postCondition: rule[2],
                timestamp: new Date().toISOString()
            });
            console.log('Rule added:', rule);
        } else {
            console.error('Invalid rule format. Expected [activatingCondition, action, postCondition]');
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
     * @param {string} state - The new state
     */
    setState(state) {
        this.currentState = state;
        console.log('State changed to:', state);
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
        this.currentState = 'idle';
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
