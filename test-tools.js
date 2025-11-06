// Test script for the 4 tool calls
const fetch = require('node-fetch');

async function testTools() {
    const baseUrl = 'http://localhost:3000/parse-text';

    // Mock initial state
    const mockState = {
        availableStates: `- off: turn light off
- on: turn light on
- color: display a custom color
- animation: play an animated pattern`,
        availableTransitions: [
            { name: 'button_click', description: 'Single click' },
            { name: 'button_double_click', description: 'Double click' },
            { name: 'button_hold', description: 'Hold button' }
        ],
        currentRules: [],
        currentState: 'off',
        globalVariables: {},
        conversationHistory: []
    };

    console.log('=== Test 1: append_rules ===');
    try {
        const response1 = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...mockState,
                userInput: 'When I click the button, turn the light red'
            })
        });
        const result1 = await response1.json();
        console.log('Result:', JSON.stringify(result1, null, 2));
    } catch (error) {
        console.error('Error:', error.message);
    }

    console.log('\n=== Test 2: set_state ===');
    try {
        const response2 = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...mockState,
                userInput: 'Turn the light blue right now'
            })
        });
        const result2 = await response2.json();
        console.log('Result:', JSON.stringify(result2, null, 2));
    } catch (error) {
        console.error('Error:', error.message);
    }

    console.log('\n=== Test 3: manage_variables ===');
    try {
        const response3 = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...mockState,
                userInput: 'Set a counter variable to 5'
            })
        });
        const result3 = await response3.json();
        console.log('Result:', JSON.stringify(result3, null, 2));
    } catch (error) {
        console.error('Error:', error.message);
    }

    console.log('\n=== Test 4: delete_rules ===');
    const mockStateWithRules = {
        ...mockState,
        currentRules: [
            { state1: 'off', transition: 'button_click', state2: 'on' },
            { state1: 'on', transition: 'button_click', state2: 'off' },
            { state1: 'off', transition: 'button_hold', state2: 'color', state2Param: { r: 255, g: 0, b: 0 } }
        ]
    };
    try {
        const response4 = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...mockStateWithRules,
                userInput: 'Delete all button_click rules'
            })
        });
        const result4 = await response4.json();
        console.log('Result:', JSON.stringify(result4, null, 2));
    } catch (error) {
        console.error('Error:', error.message);
    }

    console.log('\n=== Test 5: Multiple tools ===');
    try {
        const response5 = await fetch(baseUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...mockStateWithRules,
                userInput: 'Clear all rules, set counter to 10, and turn the light green now'
            })
        });
        const result5 = await response5.json();
        console.log('Result:', JSON.stringify(result5, null, 2));
    } catch (error) {
        console.error('Error:', error.message);
    }

    console.log('\n=== All tests complete ===');
}

// Run tests
testTools().catch(console.error);
