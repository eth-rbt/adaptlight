/**
 * Expression evaluators for AdaptLight web frontend.
 *
 * Supports three representation versions:
 * - original: r/g/b expression strings with frame variable
 * - pure_python: full Python render(prev, t) functions with math/random
 * - stdlib: Python render(prev, t) with helper functions (hsv, lerp, etc.)
 */

// =============================================================================
// ORIGINAL EVALUATOR (expression strings)
// =============================================================================

class OriginalEvaluator {
    /**
     * Original approach: separate r/g/b expression strings.
     * State: { r: "sin(frame * 0.05) * 127 + 128", g: 0, b: "...", speed: 30 }
     */

    constructor() {
        this.frame = 0;
        this.startTime = null;
    }

    isAnimated(state) {
        if (!state || !state.speed) return false;
        return (
            typeof state.r === 'string' ||
            typeof state.g === 'string' ||
            typeof state.b === 'string'
        );
    }

    reset() {
        this.frame = 0;
        this.startTime = null;
    }

    evaluate(expr, context = {}) {
        if (typeof expr === 'number') {
            return Math.max(0, Math.min(255, Math.floor(expr)));
        }
        if (expr == null) return 0;
        if (typeof expr !== 'string') return 0;

        try {
            const ctx = {
                r: context.r || 0,
                g: context.g || 0,
                b: context.b || 0,
                frame: context.frame || 0,
                t: context.t || 0,
                elapsed_ms: context.elapsed_ms || 0,
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
                PI: Math.PI,
                E: Math.E,
                random: () => Math.floor(Math.random() * 256),
            };

            const paramNames = Object.keys(ctx);
            const paramValues = Object.values(ctx);
            const fn = new Function(...paramNames, `return (${expr});`);
            const result = fn(...paramValues);

            return Math.max(0, Math.min(255, Math.floor(result)));
        } catch (e) {
            console.warn(`Expression error ("${expr}"):`, e.message);
            return 0;
        }
    }

    /**
     * Render a frame for the given state.
     * @returns {{ rgb: [r, g, b], nextMs: number|null }}
     */
    render(state, prev, elapsedMs) {
        if (this.startTime === null) {
            this.startTime = performance.now();
        }

        const context = {
            r: prev[0],
            g: prev[1],
            b: prev[2],
            frame: this.frame,
            t: elapsedMs,
            elapsed_ms: elapsedMs,
        };

        const r = this.evaluate(state.r, context);
        const g = this.evaluate(state.g, context);
        const b = this.evaluate(state.b, context);

        this.frame++;

        return {
            rgb: [r, g, b],
            nextMs: state.speed || null
        };
    }
}


// =============================================================================
// STDLIB EVALUATOR (Python code with helper functions)
// =============================================================================

class StdlibEvaluator {
    /**
     * Stdlib: Python render(prev, t) function with helper functions.
     * State: { code: "def render(prev, t):\n    return hsv(t * 0.1 % 1, 1, 1), 30" }
     */

    constructor() {
        this.renderFn = null;
        this.compiledCode = null;
    }

    // --- Helper functions (stdlib) ---

    static hsv(h, s, v) {
        h = ((h % 1) + 1) % 1; // Handle negative
        const i = Math.floor(h * 6);
        const f = h * 6 - i;
        const p = v * (1 - s);
        const q = v * (1 - f * s);
        const t_val = v * (1 - (1 - f) * s);

        let r, g, b;
        switch (i % 6) {
            case 0: r = v; g = t_val; b = p; break;
            case 1: r = q; g = v; b = p; break;
            case 2: r = p; g = v; b = t_val; break;
            case 3: r = p; g = q; b = v; break;
            case 4: r = t_val; g = p; b = v; break;
            default: r = v; g = p; b = q; break;
        }

        return [Math.floor(r * 255), Math.floor(g * 255), Math.floor(b * 255)];
    }

    static rgb(r, g, b) {
        return [
            Math.floor(Math.max(0, Math.min(255, r))),
            Math.floor(Math.max(0, Math.min(255, g))),
            Math.floor(Math.max(0, Math.min(255, b)))
        ];
    }

    static lerp(a, b, t) {
        return a + (b - a) * t;
    }

    static lerp_color(c1, c2, t) {
        return [
            Math.floor(c1[0] + (c2[0] - c1[0]) * t),
            Math.floor(c1[1] + (c2[1] - c1[1]) * t),
            Math.floor(c1[2] + (c2[2] - c1[2]) * t)
        ];
    }

    static clamp(x, lo, hi) {
        return Math.max(lo, Math.min(hi, x));
    }

