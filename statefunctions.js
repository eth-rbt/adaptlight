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

    // Set the color
    light.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
    console.log(`Light color set to: rgb(${r}, ${g}, ${b})`);
}
