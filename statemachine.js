if (window.stateMachineInterval) {
    clearInterval(window.stateMachineInterval);
}

window.state = 'blinking';
window.stateData = { blinkCount: 0 };

window.stateMachineInterval = setInterval(() => {
    console.log('State:', window.state);
    if (window.state === 'blinking') {
        toggleLight();
        window.stateData.blinkCount++;
        console.log('Blink count:', window.stateData.blinkCount);
        if (window.stateData.blinkCount >= 4) {
            turnLightOff();
            clearInterval(window.stateMachineInterval);
            window.state = 'idle';
        }
    }
}, 500);