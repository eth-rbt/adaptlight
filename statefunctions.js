// State functions - functions to execute when entering different states

// Helper functions for controlling the light
function turnLightOn() {
    isLightOn = true;
    light.classList.add('on');
}

function turnLightOff() {
    isLightOn = false;
    light.classList.remove('on');
    light.style.backgroundColor = ''; // Reset background color
}

// Set light color based on RGB values
function setColor(r, g, b) {
    // Get RGB values from state machine data if not provided
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

    // Set the color
    light.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
    console.log(`Light color set to: rgb(${r}, ${g}, ${b})`);
}
