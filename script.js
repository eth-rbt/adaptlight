// Get references to DOM elements
const light = document.getElementById('light');
const toggleButton = document.getElementById('button');
const textBox = document.getElementById('textBox');
const sendButton = document.getElementById('sendButton');
const runButton = document.getElementById('runButton');
let isLightOn = false;

// Toggle light on button click - now integrated with state machine
button.addEventListener('click', () => {
    // Execute the transition based on button_press action
    // The state's onEnter function will automatically be called
    window.stateMachine.executeTransition('button_press');
});

// Send button click handler
sendButton.addEventListener('click', async () => {
    const userInput = textBox.value.trim();
    if (!userInput) return;

    try {
        // Get available states for the prompt
        const availableStates = window.stateMachine.states.getStatesForPrompt();

        // Parse the text into [activating condition, action, post condition]
        const response = await fetch('http://localhost:3000/parse-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ userInput, availableStates })
        });

        const data = await response.json();

        if (data.success) {
            console.log('Parsed rules:', data.parsedRules);

            // Add all rules to the global state machine
            for (const rule of data.parsedRules) {
                window.stateMachine.addRule(rule);
            }

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
    const stateList = window.stateMachine.getStateList();

    console.log('=== State Machine Summary ===');
    console.log('Rules:', window.stateMachine.getRules());
    console.log('Current State:', summary.currentState);
    console.log('State Data:', summary.stateData);
    console.log('Is Running:', summary.isRunning);
    console.log('States:', stateList);
    console.log('============================');

    // Build state list string
    let stateListStr = stateList.map(s => `  ${s.name}: ${s.description}`).join('\n');

    // Display an alert with the summary
    alert(`State Machine Summary:\n\n` +
          `Rules: ${summary.rulesCount}\n` +
          `Current State: ${summary.currentState}\n` +
          `Is Running: ${summary.isRunning}\n\n` +
          `States:\n${stateListStr}`);
});
