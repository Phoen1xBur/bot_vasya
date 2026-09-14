// Simple Web Audio sound engine with mute toggle

let audioCtx: AudioContext | null = null;
let muted = false;

function getCtx(): AudioContext | null {
  if (typeof window === "undefined") return null;
  if (!audioCtx) {
    try {
      audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    } catch {
      return null;
    }
  }
  return audioCtx;
}

export function setMuted(m: boolean) {
  muted = m;
}

export function isMuted() {
  return muted;
}

export function beep(freq = 440, duration = 100, type: OscillatorType = "sine", volume = 0.15) {
  if (muted) return;
  const ctx = getCtx();
  if (!ctx) return;
  if (ctx.state === "suspended") ctx.resume();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(volume, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration / 1000);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + duration / 1000);
}

export function soundClick() {
  beep(800, 50, "square", 0.08);
}

export function soundWin() {
  beep(523, 100, "sine", 0.15);
  setTimeout(() => beep(659, 100, "sine", 0.15), 100);
  setTimeout(() => beep(784, 200, "sine", 0.15), 200);
}

export function soundLose() {
  beep(300, 150, "sawtooth", 0.1);
  setTimeout(() => beep(200, 200, "sawtooth", 0.1), 150);
}

export function soundSpin() {
  beep(400, 80, "triangle", 0.06);
}
