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

// ===== Tool Definitions =====
const tools = [
    {
        type: "function",
        name: "add_rule",
        description: "Add a new state machine rule that defines a transition from one state to another",
        parameters: {
            type: "object",
            properties: {
                state1: {
                    type: "string",
                    description: "The starting state name"
                },
                transition: {
                    type: "string",
                    description: "The transition/trigger name (e.g., 'button_click', 'button_hold')"
                },
                state2: {
                    type: "string",
                    description: "The destination state name"
                },
                state1Param: {
                    type: ["object", "null"],
                    description: "Optional parameters for state1"
                },
                state2Param: {
                    type: ["object", "null"],
                    description: "Optional parameters for state2 (e.g., {r: 255, g: 0, b: 0} for color state)"
                },
                condition: {
                    type: ["string", "null"],
                    description: "Optional condition expression that must be true for this rule to trigger"
                },
                action: {
                    type: ["string", "null"],
                    description: "Optional action to execute before transitioning"
                }
            },
            required: ["state1", "transition", "state2"]
        }
    },
    {
        type: "function",
        name: "delete_rule",
        description: "Delete all rules matching the specified criteria. If multiple criteria are provided, only rules matching ALL criteria will be deleted.",
        parameters: {
            type: "object",
            properties: {
                state1: {
                    type: ["string", "null"],
                    description: "Match rules with this starting state"
                },
                transition: {
                    type: ["string", "null"],
                    description: "Match rules with this transition"
                },
                state2: {
                    type: ["string", "null"],
                    description: "Match rules with this destination state"
                }
            },
            required: []
        }
    },
    {
        type: "function",
        name: "set_state",
        description: "Immediately transition the state machine to a specific state",
        parameters: {
            type: "object",
            properties: {
                state: {
                    type: "string",
                    description: "The state to transition to"
                },
                params: {
                    type: ["object", "null"],
                    description: "Optional parameters to pass to the state"
                }
            },
            required: ["state"]
        }
    },
    {
        type: "function",
        name: "get_time",
        description: "Get the current time information (hour, minute, second, day of week)",
        parameters: {
            type: "object",
            properties: {},
            required: []
        }
    },
    {
        type: "function",
        name: "set_data",
        description: "Set a global state machine data variable",
        parameters: {
            type: "object",
            properties: {
                key: {
                    type: "string",
                    description: "The data key name"
                },
                value: {
                    description: "The value to store (can be any type)"
                }
            },
            required: ["key", "value"]
        }
    }
];

// ===== Tool Execution Functions =====
function executeToolCall(toolName, args, context) {
    const { rules, stateChanges, dataChanges } = context;

    switch (toolName) {
        case "add_rule":
            rules.push({
                state1: args.state1,
                state1Param: args.state1Param || null,
                transition: args.transition,
                state2: args.state2,
                state2Param: args.state2Param || null,
                condition: args.condition || null,
                action: args.action || null
            });
            return { success: true, message: `Added rule: ${args.state1} --[${args.transition}]--> ${args.state2}` };

        case "delete_rule":
            const beforeCount = rules.length;
            const filtered = rules.filter(rule => {
                let matches = true;
                if (args.state1) matches = matches && rule.state1 === args.state1;
                if (args.transition) matches = matches && rule.transition === args.transition;
                if (args.state2) matches = matches && rule.state2 === args.state2;
                return !matches; // Keep rules that DON'T match
            });
            const deletedCount = beforeCount - filtered.length;
            // Update rules array in place
            rules.length = 0;
            rules.push(...filtered);
            return { success: true, message: `Deleted ${deletedCount} rule(s)`, deletedCount };

        case "set_state":
            stateChanges.push({ state: args.state, params: args.params || null });
            return { success: true, message: `Will transition to state: ${args.state}` };

        case "get_time":
            const now = new Date();
            const timeInfo = {
                hour: now.getHours(),
                minute: now.getMinutes(),
                second: now.getSeconds(),
                dayOfWeek: now.getDay(),
                dayName: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][now.getDay()],
                timestamp: now.getTime()
            };
            return timeInfo;

        case "set_data":
            dataChanges.push({ key: args.key, value: args.value });
            return { success: true, message: `Set data: ${args.key} = ${JSON.stringify(args.value)}` };

        default:
            return { error: `Unknown tool: ${toolName}` };
    }
}

