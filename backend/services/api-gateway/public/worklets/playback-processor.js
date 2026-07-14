class PlaybackProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    // Ring buffer size (e.g., 2 seconds of 48kHz audio = 96000 frames)
    this.bufferSize = options?.processorOptions?.bufferSize || 96000;
    this.ringBuffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;
    this.framesAvailable = 0;
    
    // Jitter buffer settings
    this.minJitterFrames = options?.processorOptions?.minJitterFrames || 2400; // 50ms at 48kHz
    this.isPlaying = false;

    this.port.onmessage = (event) => {
      if (event.data.type === 'audio') {
        const pcmData = event.data.data; // Expected Float32Array
        this.writeAudio(pcmData);
      } else if (event.data.type === 'interrupt') {
        this.clearBuffer();
      }
    };
  }

  writeAudio(pcmData) {
    for (let i = 0; i < pcmData.length; i++) {
      this.ringBuffer[this.writeIndex] = pcmData[i];
      this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
      
      if (this.framesAvailable < this.bufferSize) {
        this.framesAvailable++;
      } else {
        // Buffer overflow, overwrite oldest data
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }
  }

  clearBuffer() {
    this.writeIndex = 0;
    this.readIndex = 0;
    this.framesAvailable = 0;
    this.isPlaying = false;
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    const channel = output[0];

    // Check if we should start playing (jitter buffer threshold)
    if (!this.isPlaying && this.framesAvailable >= this.minJitterFrames) {
      this.isPlaying = true;
    }

    if (this.isPlaying && this.framesAvailable >= channel.length) {
      for (let i = 0; i < channel.length; i++) {
        channel[i] = this.ringBuffer[this.readIndex];
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
      this.framesAvailable -= channel.length;
    } else {
      // Not enough data, underrun or waiting for jitter buffer
      this.isPlaying = false;
      for (let i = 0; i < channel.length; i++) {
        channel[i] = 0;
      }
      if (this.framesAvailable > 0) {
         // Notify main thread of underrun if it was playing
         this.port.postMessage({ type: 'underrun' });
      }
    }
    
    return true;
  }
}

registerProcessor('playback-processor', PlaybackProcessor);
