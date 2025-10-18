// Initialization script for AdaptLight state machine

// Global state machine variables (legacy, keeping for backward compatibility)
window.state = 'idle';
window.stateData = {};
window.stateMachineInterval = null;

// Initialize: set initial state and attach event listeners
window.addEventListener('DOMContentLoaded', () => {
    // Initialize default parameter generators, states, and rules
    initializeDefaultParamGenerators();
    initializeDefaultStates();
    initializeDefaultRules();

    // Set the initial state (this will call the onEnter function)
    window.stateMachine.setState('off');
    console.log('State machine initialized. Current state:', window.stateMachine.getState());

    // Attach transitions to the button
    const button = document.getElementById('button');
    if (button && window.transitions) {
        window.transitions.attachToElement(button);
        console.log('Transitions attached to button');
    }

    // Update the rules display with default rules
    if (typeof updateRulesDisplay === 'function') {
        updateRulesDisplay();
    }
});