    static map_range(x, in_lo, in_hi, out_lo, out_hi) {
        return out_lo + (x - in_lo) * (out_hi - out_lo) / (in_hi - in_lo);
    }

    static ease_in(t) {
        return t * t;
    }

    static ease_out(t) {
        return 1 - (1 - t) * (1 - t);
    }

    static ease_in_out(t) {
        if (t < 0.5) {
            return 2 * t * t;
        } else {
            return 1 - Math.pow(-2 * t + 2, 2) / 2;
        }
    }

    isAnimated(state) {
        return state && state.code;
    }

    reset() {
        this.renderFn = null;
        this.compiledCode = null;
    }

    /**
     * Transpile Python render function to JavaScript.
     */
    compile(code) {
        if (this.compiledCode === code && this.renderFn) {
            return this.renderFn;
        }

        let jsCode;
        try {
            jsCode = this._transpile(code);
            console.log('Transpiled JS:', jsCode);  // Debug: show transpiled code
            // Create function with stdlib in scope
            const fn = new Function(
                'hsv', 'rgb', 'lerp', 'lerp_color', 'clamp', 'map_range',
                'ease_in', 'ease_out', 'ease_in_out',
                'sin', 'cos', 'tan', 'abs', 'floor', 'ceil', 'sqrt', 'pow',
                'min', 'max', 'round', 'random', 'randint', 'PI', 'E', 'int', 'float', 'len', 'range',
                `${jsCode}\nreturn render;`
            );

            this.renderFn = fn(
                StdlibEvaluator.hsv,
                StdlibEvaluator.rgb,
                StdlibEvaluator.lerp,
                StdlibEvaluator.lerp_color,
                StdlibEvaluator.clamp,
                StdlibEvaluator.map_range,
                StdlibEvaluator.ease_in,
                StdlibEvaluator.ease_out,
                StdlibEvaluator.ease_in_out,
                Math.sin, Math.cos, Math.tan, Math.abs, Math.floor, Math.ceil, Math.sqrt, Math.pow,
                Math.min, Math.max, Math.round,
                Math.random,
                (lo, hi) => Math.floor(Math.random() * (hi - lo + 1)) + lo,
                Math.PI, Math.E,
                (x) => Math.floor(x),
                (x) => parseFloat(x),
                (x) => x.length,
                (n) => [...Array(n).keys()]
            );

            this.compiledCode = code;
            return this.renderFn;
        } catch (e) {
            console.error('Compilation error:', e);
            console.error('Python code:', code);
            console.error('Transpiled JS:', jsCode);
            this.renderFn = (prev, t) => [prev, null];
            return this.renderFn;
        }
    }

    /**
     * Simple Python to JavaScript transpiler for the subset we use.
     */
    _transpile(pythonCode) {
        let js = pythonCode;

        // FIRST: Strip and store comments to avoid mangling them
        const comments = [];
        js = js.replace(/#([^\n]*)/g, (match, comment) => {
            comments.push(comment);
            return `__COMMENT_${comments.length - 1}__`;
        });

