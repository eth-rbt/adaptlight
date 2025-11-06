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

// Define tool schemas for OpenAI function calling (GPT-5 format)
const tools = [
    {
        type: "function",
        name: "append_rules",
        description: "Add new state transition rules to the state machine. Use this to create new behaviors.",
        parameters: {
            type: "object",
            properties: {
                rules: {
                    type: "array",
                    description: "Array of rule objects to add",
                    items: {
                        type: "object",
                        properties: {
                            state1: { type: "string", description: "Starting state name" },
                            state1Param: { description: "Parameters for state1 (null if none)" },
                            transition: { type: "string", description: "Transition/event that triggers this rule" },
                            state2: { type: "string", description: "Destination state name" },
                            state2Param: { description: "Parameters for state2 (object, string, or null)" },
                            condition: { type: "string", description: "Optional condition expression" },
                            action: { type: "string", description: "Optional action to execute" }
                        },
                        required: ["state1", "transition", "state2"]
                    }
                }
            },
            required: ["rules"]
        }
    },
    {
        type: "function",
        name: "delete_rules",
        description: "Delete existing rules from the state machine. Can delete by index, by criteria, or all rules.",
        parameters: {
            type: "object",
            properties: {
                indices: {
                    type: "array",
                    description: "Array of rule indices to delete (0-based)",
                    items: { type: "number" }
                },
                state1: { type: "string", description: "Delete rules matching this starting state" },
                transition: { type: "string", description: "Delete rules matching this transition" },
                state2: { type: "string", description: "Delete rules matching this destination state" },
                delete_all: { type: "boolean", description: "If true, delete all rules" }
            }
        }
    },
    {
        type: "function",
        name: "set_state",
        description: "Change the current state of the system immediately.",
        parameters: {
            type: "object",
            properties: {
                state: { type: "string", description: "The state to switch to" },
                params: { description: "Optional parameters to pass to the state (e.g., color values)" }
            },
            required: ["state"]
        }
    },
    {
        type: "function",
        name: "manage_variables",
        description: "Manage global variables in the state machine data store.",
        parameters: {
            type: "object",
            properties: {
                action: {
                    type: "string",
                    enum: ["set", "delete", "clear_all"],
                    description: "Action to perform: 'set' to add/update variables, 'delete' to remove specific keys, 'clear_all' to remove all variables"
                },
                variables: {
                    type: "object",
                    description: "Key-value pairs to set (used with action: 'set')"
                },
                keys: {
                    type: "array",
                    description: "Array of keys to delete (used with action: 'delete')",
                    items: { type: "string" }
                }
            },
            required: ["action"]
        }
    }
];

// API endpoint to parse text into state machine array
app.post('/parse-text', async (req, res) => {
    try {
        const { userInput, conversationHistory, availableStates, availableTransitions, currentRules, currentState, globalVariables } = req.body;

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

        if (currentState) {
            dynamicContent += `### Current State\n${currentState}\n\n`;
        }

        if (globalVariables && Object.keys(globalVariables).length > 0) {
            dynamicContent += `### Global Variables\n`;
            dynamicContent += Object.entries(globalVariables).map(([key, value]) =>
                `- ${key}: ${JSON.stringify(value)}`
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
            dynamicContent += currentRules.map((rule, idx) =>
                `[${idx}] ${rule.state1} --[${rule.transition}]--> ${rule.state2}${rule.state2Param ? ` (with params: ${JSON.stringify(rule.state2Param)})` : ''}${rule.condition ? ` [condition: ${rule.condition}]` : ''}`
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

        // Build input list for GPT-5 (responses API)
        const inputList = [
            { role: "system", content: systemPrompt },
            { role: "user", content: userInput }
        ];

        // Call GPT-5 with tools
        const response = await openai.responses.create({
            model: "gpt-5",
            tools: tools,
            input: inputList,
            reasoning: { effort: "minimal" },
            text: { verbosity: "low" }
        });

        // Process the output
        const results = {
            toolCalls: [],
            success: true
        };

        // Extract function calls and text from the output
        let textResponse = null;

        for (const item of response.output) {
            if (item.type === "function_call") {
                const args = JSON.parse(item.arguments);

                results.toolCalls.push({
                    id: item.call_id,
                    name: item.name,
                    arguments: args
                });
            } else if (item.type === "text") {
                textResponse = item.text;
            }
        }

        // Add text response if present
        if (textResponse) {
            results.message = textResponse;
        }

        res.json(results);
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to parse text', details: error.message });
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
