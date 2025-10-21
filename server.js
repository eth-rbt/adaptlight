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
        const { userInput, conversationHistory, availableStates, availableTransitions, currentRules } = req.body;

        // Build the dynamic content section
        let dynamicContent = '\n\n';

        if (availableStates) {
            dynamicContent += `### Available States\n${availableStates}\n\n`;
        }

        if (availableTransitions && availableTransitions.length > 0) {
            dynamicContent += `### Available Transitions\n`;
            dynamicContent += availableTransitions.map(t =>
                typeof t === 'string' ? `- ${t}` : `- ${t.name}: ${t.description}`
            ).join('\n');
            dynamicContent += '\n\n';
        }

        if (conversationHistory && conversationHistory.length > 0) {
            dynamicContent += `### Past User Inputs\n`;
            dynamicContent += conversationHistory.map((msg, idx) =>
                `${idx + 1}. "${msg}"`
            ).join('\n');
            dynamicContent += '\n\n';
        }

        if (currentRules && currentRules.length > 0) {
            dynamicContent += `### Current Rules\n`;
            dynamicContent += currentRules.map(rule =>
                `- ${rule.state1} --[${rule.transition}]--> ${rule.state2}${rule.state2Param ? ` (with params: ${JSON.stringify(rule.state2Param)})` : ''}`
            ).join('\n');
            dynamicContent += '\n\n';
        } else {
            dynamicContent += `### Current Rules\nNo rules defined yet.\n\n`;
        }

        // Insert dynamic content into the system prompt
        let systemPrompt = parsingPrompt.systemPrompt.replace(
            '---DYNAMIC CONTENT WILL BE INSERTED HERE---',
            dynamicContent
        );

        const result = await openai.responses.create({
            model: "gpt-5",
            input: `${systemPrompt}\n\nUser: ${userInput}`,
            reasoning: { effort: "low" },
            text: { verbosity: "low" },
        });

        const parsedResult = result.output_text.trim();

        // Parse the JSON from the response (should be an array of rules)
        let parsedRules;
        try {
            parsedRules = JSON.parse(parsedResult);
        } catch (e) {
            // If parsing fails, try to extract JSON from response
            const jsonMatch = parsedResult.match(/\[.*\]/s);
            if (jsonMatch) {
                parsedRules = JSON.parse(jsonMatch[0]);
            } else {
                throw new Error('Failed to parse response as JSON array');
            }
        }

        // Ensure the result is an array
        if (!Array.isArray(parsedRules)) {
            parsedRules = [parsedRules];
        }

        // Return the parsed rules
        res.json({ parsedRules, success: true });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to parse text' });
    }
});

// API endpoint to reset rules
app.post('/reset-rules', async (req, res) => {
    try {
        const stateMachineTxtPath = path.join(__dirname, 'statemachine.txt');

        // Clear the file by writing an empty string
        fs.writeFileSync(stateMachineTxtPath, '');

        res.json({ success: true });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to reset rules' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