        // Remove 'def ' and add 'function '
        js = js.replace(/def\s+(\w+)\s*\(/g, 'function $1(');

        // Python True/False/None -> JS
        js = js.replace(/\bTrue\b/g, 'true');
        js = js.replace(/\bFalse\b/g, 'false');
        js = js.replace(/\bNone\b/g, 'null');

        // Python 'and'/'or'/'not' -> JS (now safe, comments are stripped)
        js = js.replace(/\band\b/g, '&&');
        js = js.replace(/\bor\b/g, '||');
        js = js.replace(/\bnot\s+/g, '!');

        // Python elif -> else if
        js = js.replace(/\belif\b/g, 'else if');

        // Handle Python's power operator **
        js = js.replace(/(\w+|\))\s*\*\*\s*(\w+|\()/g, 'pow($1, $2)');

        // Handle Python tuple unpacking: "a, b, c = expr" -> "var [a, b, c] = expr"
        js = js.replace(/^(\s*)(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*=\s*(.+)$/gm, (match, indent, a, b, c, expr) => {
            // Strip any trailing comment placeholder
            expr = expr.replace(/__COMMENT_\d+__/, '').trim();
            // If expr contains comma but no parens/brackets, wrap in brackets
            if (expr.includes(',') && !expr.includes('(') && !expr.includes('[')) {
                return `${indent}var [${a}, ${b}, ${c}] = [${expr}]`;
            }
            return `${indent}var [${a}, ${b}, ${c}] = ${expr}`;
        });
        js = js.replace(/^(\s*)(\w+)\s*,\s*(\w+)\s*=\s*(.+)$/gm, (match, indent, a, b, expr) => {
            expr = expr.replace(/__COMMENT_\d+__/, '').trim();
            if (expr.includes(',') && !expr.includes('(') && !expr.includes('[')) {
                return `${indent}var [${a}, ${b}] = [${expr}]`;
            }
            return `${indent}var [${a}, ${b}] = ${expr}`;
        });

        // Handle simple variable assignments: "x = expr" -> "var x = expr"
        js = js.replace(/^(\s*)([a-z_]\w*)\s*=\s*([^=].*)$/gim, '$1var $2 = $3');

        // Handle Python tuple returns: "return expr, value" -> "return [expr, value]"
        js = js.split('\n').map(line => {
            const returnMatch = line.match(/^(\s*)return\s+(.+)$/);
            if (returnMatch) {
                const indent = returnMatch[1];
                let expr = returnMatch[2];
                // Strip trailing comment placeholder for processing
                const commentMatch = expr.match(/(__COMMENT_\d+__)$/);
                if (commentMatch) {
                    expr = expr.replace(commentMatch[1], '').trim();
                }
                // Find the last comma not inside parentheses
                let depth = 0;
                let lastCommaIdx = -1;
                for (let i = 0; i < expr.length; i++) {
                    if (expr[i] === '(' || expr[i] === '[') depth++;
                    else if (expr[i] === ')' || expr[i] === ']') depth--;
                    else if (expr[i] === ',' && depth === 0) lastCommaIdx = i;
                }
                if (lastCommaIdx > 0) {
                    const first = expr.substring(0, lastCommaIdx).trim();
                    const second = expr.substring(lastCommaIdx + 1).trim();
                    return `${indent}return [${first}, ${second}]`;
                }
            }
            return line;
        }).join('\n');

        // Handle Python tuples in parentheses: (a, b, c) -> [a, b, c]
        js = js.replace(/(?<!\w)\((\w+)\s*,\s*(\w+)\s*,\s*(\w+)\)/g, '[$1, $2, $3]');
        js = js.replace(/(?<!\w)\((\w+)\s*,\s*(\w+)\)/g, '[$1, $2]');

        // Remove any remaining comment placeholders before indentation processing
        js = js.replace(/__COMMENT_\d+__/g, '');

        // Convert indentation-based blocks to braces
        js = this._convertIndentation(js);

        return js;
    }

    /**
     * Convert Python indentation to JS braces.
     */
    _convertIndentation(code) {
        const lines = code.split('\n');
        const result = [];
        const indentStack = [0];

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            const trimmed = line.trimStart();

            if (trimmed === '' || trimmed.startsWith('//')) {
                result.push(line);
                continue;
            }

            const currentIndent = line.length - trimmed.length;
            const prevIndent = indentStack[indentStack.length - 1];

            // Close blocks when dedenting
            while (currentIndent < prevIndent && indentStack.length > 1) {
                indentStack.pop();
                const spaces = '    '.repeat(indentStack.length);
                result.push(spaces + '}');
            }

            // Check if line ends with colon (start of block)
            if (trimmed.endsWith(':')) {
                const indent = line.substring(0, currentIndent);
                let statement = trimmed.slice(0, -1); // Remove colon

                // Add parentheses around if/else if conditions
                if (statement.startsWith('if ')) {
                    const condition = statement.substring(3).trim();
                    line = `${indent}if (${condition}) {`;
                } else if (statement.startsWith('else if ')) {
                    const condition = statement.substring(8).trim();
                    line = `${indent}} else if (${condition}) {`;
                    // Don't push closing brace separately since we included it
                    // Remove the last '}' we added when dedenting
                    if (result.length > 0 && result[result.length - 1].trim() === '}') {
                        result.pop();
                    }
                } else if (statement === 'else') {
                    line = `${indent}} else {`;
                    if (result.length > 0 && result[result.length - 1].trim() === '}') {
                        result.pop();
                    }
                } else {
                    // Other blocks (function, for, while, etc.)
                    line = `${indent}${statement} {`;
                }

                result.push(line);
                indentStack.push(currentIndent + 4);
            } else {
                // Regular statement - add semicolon if needed
                if (!trimmed.endsWith('{') && !trimmed.endsWith('}') &&
                    !trimmed.endsWith(';') && !trimmed.startsWith('//')) {
                    line = line + ';';
                }
                result.push(line);
            }
        }

        // Close any remaining open blocks
        while (indentStack.length > 1) {
            indentStack.pop();
            result.push('}');
        }

        return result.join('\n');
    }

