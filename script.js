// Get references to DOM elements
const light = document.getElementById('light');
const toggleButton = document.getElementById('button');
const textBox = document.getElementById('textBox');
const sendButton = document.getElementById('sendButton');
const rulesToggle = document.getElementById('rulesToggle');
const rulesContent = document.getElementById('rulesContent');
const rulesList = document.getElementById('rulesList');
let isLightOn = false;

// Toggle rules panel
rulesToggle.addEventListener('click', () => {
    rulesContent.classList.toggle('hidden');
    const toggleIcon = rulesToggle.querySelector('.toggle-icon');
    toggleIcon.classList.toggle('collapsed');
});

// Function to update the rules display
function updateRulesDisplay() {
    const rules = window.stateMachine.getRules();

    if (rules.length === 0) {
        rulesList.innerHTML = '<div class="no-rules">No rules yet</div>';
        return;
    }

    let html = '';
    rules.forEach((rule, index) => {
        const state1Param = rule.state1Param ?
            `<span class="rule-param">(${JSON.stringify(rule.state1Param)})</span>` : '';
        const state2Param = rule.state2Param ?
            `<span class="rule-param">(${JSON.stringify(rule.state2Param)})</span>` : '';

        html += `
            <div class="rule-item">
                <span class="rule-state">${rule.state1}</span>${state1Param}
                →
                <span class="rule-transition">${rule.transition}</span>
                →
                <span class="rule-state">${rule.state2}</span>${state2Param}
            </div>
        `;
    });

    rulesList.innerHTML = html;
}

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

            // Update the rules display
            updateRulesDisplay();

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
