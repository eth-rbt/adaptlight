// State functions - functions to execute when entering different states

// Helper functions for controlling the light
function turnLightOn() {
    isLightOn = true;
    light.classList.add('on');
}

function turnLightOff() {
    isLightOn = false;
    light.classList.remove('on');
    light.style.background = ''; // Reset background
    light.style.boxShadow = ''; // Reset box shadow
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

    console.log(`Light color set to: rgb(${r}, ${g}, ${b})`);
}