    /**
     * Render a frame.
     * @returns {{ rgb: [r, g, b], nextMs: number|null }}
     */
    render(state, prev, elapsedMs) {
        // If no code field, fall back to simple r/g/b values
        if (!state.code) {
            const r = typeof state.r === 'number' ? state.r : 0;
            const g = typeof state.g === 'number' ? state.g : 0;
            const b = typeof state.b === 'number' ? state.b : 0;
            return {
                rgb: [
                    Math.max(0, Math.min(255, Math.floor(r))),
                    Math.max(0, Math.min(255, Math.floor(g))),
                    Math.max(0, Math.min(255, Math.floor(b)))
                ],
                nextMs: null
            };
        }

        const renderFn = this.compile(state.code);

        try {
            // t is in seconds for stdlib
            const t = elapsedMs / 1000;
            const result = renderFn(prev, t);

            // Result is [[r, g, b], nextMs] or [(r, g, b), nextMs]
            if (Array.isArray(result) && result.length === 2) {
                const [rgb, nextMs] = result;
                return {
                    rgb: Array.isArray(rgb) ? rgb : [rgb.r || 0, rgb.g || 0, rgb.b || 0],
                    nextMs: nextMs
                };
            }

            return { rgb: prev, nextMs: null };
        } catch (e) {
            console.error('Render error:', e);
            return { rgb: prev, nextMs: null };
        }
    }
}


// =============================================================================
// PURE PYTHON EVALUATOR (same as stdlib but with math module)
// =============================================================================

class PurePythonEvaluator extends StdlibEvaluator {
    /**
     * Pure Python: render(prev, t) with math/random modules available.
     * No helper functions like hsv() - you write everything yourself.
     */

    compile(code) {
        if (this.compiledCode === code && this.renderFn) {
            return this.renderFn;
        }

        try {
            const jsCode = this._transpile(code);

            // Math module object
            const mathModule = {
                sin: Math.sin,
                cos: Math.cos,
                tan: Math.tan,
                asin: Math.asin,
                acos: Math.acos,
                atan: Math.atan,
                atan2: Math.atan2,
                floor: Math.floor,
                ceil: Math.ceil,
                sqrt: Math.sqrt,
                pow: Math.pow,
                exp: Math.exp,
                log: Math.log,
                log10: Math.log10,
                pi: Math.PI,
                e: Math.E,
            };

            // Random module object
            const randomModule = {
                random: Math.random,
                randint: (lo, hi) => Math.floor(Math.random() * (hi - lo + 1)) + lo,
                choice: (arr) => arr[Math.floor(Math.random() * arr.length)],
                uniform: (lo, hi) => lo + Math.random() * (hi - lo),
            };

            const fn = new Function(
                'math', 'random',
                'abs', 'min', 'max', 'round', 'int', 'float', 'bool', 'len', 'range', 'sum',
                `${jsCode}\nreturn render;`
            );

            this.renderFn = fn(
                mathModule,
                randomModule,
                Math.abs, Math.min, Math.max, Math.round,
                (x) => Math.floor(x),
                (x) => parseFloat(x),
                (x) => !!x,
                (x) => x.length,
                (n) => [...Array(n).keys()],
                (arr) => arr.reduce((a, b) => a + b, 0)
            );

            this.compiledCode = code;
            return this.renderFn;
        } catch (e) {
            console.error('Compilation error:', e);
            this.renderFn = (prev, t) => [prev, null];
            return this.renderFn;
        }
    }
}


// =============================================================================
// STDLIB JS EVALUATOR (native JavaScript, no transpilation)
// =============================================================================

class StdlibJSEvaluator {
    /**
     * Stdlib JS: JavaScript code executed directly, no transpilation needed.
     * State: { code: "function render(prev, t) { return [hsv(t * 0.1 % 1, 1, 1), 30]; }" }
     */

    constructor() {
        this.renderFn = null;
        this.compiledCode = null;
    }

    isAnimated(state) {
        return state && state.code;
    }

    reset() {
        this.renderFn = null;
        this.compiledCode = null;
    }

