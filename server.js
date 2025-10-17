const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const OpenAI = require('openai');
require('dotenv').config();

const app = express();
const port = 3000;

// Initialize OpenAI
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});

app.use(cors());
app.use(express.json());

// Serve static files
app.use(express.static('.'));

// API endpoint to generate code
app.post('/generate-code', async (req, res) => {
    try {
        const { userInput } = req.body;

        const completion = await openai.chat.completions.create({
            model: "gpt-4o-mini",
            messages: [
                {
                    role: "system",
                    content: `You are a code generator for a state machine that controls a light.
The user will describe what they want to do with a light.

Generate a complete JavaScript state machine file with:
1. State variables (currentState, stateData, etc.)
2. A setInterval loop that runs every 100ms
3. State logic inside the interval

Available functions you can call:
- turnLightOn() - turns the light on
- turnLightOff() - turns the light off
- toggleLight() - toggles the light state

IMPORTANT:
- Use window.state (NOT currentState) for the main state
- Use window.stateData for any additional variables (e.g., window.stateData.blinkCount)
- Clear and reassign window.stateMachineInterval

Example structure:
// Clear any existing interval
if (window.stateMachineInterval) {
    clearInterval(window.stateMachineInterval);
}

window.state = 'blinking';
window.stateData.blinkCount = 0;

window.stateMachineInterval = setInterval(() => {
    if (window.state === 'blinking') {
        toggleLight();
        window.stateData.blinkCount++;
        if (window.stateData.blinkCount >= 6) {
            window.state = 'idle';
        }
    }
}, 500);

Return ONLY the JavaScript code for the state machine, no explanations, no markdown, no code blocks.`
                },
                {
                    role: "user",
                    content: userInput
                }
            ],
            temperature: 0.7,
        });

        const generatedCode = completion.choices[0].message.content.trim();

        // Write the generated code to statemachine.js
        const stateMachinePath = path.join(__dirname, 'statemachine.js');
        fs.writeFileSync(stateMachinePath, generatedCode);

        res.json({ code: generatedCode, updated: true });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to generate code' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
