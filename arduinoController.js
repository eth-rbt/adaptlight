/**
 * ArduinoController - handles WebSerial communication with Arduino
 * Receives button transitions from Arduino and sends LED commands to Arduino
 */
class ArduinoController {
    constructor() {
        this.port = null;
        this.reader = null;
        this.writer = null;
        this.isConnected = false;
        this.readableStreamClosed = null;
        this.writableStreamClosed = null;
    }

    /**
     * Check if WebSerial API is supported
     */
    isSupported() {
        return 'serial' in navigator;
    }

    /**
     * Connect to Arduino via WebSerial
     */
    async connect() {
        if (!this.isSupported()) {
            throw new Error('WebSerial is not supported in this browser');
        }

        try {
            // Request a port and open a connection
            this.port = await navigator.serial.requestPort();
            await this.port.open({ baudRate: 115200 });

            this.isConnected = true;
            console.log('Connected to Arduino');

            // Set up the reader and writer
            const textDecoder = new TextDecoderStream();
            this.readableStreamClosed = this.port.readable.pipeTo(textDecoder.writable);
            this.reader = textDecoder.readable.getReader();

            const textEncoder = new TextEncoderStream();
            this.writableStreamClosed = textEncoder.readable.pipeTo(this.port.writable);
            this.writer = textEncoder.writable.getWriter();

            // Start reading messages
            this.startReading();

            return true;
        } catch (error) {
            console.error('Failed to connect to Arduino:', error);
            this.isConnected = false;
            throw error;
        }
    }

    /**
     * Disconnect from Arduino
     */
    async disconnect() {
        if (!this.isConnected) {
            return;
        }

        try {
            // Cancel the reader
            if (this.reader) {
                await this.reader.cancel();
                await this.readableStreamClosed.catch(() => {}); // Ignore errors
            }

            // Close the writer
            if (this.writer) {
                await this.writer.close();
                await this.writableStreamClosed.catch(() => {}); // Ignore errors
            }

            // Close the port
            if (this.port) {
                await this.port.close();
            }

            this.isConnected = false;
            this.port = null;
            this.reader = null;
            this.writer = null;

            console.log('Disconnected from Arduino');
        } catch (error) {
            console.error('Error disconnecting from Arduino:', error);
        }
    }

    /**
     * Start reading messages from Arduino
     */
    async startReading() {
        let buffer = '';

        try {
            while (true) {
                const { value, done } = await this.reader.read();
                if (done) {
                    break;
                }

                // Append to buffer and process complete lines
                buffer += value;
                const lines = buffer.split('\n');

                // Keep the last incomplete line in the buffer
                buffer = lines.pop();

                // Process complete lines
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (trimmed) {
                        this.handleMessage(trimmed);
                    }
                }
            }
        } catch (error) {
            console.error('Error reading from Arduino:', error);
            this.isConnected = false;
        }
    }

    /**
     * Handle incoming message from Arduino
     * @param {string} message - The message received from Arduino
     */
    handleMessage(message) {
        console.log('Arduino message:', message);

        // Map Arduino messages to transition names
        const transitionMap = {
            'button_click': 'button_click',
            'button_double_click': 'button_double_click',
            'button_hold': 'button_hold',
            'button_release': 'button_release',
            // Legacy support for old Arduino code
            'button press': 'button_click'
        };

        const transition = transitionMap[message];
        if (transition) {
            this.emitTransition(transition);
        } else {
            console.warn('Unknown Arduino message:', message);
        }
    }

    /**
     * Emit a transition event to the state machine
     * @param {string} transitionName - The name of the transition to emit
     */
    emitTransition(transitionName) {
        console.log(`Arduino transition detected: ${transitionName}`);

        // Execute the transition on the global state machine
        if (window.stateMachine) {
            window.stateMachine.executeTransition(transitionName);
        } else {
            console.error('State machine not found on window object');
        }
    }

    /**
     * Send LED color command to Arduino
     * @param {number} r - Red value (0-255)
     * @param {number} g - Green value (0-255)
     * @param {number} b - Blue value (0-255)
     * @param {number} brightness - Brightness (0-255), optional
     */
    async sendColor(r, g, b, brightness = null) {
        if (!this.isConnected || !this.writer) {
            console.warn('Cannot send color: not connected to Arduino');
            return;
        }

        try {
            let command;
            if (brightness !== null) {
                command = `COLOR:${r},${g},${b},${brightness}\n`;
            } else {
                command = `COLOR:${r},${g},${b}\n`;
            }

            await this.writer.write(command);
            console.log('Sent to Arduino:', command.trim());
        } catch (error) {
            console.error('Error sending color to Arduino:', error);
        }
    }

    /**
     * Send brightness command to Arduino
     * @param {number} brightness - Brightness (0-255)
     */
    async sendBrightness(brightness) {
        if (!this.isConnected || !this.writer) {
            console.warn('Cannot send brightness: not connected to Arduino');
            return;
        }

        try {
            const command = `BRIGHTNESS:${brightness}\n`;
            await this.writer.write(command);
            console.log('Sent to Arduino:', command.trim());
        } catch (error) {
            console.error('Error sending brightness to Arduino:', error);
        }
    }

    /**
     * Get connection status
     */
    getStatus() {
        return {
            connected: this.isConnected,
            supported: this.isSupported()
        };
    }
}

// Create global instance
window.arduinoController = new ArduinoController();