    /**
     * Compile JS code directly (no transpilation).
     */
    compile(code) {
        if (this.compiledCode === code && this.renderFn) {
            return this.renderFn;
        }

        try {
            console.log('Compiling JS code directly');
            // Create function with stdlib in scope - code is already JavaScript
            const fn = new Function(
                'hsv', 'rgb', 'lerp', 'lerp_color', 'clamp', 'map_range',
                'ease_in', 'ease_out', 'ease_in_out',
                'sin', 'cos', 'tan', 'abs', 'floor', 'ceil', 'sqrt', 'pow',
                'min', 'max', 'round', 'random', 'randint', 'PI', 'E', 'int', 'float', 'len', 'range',
                `${code}\nreturn render;`
            );

            this.renderFn = fn(
                StdlibEvaluator.hsv,
                StdlibEvaluator.rgb,
                StdlibEvaluator.lerp,
                StdlibEvaluator.lerp_color,
                StdlibEvaluator.clamp,
                StdlibEvaluator.map_range,
                StdlibEvaluator.ease_in,
                StdlibEvaluator.ease_out,
                StdlibEvaluator.ease_in_out,
                Math.sin, Math.cos, Math.tan, Math.abs, Math.floor, Math.ceil, Math.sqrt, Math.pow,
                Math.min, Math.max, Math.round,
                Math.random,
                (lo, hi) => Math.floor(Math.random() * (hi - lo + 1)) + lo,
                Math.PI, Math.E,
                (x) => Math.floor(x),
                (x) => parseFloat(x),
                (x) => x.length,
                (n) => [...Array(n).keys()]
            );

            this.compiledCode = code;
            return this.renderFn;
        } catch (e) {
            console.error('JS Compilation error:', e);
            console.error('Code:', code);
            this.renderFn = (prev, t) => [prev, null];
            return this.renderFn;
        }
    }

    /**
     * Render a frame.
     * @returns {{ rgb: [r, g, b], nextMs: number|null }}
     */
    render(state, prev, elapsedMs) {
        // If no code field, fall back to simple r/g/b values
        if (!state.code) {
            const r = typeof state.r === 'number' ? state.r : 0;
            const g = typeof state.g === 'number' ? state.g : 0;
            const b = typeof state.b === 'number' ? state.b : 0;
            return {
                rgb: [
                    Math.max(0, Math.min(255, Math.floor(r))),
                    Math.max(0, Math.min(255, Math.floor(g))),
                    Math.max(0, Math.min(255, Math.floor(b)))
                ],
                nextMs: null
            };
        }

        const renderFn = this.compile(state.code);

        try {
            // t is in seconds
            const t = elapsedMs / 1000;
            const result = renderFn(prev, t);

            // Result is [[r, g, b], nextMs]
            if (Array.isArray(result) && result.length === 2) {
                const [rgb, nextMs] = result;
                return {
                    rgb: Array.isArray(rgb) ? rgb : [rgb.r || 0, rgb.g || 0, rgb.b || 0],
                    nextMs: nextMs
                };
            }

            return { rgb: prev, nextMs: null };
        } catch (e) {
            console.error('JS Render error:', e);
            return { rgb: prev, nextMs: null };
        }
    }
}


// =============================================================================
// UNIFIED EXPRESSION EVALUATOR
// =============================================================================

const ExpressionEvaluator = {
    version: 'original',
    evaluator: new OriginalEvaluator(),

    /**
     * Set the representation version.
     * @param {string} version - 'original', 'pure_python', 'stdlib', or 'stdlib_js'
     */
    setVersion(version) {
        this.version = version;
        switch (version) {
            case 'original':
                this.evaluator = new OriginalEvaluator();
                break;
            case 'pure_python':
                this.evaluator = new PurePythonEvaluator();
                break;
            case 'stdlib':
                this.evaluator = new StdlibEvaluator();
                break;
            case 'stdlib_js':
                this.evaluator = new StdlibJSEvaluator();
                break;
            default:
                console.warn(`Unknown version: ${version}, using stdlib_js`);
                this.evaluator = new StdlibJSEvaluator();
        }
        console.log(`ExpressionEvaluator: using ${version} renderer`);
    },

    /**
     * Check if state has animation.
     */
    isAnimated(state) {
        return this.evaluator.isAnimated(state);
    },

    /**
     * Reset evaluator state.
     */
    reset() {
        this.evaluator.reset();
    },

    /**
     * Render a frame for the given state.
     * @param {object} state - State object
     * @param {[number, number, number]} prev - Previous RGB values
     * @param {number} elapsedMs - Milliseconds since animation started
     * @returns {{ rgb: [r, g, b], nextMs: number|null }}
     */
    render(state, prev, elapsedMs) {
        return this.evaluator.render(state, prev, elapsedMs);
    },

    // Legacy API for backwards compatibility
    evaluate(expr, context = {}) {
        if (this.evaluator instanceof OriginalEvaluator) {
            return this.evaluator.evaluate(expr, context);
        }
        return 0;
    },

    computeFrame(state, frame, elapsed_ms, current = {r: 0, g: 0, b: 0}) {
        const prev = [current.r, current.g, current.b];
        const result = this.render(state, prev, elapsed_ms);
        return {
            r: result.rgb[0],
            g: result.rgb[1],
            b: result.rgb[2]
        };
    }
};
