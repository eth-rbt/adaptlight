const express = require('express');
const cors = require('cors');
const OpenAI = require('openai');
require('dotenv').config();

const app = express();
const port = 3000;

// Initialize OpenAI
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
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
                    content: `You are a code generator. The user will describe what they want to do with a light.
Generate ONLY JavaScript code that controls a light. Available functions:
- turnLightOn() - turns the light on
- turnLightOff() - turns the light off
- toggleLight() - toggles the light state
- blinkLight(times, interval) - blinks the light X times with interval in ms

Return ONLY the JavaScript code, no explanations, no markdown, no code blocks.`
                },
                {
                    role: "user",
                    content: userInput
                }
            ],
            temperature: 0.7,
        });

        const generatedCode = completion.choices[0].message.content.trim();
        res.json({ code: generatedCode });
    } catch (error) {
        console.error('Error:', error);
        res.status(500).json({ error: 'Failed to generate code' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
