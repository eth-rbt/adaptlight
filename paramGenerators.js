/**
 * ParamGenerator class - represents a single parameter generator
 * Each generator has a name, description, and function to generate parameters
 */
class ParamGenerator {
    constructor(name, description, fn) {
        this.name = name;
        this.description = description;
        this.fn = fn; // Function that generates the parameter value
    }

    /**
     * Execute the generator function
     * @param {*} context - Optional context (e.g., current state parameters)
     * @returns {*} Generated parameter value
     */
    generate(context = null) {
        return this.fn(context);
    }
}

/**
 * ParamGenerators class - manages a collection of parameter generators
 */
class ParamGenerators {
    constructor() {
        this.generators = new Map();
    }

    /**
     * Add a parameter generator to the collection
     * @param {ParamGenerator} generator - The generator to add
     */
    addGenerator(generator) {
        if (generator instanceof ParamGenerator) {
            this.generators.set(generator.name, generator);
            console.log(`Parameter generator added: ${generator.name}`);
        } else {
            console.error('Can only add ParamGenerator objects');
        }
    }

    /**
     * Get a generator by name
     * @param {string} name - The generator name
     * @returns {ParamGenerator|undefined} The generator or undefined
     */
    getGenerator(name) {
        return this.generators.get(name);
    }

    /**
     * Delete a generator by name
     * @param {string} name - The generator name to delete
     * @returns {boolean} True if deleted, false if not found
     */
    deleteGenerator(name) {
        const result = this.generators.delete(name);
        if (result) {
            console.log(`Parameter generator deleted: ${name}`);
        }
        return result;
    }

    /**
     * Get all generators as an array
     * @returns {Array} Array of ParamGenerator objects
     */
    getGenerators() {
        return Array.from(this.generators.values());
    }

    /**
     * Get formatted list of generators for LLM prompt
     * @returns {string} Formatted string with generator names and descriptions
     */
    getGeneratorsForPrompt() {
        if (this.generators.size === 0) {
            return 'No parameter generators available.';
        }

        const generatorList = Array.from(this.generators.values())
            .map(gen => `- ${gen.name}: ${gen.description}`)
            .join('\n');

        return `Available parameter generators:\n${generatorList}`;
    }

    /**
     * Clear all generators
     */
    clearGenerators() {
        this.generators.clear();
        console.log('All parameter generators cleared');
    }

    /**
     * Execute a generator by name
     * @param {string} name - The generator name
     * @param {*} context - Optional context for the generator
     * @returns {*} Generated value or null if generator not found
     */
    execute(name, context = null) {
        const generator = this.generators.get(name);
        if (generator) {
            return generator.generate(context);
        } else {
            console.error(`Parameter generator not found: ${name}`);
            return null;
        }
    }
}

// Create global instance
window.paramGenerators = new ParamGenerators();

// ===== Register default parameter generators =====

/**
 * Initialize default parameter generators
 */
function initializeDefaultParamGenerators() {
    /**
     * random - Generate a random number within a range
     * Format: random([min, max])
     */
    window.paramGenerators.addGenerator(new ParamGenerator(
    'random',
    'Generates a random integer within a specified range. Usage: random([min, max]). Example: random([0, 255]) returns a number between 0 and 255.',
    (range) => {
        if (!Array.isArray(range) || range.length !== 2) {
            console.error('random() requires array [min, max]');
            return 0;
        }
        const [min, max] = range;
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }
));

/**
 * random_rgb - Generate random RGB color values
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'random_rgb',
    'Generates a random RGB color object with r, g, b values each between 0-255. Usage: random_rgb(). Returns object like {r: 134, g: 67, b: 234}.',
    () => {
        return {
            r: Math.floor(Math.random() * 256),
            g: Math.floor(Math.random() * 256),
            b: Math.floor(Math.random() * 256)
        };
    }
));

/**
 * random_color - Alias for random_rgb
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'random_color',
    'Alias for random_rgb. Generates a random RGB color object. Usage: random_color(). Returns object like {r: 134, g: 67, b: 234}.',
    () => {
        return {
            r: Math.floor(Math.random() * 256),
            g: Math.floor(Math.random() * 256),
            b: Math.floor(Math.random() * 256)
        };
    }
));

/**
 * increment_rgb - Increment current RGB values
 * Takes current color context and adds specified amounts to each channel
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'increment_rgb',
    'Increments the current RGB color by specified amounts. Usage: increment_rgb({r: 10, g: -5, b: 20}). Takes current color state and adds the specified increments, clamping to 0-255 range. If no context, starts from {r:0, g:0, b:0}.',
    (increment) => {
        // Get current color from state data if available
        let currentColor = {r: 0, g: 0, b: 0};

        if (window.stateMachine) {
            const r = window.stateMachine.getData('color_r');
            const g = window.stateMachine.getData('color_g');
            const b = window.stateMachine.getData('color_b');

            if (r !== undefined) currentColor.r = r;
            if (g !== undefined) currentColor.g = g;
            if (b !== undefined) currentColor.b = b;
        }

        // Apply increment
        const newColor = {
            r: currentColor.r + (increment?.r || 0),
            g: currentColor.g + (increment?.g || 0),
            b: currentColor.b + (increment?.b || 0)
        };

        // Clamp to valid range
        newColor.r = Math.max(0, Math.min(255, newColor.r));
        newColor.g = Math.max(0, Math.min(255, newColor.g));
        newColor.b = Math.max(0, Math.min(255, newColor.b));

        return newColor;
    }
));

/**
 * brighten - Increase brightness of current color
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'brighten',
    'Increases the brightness of the current color by adding a specified amount to all RGB channels. Usage: brighten(amount) where amount is typically 10-50. Clamps to 0-255 range. If no amount specified, adds 30.',
    (amount = 30) => {
        return window.paramGenerators.execute('increment_rgb', {
            r: amount,
            g: amount,
            b: amount
        });
    }
));

/**
 * darken - Decrease brightness of current color
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'darken',
    'Decreases the brightness of the current color by subtracting a specified amount from all RGB channels. Usage: darken(amount) where amount is typically 10-50. Clamps to 0-255 range. If no amount specified, subtracts 30.',
    (amount = 30) => {
        return window.paramGenerators.execute('increment_rgb', {
            r: -amount,
            g: -amount,
            b: -amount
        });
    }
));

/**
 * cycle_hue - Rotate hue by shifting RGB values
 */
window.paramGenerators.addGenerator(new ParamGenerator(
    'cycle_hue',
    'Cycles through hues by rotating RGB values. Usage: cycle_hue(). Takes current color and rotates: R→G, G→B, B→R. Creates a color-shifting effect when applied repeatedly.',
    () => {
        // Get current color from state data
        let currentColor = {r: 255, g: 0, b: 0}; // Default to red

        if (window.stateMachine) {
            const r = window.stateMachine.getData('color_r');
            const g = window.stateMachine.getData('color_g');
            const b = window.stateMachine.getData('color_b');

            if (r !== undefined) currentColor.r = r;
            if (g !== undefined) currentColor.g = g;
            if (b !== undefined) currentColor.b = b;
        }

        // Rotate: R→G, G→B, B→R
        return {
            r: currentColor.b,
            g: currentColor.r,
            b: currentColor.g
        };
    }
    ));

    console.log('Parameter generators initialized:', window.paramGenerators.getGenerators().length);
}