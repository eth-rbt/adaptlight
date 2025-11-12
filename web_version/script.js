// Get references to DOM elements
const light = document.getElementById('light');
const toggleButton = document.getElementById('button');
const textBox = document.getElementById('textBox');
const sendButton = document.getElementById('sendButton');
const resetButton = document.getElementById('resetButton');
const rulesToggle = document.getElementById('rulesToggle');
const rulesContent = document.getElementById('rulesContent');
const rulesList = document.getElementById('rulesList');
const arduinoConnect = document.getElementById('arduinoConnect');
const arduinoStatus = document.getElementById('arduinoStatus');

// Conversation history
let conversationHistory = [];

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

        const condition = rule.condition ?
            `<div class="rule-condition">if: ${rule.condition}</div>` : '';
        const action = rule.action ?
            `<div class="rule-action">do: ${rule.action}</div>` : '';

        html += `
            <div class="rule-item">
                <span class="rule-state">${rule.state1}</span>${state1Param}
                →
                <span class="rule-transition">${rule.transition}</span>
                →
                <span class="rule-state">${rule.state2}</span>${state2Param}
                ${condition}
                ${action}
            </div>
        `;
    });

    rulesList.innerHTML = html;
}

/**
 * Execute a tool call from the AI
 * @param {string} toolName - Name of the tool to execute
 * @param {Object} args - Arguments for the tool
 */
function executeTool(toolName, args) {
    console.log(`%c🔧 Action: ${toolName}`, 'color: #4CAF50; font-weight: bold');
    console.log('Arguments:', args);

    switch (toolName) {
        case 'append_rules':
            // Add new rules to the state machine
            if (args.rules && Array.isArray(args.rules)) {
                console.log(`%c➕ Adding ${args.rules.length} rule(s):`, 'color: #2196F3; font-weight: bold');
                for (const rule of args.rules) {
                    window.stateMachine.addRule(rule);
                    console.log(`  → ${rule.state1} --[${rule.transition}]--> ${rule.state2}`);
                }
            }
            break;

        case 'delete_rules':
            // Delete rules based on criteria
            const rulesToDelete = [];
            const allRules = window.stateMachine.getRules();

            if (args.delete_all) {
                // Delete all rules
                const count = allRules.length;
                window.stateMachine.clearRules();
                console.log(`%c🗑️ Deleted all ${count} rule(s)`, 'color: #f44336; font-weight: bold');
            } else if (args.indices && Array.isArray(args.indices)) {
                // Delete by specific indices (sort descending to avoid index shifting)
                console.log(`%c🗑️ Deleting rules at indices: ${args.indices.join(', ')}`, 'color: #f44336; font-weight: bold');
                const sortedIndices = args.indices.sort((a, b) => b - a);
                for (const index of sortedIndices) {
                    const rule = allRules[index];
                    if (rule) {
                        console.log(`  → [${index}] ${rule.state1} --[${rule.transition}]--> ${rule.state2}`);
                    }
                    window.stateMachine.removeRule(index);
                }
            } else {
                // Delete by criteria (state1, transition, state2)
                const criteria = [];
                if (args.state1) criteria.push(`state1=${args.state1}`);
                if (args.transition) criteria.push(`transition=${args.transition}`);
                if (args.state2) criteria.push(`state2=${args.state2}`);

                console.log(`%c🗑️ Deleting rules matching: ${criteria.join(', ')}`, 'color: #f44336; font-weight: bold');

                for (let i = allRules.length - 1; i >= 0; i--) {
                    const rule = allRules[i];
                    let shouldDelete = false;

                    if (args.state1 && rule.state1 === args.state1) {
                        shouldDelete = true;
                    }
                    if (args.transition && rule.transition === args.transition) {
                        shouldDelete = true;
                    }
                    if (args.state2 && rule.state2 === args.state2) {
                        shouldDelete = true;
                    }

                    if (shouldDelete) {
                        rulesToDelete.push(i);
                        console.log(`  → [${i}] ${rule.state1} --[${rule.transition}]--> ${rule.state2}`);
                    }
                }

                // Delete the matching rules
                for (const index of rulesToDelete) {
                    window.stateMachine.removeRule(index);
                }
            }
            break;

        case 'set_state':
            // Change the current state
            if (args.state) {
                const paramsStr = args.params ? JSON.stringify(args.params) : 'none';
                console.log(`%c🔄 Changing state to: ${args.state}`, 'color: #FF9800; font-weight: bold');
                console.log(`  → Parameters: ${paramsStr}`);
                window.stateMachine.setState(args.state, args.params || null);
            }
            break;

        case 'manage_variables':
            // Manage global variables
            if (args.action === 'set' && args.variables) {
                // Set/update variables
                console.log(`%c💾 Setting ${Object.keys(args.variables).length} variable(s):`, 'color: #9C27B0; font-weight: bold');
                for (const [key, value] of Object.entries(args.variables)) {
                    window.stateMachine.setData(key, value);
                    console.log(`  → ${key} = ${JSON.stringify(value)}`);
                }
            } else if (args.action === 'delete' && args.keys) {
                // Delete specific variables
                console.log(`%c💾 Deleting ${args.keys.length} variable(s):`, 'color: #9C27B0; font-weight: bold');
                for (const key of args.keys) {
                    console.log(`  → ${key}`);
                    window.stateMachine.setData(key, undefined);
                }
            } else if (args.action === 'clear_all') {
                // Clear all variables
                console.log(`%c💾 Clearing all variables`, 'color: #9C27B0; font-weight: bold');
                window.stateMachine.clearData();
            }
            break;

        default:
            console.warn(`❌ Unknown tool: ${toolName}`);
    }
}

