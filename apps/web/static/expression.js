/**
 * Expression evaluator for AdaptLight web frontend.
 *
 * Mirrors the Python evaluator in brain/utils/expression_evaluator.py
 * Supports: sin, cos, tan, abs, min, max, floor, ceil, round, sqrt, pow, PI, E, random()
 * Variables: r, g, b (current), frame, t (elapsed_ms), elapsed_ms
 */

const ExpressionEvaluator = {
    /**
     * Evaluate a color/animation expression.
     * @param {string|number} expr - Expression string or numeric value
     * @param {object} context - Variables: {r, g, b, frame, t, elapsed_ms}
     * @returns {number} Evaluated result (clamped 0-255 for colors)
     */
    evaluate(expr, context = {}) {
        // If already a number, return clamped
        if (typeof expr === 'number') {
            return Math.max(0, Math.min(255, Math.floor(expr)));
        }

        // If null/undefined, return 0
        if (expr == null) {
            return 0;
        }

        // Must be a string expression
        if (typeof expr !== 'string') {
            return 0;
        }

        try {
            // Build evaluation context
            const ctx = {
                // Current color values
                r: context.r || 0,
                g: context.g || 0,
                b: context.b || 0,
                // Animation variables
                frame: context.frame || 0,
                t: context.t || context.elapsed_ms || 0,
                elapsed_ms: context.elapsed_ms || context.t || 0,
                // Math functions
                sin: Math.sin,
                cos: Math.cos,
                tan: Math.tan,
                abs: Math.abs,
                min: Math.min,
                max: Math.max,
                floor: Math.floor,
                ceil: Math.ceil,
                round: Math.round,
                sqrt: Math.sqrt,
                pow: Math.pow,
                // Constants
                PI: Math.PI,
                E: Math.E,
                // Random (0-255)
                random: () => Math.floor(Math.random() * 256),
            };

            // Create function with context variables as parameters
            const paramNames = Object.keys(ctx);
            const paramValues = Object.values(ctx);

            // Use Function constructor for safe-ish evaluation
            // (safer than eval, variables are explicitly passed)
            const fn = new Function(...paramNames, `return (${expr});`);
            const result = fn(...paramValues);

            return Math.max(0, Math.min(255, Math.floor(result)));
        } catch (e) {
            console.warn(`Expression evaluation error ("${expr}"):`, e.message);
            return context.r || 0;
        }
    },

    /**
     * Check if a state has animated expressions.
     * @param {object} state - State object with r, g, b, speed
     * @returns {boolean} True if state should be animated
     */
    isAnimated(state) {
        if (!state || !state.speed) return false;
        return (
            typeof state.r === 'string' ||
            typeof state.g === 'string' ||
            typeof state.b === 'string'
        );
    },

    /**
     * Compute RGB values for a state at a given frame.
     * @param {object} state - State object with r, g, b
     * @param {number} frame - Current frame number
     * @param {number} elapsed_ms - Milliseconds since animation started
     * @param {object} current - Current RGB values {r, g, b}
     * @returns {object} Computed {r, g, b} values
     */
    computeFrame(state, frame, elapsed_ms, current = {r: 0, g: 0, b: 0}) {
        const context = {
            r: current.r,
            g: current.g,
            b: current.b,
            frame,
            t: elapsed_ms,
            elapsed_ms,
        };

        return {
            r: this.evaluate(state.r, context),
            g: this.evaluate(state.g, context),
            b: this.evaluate(state.b, context),
        };
    }
};
