class VoiceCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    // Default to 24kHz output for Moshi
    this.targetSampleRate = options?.processorOptions?.targetSampleRate || 24000;
    this.ratio = sampleRate / this.targetSampleRate;
    this.remainder = 0;

    // Buffer size to emit (e.g. 1920 frames = 80ms at 24kHz)
    this.bufferSize = options?.processorOptions?.bufferSize || 1920;
    this.buffer = new Int16Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input.length > 0) {
      const channelData = input[0];
      if (channelData && channelData.length > 0) {
        for (let i = this.remainder; i < channelData.length; i += this.ratio) {
          const sample = channelData[Math.floor(i)];
          
          // Convert Float32 to Int16
          const s = Math.max(-1, Math.min(1, sample));
          this.buffer[this.bufferIndex++] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          
          if (this.bufferIndex >= this.bufferSize) {
            // Post copy to main thread
            const copy = new Int16Array(this.buffer);
            this.port.postMessage({ type: 'audio', data: copy }, [copy.buffer]);
            this.bufferIndex = 0;
          }
        }
        this.remainder = (channelData.length + this.remainder) % this.ratio;
      }
    }
    return true;
  }
}

registerProcessor('voice-capture-processor', VoiceCaptureProcessor);
