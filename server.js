const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const OpenAI = require('openai');
require('dotenv').config();

// Load prompts
const parsingPrompt = require('./prompts/parsing-prompt');

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

// API endpoint to parse text into state machine array
app.post('/parse-text', async (req, res) => {
    try {
        const { userInput, availableStates } = req.body;

        // Build the system prompt with available states
        let systemPrompt = parsingPrompt.systemPrompt;

        if (availableStates) {
            systemPrompt += `\n\nAvailable states in the system:\n${availableStates}`;
        }

        const completion = await openai.chat.completions.create({
            model: "gpt-4o-mini",
            messages: [
                {
                    role: "system",
                    content: systemPrompt
                },
                {
                    role: "user",
                    content: userInput
                }
            ],
            temperature: parsingPrompt.temperature,
        });

        const parsedResult = completion.choices[0].message.content.trim();

        // Parse the JSON array from the response
        let parsedArray;
        try {
            parsedArray = JSON.parse(parsedResult);
        } catch (e) {
            // If parsing fails, try to extract array from response
            const arrayMatch = parsedResult.match(/\[.*\]/);
            if (arrayMatch) {
                parsedArray = JSON.parse(arrayMatch[0]);
            } else {
                throw new Error('Failed to parse response as array');
            }
        }

        res.json({ parsedArray, success: true });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to parse text' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
