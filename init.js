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