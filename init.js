// Initialization script for AdaptLight state machine

// Global state machine variables (legacy, keeping for backward compatibility)
window.state = 'idle';
window.stateData = {};
window.stateMachineInterval = null;

// Register states with their descriptions and onEnter functions
defaultStates = [
    new State('off', 'turn light off, no extra parameters', turnLightOff),
    new State('on', 'turn light on, no extra parameters', turnLightOn),
    new State('color', 'display a custom color base on RGB values, put in (r,g,b) as extra parameters', setColor)
]

for (const state of defaultStates) {
    window.stateMachine.registerState(state.name, state.description, state.onEnter);
}

// Add default transition rules (using new transition names from transitions.js)
window.stateMachine.addRule(new Rule('off', null, 'button_click', 'on', null));
window.stateMachine.addRule(new Rule('on', null, 'button_click', 'off', null));

// Initialize: set initial state to trigger onEnter function
window.addEventListener('DOMContentLoaded', () => {
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