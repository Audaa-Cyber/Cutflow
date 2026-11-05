/**
 * Synchronized Audio Sound Design & Web Audio API Sub-Mixer (Phase 5).
 * 
 * Synchronizes sound effect events (sticker pops, tactile clicks, whip-pan whooshes,
 * camera punch impacts) directly to video playhead playback with automatic volume
 * ducking and scrub-cancellation.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SFXSubMixer = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  class SFXSubMixer {
    constructor() {
      this.audioCtx = null;
      this.masterGain = null;
      this.videoSourceNode = null;
      this.videoGainNode = null;
      this.buffers = new Map();
      this.events = [];
      this.playedEventIds = new Set();
      this.lastPlayheadSec = 0;
      this.isDucking = false;
      this.isInitialized = false;
    }

    /**
     * Lazily initialize Web Audio Context on first user interaction.
     */
    initContext() {
      if (this.audioCtx) {
        if (this.audioCtx.state === 'suspended') {
          this.audioCtx.resume();
        }
        return;
      }

      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtxClass) return;

      this.audioCtx = new AudioCtxClass();
      this.masterGain = this.audioCtx.createGain();
      this.masterGain.gain.setValueAtTime(0.85, this.audioCtx.currentTime);
      this.masterGain.connect(this.audioCtx.destination);
      this.isInitialized = true;

      // Preload sound assets or prepare synthetic generators
      this.preloadAssets();
    }

    /**
     * Attach and wrap the video element for automated volume ducking.
     * 
     * @param {HTMLVideoElement} videoElement
     */
    attachVideo(videoElement) {
      if (!videoElement) return;
      this.initContext();

      if (!this.audioCtx || this.videoSourceNode) return;

      try {
        // Route video through Web Audio API to enable ducking
        this.videoSourceNode = this.audioCtx.createMediaElementSource(videoElement);
        this.videoGainNode = this.audioCtx.createGain();
        this.videoGainNode.gain.setValueAtTime(1.0, this.audioCtx.currentTime);

        this.videoSourceNode.connect(this.videoGainNode);
        this.videoGainNode.connect(this.audioCtx.destination);
      } catch (err) {
        // In cross-origin video restrictions, mediaElementSource may fail; fallback to normal video playback
        console.warn('[SFXSubMixer] Note: media element source routing bypassed:', err.message);
      }
    }

    /**
     * Preload .wav SFX assets from server or generate procedural buffers.
     */
    async preloadAssets() {
      const sounds = ['pop', 'click', 'whoosh', 'punch'];
      for (const sound of sounds) {
        try {
          const res = await fetch(`/assets/sfx/${sound}.wav`);
          if (res.ok) {
            const arrayBuf = await res.arrayBuffer();
            const decoded = await this.audioCtx.decodeAudioData(arrayBuf);
            this.buffers.set(sound, decoded);
          }
        } catch (err) {
          // Will use procedural synthesis fallback
        }
      }
    }

    /**
     * Synchronize sub-mixer schedule to a timeline payload.
     * 
     * @param {Object} timeline - Phase 1 / Phase 5 timeline
     */
    syncTimeline(timeline) {
      if (!timeline) {
        this.events = [];
        return;
      }

      this.events = (timeline.audio_sfx || []).map((ev, idx) => ({
        id: `sfx_${idx}_${ev.timestamp_ms}`,
        type: ev.type,
        timestamp_ms: ev.timestamp_ms,
        volume: ev.volume !== undefined ? ev.volume : 0.75,
      }));

      this.resetTracking();
    }

    /**
     * Reset triggered event history on seek, scrub, or preset change.
     */
    resetTracking() {
      this.playedEventIds.clear();
      this.unduck();
    }

    /**
     * Check and trigger SFX events synchronized with playback time.
     * 
     * @param {number} currentTimeSec - Playhead time in seconds
     * @param {boolean} isPaused - Video playback state
     */
    update(currentTimeSec, isPaused = false) {
      if (isPaused) {
        this.lastPlayheadSec = currentTimeSec;
        return;
      }

      this.initContext();
      if (!this.audioCtx) return;

      const currentMs = currentTimeSec * 1000.0;
      const prevMs = this.lastPlayheadSec * 1000.0;

      // Handle seeking backwards or forwards jumps (>300ms gap)
      if (Math.abs(currentMs - prevMs) > 300) {
        this.resetTracking();
      }

      // Detect and trigger any event in the current playhead window
      for (let i = 0; i < this.events.length; i++) {
        const ev = this.events[i];
        if (this.playedEventIds.has(ev.id)) continue;

        // Trigger if timestamp falls between prev frame and current frame
        if (ev.timestamp_ms >= prevMs - 40 && ev.timestamp_ms <= currentMs + 30) {
          this.triggerSound(ev.type, ev.volume);
          this.playedEventIds.add(ev.id);
        }
      }

      this.lastPlayheadSec = currentTimeSec;
    }

    /**
     * Trigger a sound effect either via pre-decoded buffer or procedural synthesis.
     * 
     * @param {string} soundType - 'pop' | 'click' | 'whoosh' | 'punch'
     * @param {number} volume - Output volume (0.0 - 1.0)
     */
    triggerSound(soundType, volume = 0.75) {
      if (!this.audioCtx) return;
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      this.applyDucking();

      // 1. Play pre-decoded buffer if available
      if (this.buffers.has(soundType)) {
        const buffer = this.buffers.get(soundType);
        const source = this.audioCtx.createBufferSource();
        const gain = this.audioCtx.createGain();

        source.buffer = buffer;
        gain.gain.setValueAtTime(volume, this.audioCtx.currentTime);

        source.connect(gain);
        gain.connect(this.masterGain);
        source.start();
        return;
      }

      // 2. Procedural Web Audio API Synthesis Fallback
      this.synthesizeProceduralSound(soundType, volume);
    }

    /**
     * Synthesize clean, organic procedural sound effect fallback.
     */
    synthesizeProceduralSound(type, volume) {
      const now = this.audioCtx.currentTime;

      if (type === 'pop') {
        // Fast pitch-dropped sine wave (780Hz -> 260Hz)
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(780, now);
        osc.frequency.exponentialRampToValueAtTime(260, now + 0.08);

        gain.gain.setValueAtTime(volume * 0.8, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.09);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.1);
      } else if (type === 'click') {
        // Snappy tactile click
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(1800, now);
        osc.frequency.exponentialRampToValueAtTime(400, now + 0.03);

        gain.gain.setValueAtTime(volume * 0.65, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.04);
      } else if (type === 'whoosh') {
        // Modulated frequency air rush
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(220, now);
        osc.frequency.linearRampToValueAtTime(540, now + 0.12);
        osc.frequency.linearRampToValueAtTime(200, now + 0.24);

        gain.gain.setValueAtTime(0.001, now);
        gain.gain.linearRampToValueAtTime(volume * 0.6, now + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.26);
      } else if (type === 'punch') {
        // Low-end impact thud
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(160, now);
        osc.frequency.exponentialRampToValueAtTime(55, now + 0.14);

        gain.gain.setValueAtTime(volume * 0.85, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);

        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.18);
      }
    }

    /**
     * Subtle vocal ducking: lowers background audio by ~15% for legibility.
     */
    applyDucking() {
      if (!this.videoGainNode || this.isDucking) return;
      this.isDucking = true;
      const now = this.audioCtx.currentTime;
      this.videoGainNode.gain.cancelScheduledValues(now);
      this.videoGainNode.gain.setValueAtTime(this.videoGainNode.gain.value, now);
      this.videoGainNode.gain.linearRampToValueAtTime(0.85, now + 0.03);

      setTimeout(() => this.unduck(), 160);
    }

    unduck() {
      if (!this.videoGainNode || !this.isDucking) return;
      this.isDucking = false;
      if (!this.audioCtx) return;
      const now = this.audioCtx.currentTime;
      this.videoGainNode.gain.cancelScheduledValues(now);
      this.videoGainNode.gain.setValueAtTime(this.videoGainNode.gain.value, now);
      this.videoGainNode.gain.linearRampToValueAtTime(1.0, now + 0.08);
    }

    dispose() {
      if (this.audioCtx && this.audioCtx.state !== 'closed') {
        this.audioCtx.close();
      }
      this.audioCtx = null;
      this.buffers.clear();
      this.events = [];
    }
  }

  return SFXSubMixer;
}));

