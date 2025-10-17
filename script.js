// Get references to DOM elements
const light = document.getElementById('light');
const toggleButton = document.getElementById('button');
const textBox = document.getElementById('textBox');
const sendButton = document.getElementById('sendButton');
const runButton = document.getElementById('runButton');

// Track light state
let isLightOn = false;

// Global state machine variables
window.state = 'idle';
window.stateData = {};
window.stateMachineInterval = null;

// Helper functions for LLM-generated code
function turnLightOn() {
    isLightOn = true;
    light.classList.add('on');
}

function turnLightOff() {
    isLightOn = false;
    light.classList.remove('on');
}

function toggleLight() {
    isLightOn = !isLightOn;
    if (isLightOn) {
        light.classList.add('on');
    } else {
        light.classList.remove('on');
    }
}

function blinkLight(times, interval = 500) {
    let count = 0;
    const blinkInterval = setInterval(() => {
        toggleLight();
        count++;
        if (count >= times * 2) {
            clearInterval(blinkInterval);
        }
    }, interval);
}

// Toggle light on button click
button.addEventListener('click', () => {
    toggleLight();
});

// Send button click handler
sendButton.addEventListener('click', async () => {
    const userInput = textBox.value.trim();
    if (!userInput) return;

    try {
        // Parse the text into [activating condition, action, post condition]
        const response = await fetch('http://localhost:3000/parse-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ userInput })
        });

        const data = await response.json();

        if (data.success) {
            console.log('Parsed array:', data.parsedArray);

            // Add the rule to the global state machine
            window.stateMachine.addRule(data.parsedArray);

            console.log('Current rules:', window.stateMachine.getRules());

            // Clear the text box after successful parse
            textBox.value = '';
        }
    } catch (error) {
        console.error('Error:', error);
    }
});

// Allow Enter key to send
textBox.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

// Run button click handler - display state machine summary
runButton.addEventListener('click', () => {
    const summary = window.stateMachine.getSummary();
    console.log('=== State Machine Summary ===');
    console.log('Rules:', window.stateMachine.getRules());
    console.log('Current State:', summary.currentState);
    console.log('State Data:', summary.stateData);
    console.log('Is Running:', summary.isRunning);
    console.log('============================');

    // Display an alert with the summary
    alert(`State Machine Summary:\n\n` +
          `Rules: ${summary.rulesCount}\n` +
          `Current State: ${summary.currentState}\n` +
          `Is Running: ${summary.isRunning}`);
});
