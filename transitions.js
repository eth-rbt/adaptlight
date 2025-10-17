/**
 * Transitions class - handles input pattern detection and emits transition events
 * Detects: single click, double click, and hold patterns
 */
class Transitions {
    constructor() {
        this.clickCount = 0;
        this.clickTimer = null;
        this.holdTimer = null;
        this.mousedownTime = null;
        this.isHolding = false;

        // Configuration thresholds (in milliseconds)
        this.DOUBLE_CLICK_THRESHOLD = 300; // Time window for double click
        this.HOLD_THRESHOLD = 500; // Time before a hold is registered

        // Store bound event handlers for cleanup
        this.boundHandlers = {
            mousedown: null,
            mouseup: null,
            click: null
        };
    }

    /**
     * Attach transition detection to a DOM element
     * @param {HTMLElement} element - The element to monitor for transitions
     */
    attachToElement(element) {
        // Create bound handlers
        this.boundHandlers.mousedown = this.handleMouseDown.bind(this);
        this.boundHandlers.mouseup = this.handleMouseUp.bind(this);
        this.boundHandlers.click = this.handleClick.bind(this);

        // Attach event listeners
        element.addEventListener('mousedown', this.boundHandlers.mousedown);
        element.addEventListener('mouseup', this.boundHandlers.mouseup);
        element.addEventListener('click', this.boundHandlers.click);

        console.log('Transitions attached to element:', element);
    }

    /**
     * Detach transition detection from an element
     * @param {HTMLElement} element - The element to detach from
     */
    detachFromElement(element) {
        if (this.boundHandlers.mousedown) {
            element.removeEventListener('mousedown', this.boundHandlers.mousedown);
            element.removeEventListener('mouseup', this.boundHandlers.mouseup);
            element.removeEventListener('click', this.boundHandlers.click);
        }

        // Clear any pending timers
        this.clearTimers();

        console.log('Transitions detached from element:', element);
    }

    /**
     * Handle mousedown event - start of a potential hold
     */
    handleMouseDown(event) {
        this.mousedownTime = Date.now();
        this.isHolding = false;

        // Start hold timer
        this.holdTimer = setTimeout(() => {
            this.isHolding = true;
            this.emitTransition('button_hold');

            // Clear click detection since this is now a hold
            this.clearClickTimer();
            this.clickCount = 0;
        }, this.HOLD_THRESHOLD);
    }

    /**
     * Handle mouseup event - end of a potential hold
     */
    handleMouseUp(event) {
        // Clear hold timer if button is released
        if (this.holdTimer) {
            clearTimeout(this.holdTimer);
            this.holdTimer = null;
        }

        // If this was a hold, optionally emit release event
        if (this.isHolding) {
            // Uncomment if you want a button_release transition:
            // this.emitTransition('button_release');
            this.isHolding = false;
        }

        this.mousedownTime = null;
    }

    /**
     * Handle click event - detect single vs double click
     */
    handleClick(event) {
        // Ignore clicks that were part of a hold gesture
        if (this.isHolding) {
            return;
        }

        this.clickCount++;

        if (this.clickCount === 1) {
            // First click - start waiting for potential second click
            this.clickTimer = setTimeout(() => {
                // Timeout expired, this is a single click
                this.emitTransition('button_click');
                this.clickCount = 0;
            }, this.DOUBLE_CLICK_THRESHOLD);
        } else if (this.clickCount === 2) {
            // Second click arrived - this is a double click
            this.clearClickTimer();
            this.emitTransition('button_double_click');
            this.clickCount = 0;
        }
    }

    /**
     * Clear the click timer
     */
    clearClickTimer() {
        if (this.clickTimer) {
            clearTimeout(this.clickTimer);
            this.clickTimer = null;
        }
    }

    /**
     * Clear all timers
     */
    clearTimers() {
        this.clearClickTimer();

        if (this.holdTimer) {
            clearTimeout(this.holdTimer);
            this.holdTimer = null;
        }
    }

    /**
     * Emit a transition event to the state machine
     * @param {string} transitionName - The name of the transition to emit
     */
    emitTransition(transitionName) {
        console.log(`Transition detected: ${transitionName}`);

        // Execute the transition on the global state machine
        if (window.stateMachine) {
            window.stateMachine.executeTransition(transitionName);
        } else {
            console.error('State machine not found on window object');
        }
    }

    /**
     * Get current configuration
     * @returns {Object} Current threshold configuration
     */
    getConfig() {
        return {
            doubleClickThreshold: this.DOUBLE_CLICK_THRESHOLD,
            holdThreshold: this.HOLD_THRESHOLD
        };
    }

    /**
     * Update configuration thresholds
     * @param {Object} config - Configuration object
     * @param {number} config.doubleClickThreshold - Time window for double click
     * @param {number} config.holdThreshold - Time before hold is registered
     */
    setConfig(config) {
        if (config.doubleClickThreshold !== undefined) {
            this.DOUBLE_CLICK_THRESHOLD = config.doubleClickThreshold;
        }
        if (config.holdThreshold !== undefined) {
            this.HOLD_THRESHOLD = config.holdThreshold;
        }
        console.log('Transitions config updated:', this.getConfig());
    }
}

// Create global instance
window.transitions = new Transitions();