// Send button click handler
sendButton.addEventListener('click', async () => {
    const userInput = textBox.value.trim();
    if (!userInput) return;

    // Show loading animation
    let dotCount = 0;
    textBox.value = 'Processing';
    textBox.disabled = true;
    sendButton.disabled = true;

    const loadingInterval = setInterval(() => {
        dotCount = (dotCount + 1) % 4;
        textBox.value = 'Processing' + '.'.repeat(dotCount);
    }, 300);

    // Send loading command to Arduino
    if (window.arduinoController && window.arduinoController.isConnected) {
        await window.arduinoController.sendLoading();
    }

    try {
        // Gather current system state for the prompt
        const availableStates = window.stateMachine.states.getStatesForPrompt();
        const availableTransitions = window.transitions.getAvailableTransitions();
        const currentRules = window.stateMachine.getRules().map(rule => rule.toObject());
        const currentState = window.stateMachine.getState();
        const globalVariables = window.stateMachine.stateData;

        // Parse the text into rules
        const response = await fetch('http://localhost:3000/parse-text', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                userInput,
                conversationHistory,
                availableStates,
                availableTransitions,
                currentRules,
                currentState,
                globalVariables
            })
        });

        const data = await response.json();

        if (data.success) {
            console.log('%c═══════════════════════════════════════', 'color: #666');
            console.log('%c👤 User:', 'color: #9E9E9E; font-weight: bold');
            console.log(`%c"${userInput}"`, 'color: #9E9E9E');

            // Log AI message if present
            if (data.message) {
                console.log('%c\n💬 AI Response:', 'color: #00BCD4; font-weight: bold; font-size: 14px');
                console.log(`%c${data.message}`, 'color: #00BCD4; font-style: italic');
            }

            // Execute tool calls if present
            if (data.toolCalls && data.toolCalls.length > 0) {
                console.log(`%c\n⚡ Executing ${data.toolCalls.length} action(s):`, 'color: #4CAF50; font-weight: bold; font-size: 14px');

                // Execute each tool call
                for (let i = 0; i < data.toolCalls.length; i++) {
                    const toolCall = data.toolCalls[i];
                    console.log(`\n[${i + 1}/${data.toolCalls.length}]`);
                    executeTool(toolCall.name, toolCall.arguments);
                }
            }

            console.log('%c═══════════════════════════════════════\n', 'color: #666');

            // Update the rules display
            updateRulesDisplay();

            // Add to conversation history
            conversationHistory.push(userInput);
            // Keep only last 10 messages to avoid token bloat
            if (conversationHistory.length > 10) {
                conversationHistory.shift();
            }

            // Clear the text box after successful parse
            textBox.value = '';
        }
    } catch (error) {
        console.error('Error:', error);
        textBox.value = '';
    } finally {
        // Send finished command to Arduino
        if (window.arduinoController && window.arduinoController.isConnected) {
            await window.arduinoController.sendFinished();
        }

        // Clear loading animation and re-enable inputs
        clearInterval(loadingInterval);
        textBox.disabled = false;
        sendButton.disabled = false;
        textBox.focus();
    }
});

// Allow Enter key to send
textBox.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendButton.click();
    }
});

// Film mode toggle (press 'f' key)
document.addEventListener('keydown', (e) => {
    // Only toggle if not focused on an input
    if (e.key === 'f' && document.activeElement !== textBox) {
        document.body.classList.toggle('film-mode');
        console.log('Film mode:', document.body.classList.contains('film-mode') ? 'ON' : 'OFF');
    }
});

// Reset button click handler
resetButton.addEventListener('click', async () => {
    try {
        // Clear rules on the server
        const response = await fetch('http://localhost:3000/reset-rules', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const data = await response.json();

        if (data.success) {
            // Clear the local state machine rules
            window.stateMachine.clearRules();

            // Restore default rules
            initializeDefaultRules();

            // Set state back to 'off'
            window.stateMachine.setState('off');

            // Clear conversation history
            conversationHistory = [];

            // Update the rules display
            updateRulesDisplay();

            console.log('Rules reset to default');
        }
    } catch (error) {
        console.error('Error resetting rules:', error);
    }
});

// Arduino connect button handler
arduinoConnect.addEventListener('click', async () => {
    if (window.arduinoController.isConnected) {
        // Disconnect
        await window.arduinoController.disconnect();
        arduinoConnect.textContent = 'Connect Arduino';
        arduinoStatus.textContent = 'Not connected';
        arduinoStatus.style.color = '#999';
    } else {
        // Connect
        try {
            await window.arduinoController.connect();
            arduinoConnect.textContent = 'Disconnect Arduino';
            arduinoStatus.textContent = 'Connected';
            arduinoStatus.style.color = '#4CAF50';
        } catch (error) {
            arduinoStatus.textContent = 'Connection failed';
            arduinoStatus.style.color = '#f44336';
            console.error('Failed to connect to Arduino:', error);
        }
    }
});
