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
 * Currently no default generators - use expressions instead
 */
function initializeDefaultParamGenerators() {
    console.log('Parameter generators initialized (expression-based system active)');
}