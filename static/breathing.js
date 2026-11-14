(() => {
  const circle = document.getElementById("breathCircle");
  const phaseEl = document.getElementById("breathPhase");
  const countdownEl = document.getElementById("breathCountdown");
  const instructionEl = document.getElementById("breathInstruction");
  const startBtn = document.getElementById("breathStart");
  const pauseBtn = document.getElementById("breathPause");
  const resetBtn = document.getElementById("breathReset");
  if (!circle || !phaseEl || !countdownEl || !instructionEl) return;

  const sessionLength = 5 * 60;
  const phases = [
    { name: "Inhale", key: "inhale", seconds: 4, instruction: "Breathe in gently through your nose." },
    { name: "Hold", key: "hold", seconds: 2, instruction: "Pause softly, only if comfortable." },
    { name: "Exhale", key: "exhale", seconds: 6, instruction: "Breathe out slowly and release tension." }
  ];
  let remaining = sessionLength;
  let phaseIndex = 0;
  let phaseRemaining = phases[0].seconds;
  let running = false;
  let intervalId = null;

  function formatTime(seconds) {
    const min = Math.floor(seconds / 60).toString().padStart(2, "0");
    const sec = (seconds % 60).toString().padStart(2, "0");
    return `${min}:${sec}`;
  }
  function render() {
    countdownEl.textContent = formatTime(remaining);
    if (!running && remaining === sessionLength) {
      phaseEl.textContent = "Ready?";
      instructionEl.textContent = "Press Start when you're ready.";
      circle.className = "breath-circle";
    } else if (remaining <= 0) {
      phaseEl.textContent = "Complete";
      instructionEl.textContent = "Well done. Take a moment to notice how you feel.";
      circle.className = "breath-circle";
    } else {
      const phase = phases[phaseIndex];
      phaseEl.textContent = phase.name;
      instructionEl.textContent = phase.instruction;
      circle.className = "breath-circle " + phase.key;
    }
    startBtn.disabled = running || remaining <= 0;
    pauseBtn.disabled = !running;
    startBtn.textContent = remaining <= 0 ? "Session complete" : (remaining < sessionLength ? "Resume" : "Start breathing");
  }
  function tick() {
    if (remaining <= 0) {
      stopTimer();
      remaining = 0;
      render();
      return;
    }
    remaining -= 1;
    phaseRemaining -= 1;
    if (phaseRemaining <= 0) {
      phaseIndex = (phaseIndex + 1) % phases.length;
      phaseRemaining = phases[phaseIndex].seconds;
    }
    render();
  }
  function stopTimer() {
    running = false;
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }
  startBtn.addEventListener("click", () => {
    if (running || remaining <= 0) return;
    running = true;
    render();
    intervalId = setInterval(tick, 1000);
  });
  pauseBtn.addEventListener("click", () => {
    stopTimer();
    instructionEl.textContent = "Paused. Resume whenever you're ready.";
    render();
  });
  resetBtn.addEventListener("click", () => {
    stopTimer();
    remaining = sessionLength;
    phaseIndex = 0;
    phaseRemaining = phases[0].seconds;
    render();
  });
  render();
})();
