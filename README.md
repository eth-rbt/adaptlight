# adaptlight
Adaptive light software - an interactive light simulator that uses AI to generate state machine code for controlling light behaviors.
rsync -avz --exclude '__pycache__' --exclude '.git' --exclude '*.pyc' /Users/ethrbt/code/adaptlight/raspi/ lamp@100.114.12.83:~/Desktop/raspi
## Prerequisites

- Node.js (v14 or higher)
- npm (comes with Node.js)
- OpenAI API key

## Installation

1. Clone the repository and navigate to the project directory:
```bash
cd adaptlight
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env` file in the project root with your OpenAI API key:
```
OPENAI_API_KEY=your_openai_api_key_here
```

## Running the Application

### Development Mode (with auto-reload)
```bash
npm run dev
```

### Production Mode
```bash
npm start
```

The server will start on `http://localhost:3000`

## Usage

1. Open your browser and navigate to `http://localhost:3000`
2. You'll see the AdaptLight Simulator interface with:
   - A button control
   - A light indicator
   - A text input field
3. Enter a description of how you want the light to behave (e.g., "blink 3 times then stay on")
4. Click "Send" to generate the state machine code using AI
5. Click "Run" to execute the generated behavior
6. Watch the light respond according to your instructions

## Project Structure

- `server.js` - Express server that handles API requests and serves static files
- `script.js` - Client-side JavaScript for UI interactions
- `statemachine.js` - Generated state machine code for light control
- `index.html` - Main application interface
- `style.css` - Application styling

## How It Works

The application uses OpenAI's GPT model to interpret natural language descriptions and generate JavaScript state machine code that controls the light behavior. The generated code is automatically saved and can be executed to see the light respond in real-time.