// API endpoint to parse text and execute tool calls
app.post('/parse-text', async (req, res) => {
    try {
        const { userInput, conversationHistory, availableStates, availableTransitions, currentRules } = req.body;

        // Build the dynamic content section for system prompt
        let dynamicContent = '\n\n## Current System State\n\n';

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
            dynamicContent += `### Recent User Inputs\n`;
            dynamicContent += conversationHistory.slice(-5).map((msg, idx) =>
                `${idx + 1}. "${msg}"`
            ).join('\n');
            dynamicContent += '\n\n';
        }

        if (currentRules && currentRules.length > 0) {
            dynamicContent += `### Current Rules (${currentRules.length})\n`;
            dynamicContent += currentRules.map(rule =>
                `- ${rule.state1} --[${rule.transition}]--> ${rule.state2}${rule.state2Param ? ` (params: ${JSON.stringify(rule.state2Param)})` : ''}${rule.condition ? ` IF ${rule.condition}` : ''}`
            ).join('\n');
            dynamicContent += '\n\n';
        } else {
            dynamicContent += `### Current Rules\nNo rules defined yet.\n\n`;
        }

        dynamicContent += `\nUse the provided tools to add/delete rules, set state, get time, or set data as needed.`;

        // Build the system prompt
        const systemPrompt = `You are an AI assistant that helps users configure a smart light state machine. The user will describe what they want the light to do, and you should use the provided tools to configure the state machine accordingly.

${dynamicContent}

When the user asks you to configure behavior:
- Use add_rule to create new state transitions
- Use delete_rule to remove existing rules
- Use set_state to immediately change the current state
- Use get_time to check the current time
- Use set_data to store values for use in conditions/actions

After using tools, provide a brief, friendly confirmation of what you did.`;

        // Initialize context for tool execution
        const context = {
            rules: [...currentRules], // Start with copy of current rules
            stateChanges: [],
            dataChanges: []
        };

        console.log('Initial request:', userInput);

        // Build input list for conversation
        const inputList = [
            { role: "system", content: systemPrompt },
            { role: "user", content: userInput }
        ];

        // Make initial request with tools
        let response = await openai.responses.create({
            model: "gpt-5",
            reasoning: { effort: "low" },
            text: { verbosity: "low" },
            input: inputList,
            tools: tools
        });

        // Save response output for subsequent requests
        inputList.push(...response.output);

        console.log('Response output:', response.output);

        // Execute tool calls and build function_call_output entries
        const hasFunctionCalls = response.output.some(item => item.type === "function_call");

        if (hasFunctionCalls) {
            for (const item of response.output) {
                if (item.type === "function_call") {
                    const toolName = item.name;
                    const args = JSON.parse(item.arguments);

                    console.log(`Executing tool: ${toolName}`, args);

                    // Execute the tool
                    const result = executeToolCall(toolName, args, context);

                    console.log(`Tool result:`, result);

                    // Provide function call results to the model
                    inputList.push({
                        type: "function_call_output",
                        call_id: item.call_id,
                        output: JSON.stringify(result)
                    });
                }
            }

            // Make second request with function results
            //response = await openai.responses.create({
            //    model: "gpt-5",
            //    reasoning: { effort: "low" },
            //    text: { verbosity: "low" },
            //    input: inputList,
            //    tools: tools
            //});

            console.log('Final response output:', response.output);
        }

        // Extract final message text
        const finalMessage = response.output_text || "Done!";

        console.log('Final message:', finalMessage);
        console.log('Final rules count:', context.rules.length);
        console.log('State changes:', context.stateChanges);
        console.log('Data changes:', context.dataChanges);

        // Return results
        res.json({
            success: true,
            message: finalMessage,
            rules: context.rules,
            stateChanges: context.stateChanges,
            dataChanges: context.dataChanges
        });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({
            success: false,
            error: 'Failed to parse text',
            details: error.message
        });
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
