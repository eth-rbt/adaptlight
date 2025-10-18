// Default rules for AdaptLight state machine
class Rule {
    constructor(state1, state1Param, transition, state2, state2Param) {
        this.state1 = state1;
        this.state1Param = state1Param || null;
        this.transition = transition;
        this.state2 = state2;
        this.state2Param = state2Param || null;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Check if this rule matches the current state and action
     */
    matches(currentState, action) {
        return this.state1 === currentState && this.transition === action;
    }

    /**
     * Convert to a simple object representation
     */
    toObject() {
        return {
            state1: this.state1,
            state1Param: this.state1Param,
            transition: this.transition,
            state2: this.state2,
            state2Param: this.state2Param,
            timestamp: this.timestamp
        };
    }
}

/**
 * Initialize default rules for the state machine
 * These rules define the basic button interactions
 */
function initializeDefaultRules() {
    // Add default transition rules (using transition names from transitions.js)
    window.stateMachine.addRule(new Rule('off', null, 'button_click', 'on', null));
    window.stateMachine.addRule(new Rule('on', null, 'button_click', 'off', null));

    console.log('Default rules initialized');
}
