// Runs on the audio thread. Converts mic samples to 16-bit PCM and posts 100 ms chunks.
class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Int16Array(1600); // 100 ms at 16 kHz
    this.offset = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (input.length > 0) {
      const channel = input[0];
      for (let i = 0; i < channel.length; i++) {
        const sample = Math.max(-1, Math.min(1, channel[i]));
        this.buffer[this.offset++] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
        if (this.offset === this.buffer.length) {
          this.port.postMessage(this.buffer.buffer.slice(0));
          this.offset = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCaptureProcessor);