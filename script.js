// Get references to DOM elements
const light = document.getElementById('light');
const toggleButton = document.getElementById('button');
const textBox = document.getElementById('textBox');
const sendButton = document.getElementById('sendButton');

// Track light state
let isLightOn = false;

// Helper functions for LLM-generated code
function turnLightOn() {
    isLightOn = true;
    light.classList.add('on');
}

function turnLightOff() {
    isLightOn = false;
    light.classList.remove('on');
}

function toggleLight() {
    isLightOn = !isLightOn;
    if (isLightOn) {
        light.classList.add('on');
    } else {
        light.classList.remove('on');
    }
}

function blinkLight(times, interval = 500) {
    let count = 0;
    const blinkInterval = setInterval(() => {
        toggleLight();
        count++;
        if (count >= times * 2) {
            clearInterval(blinkInterval);
        }
    }, interval);
}

// Toggle light on button click
button.addEventListener('click', () => {
    toggleLight();
});

// Send button click handler
sendButton.addEventListener('click', async () => {
    const userInput = textBox.value.trim();
    if (!userInput) return;

    try {
        const response = await fetch('http://localhost:3000/generate-code', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ userInput })
        });

        const data = await response.json();

        if (data.code) {
            // Execute the generated code
            eval(data.code);
            console.log('Executed code:', data.code);
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
