/**
 * Deterministic Spring-Damper Animation Subsystem & Kinetic Typography Generators (Phase 3).
 * 
 * Implements analytical closed-form damped harmonic oscillator physics:
 *   m * d^2x/dt^2 + c * dx/dt + k * x = 0
 * 
 * Evaluates exact displacement and velocity in O(1) time at any millisecond timestamp t
 * without frame-rate dependency. Guarantees 1:1 motion parity between browser rAF
 * and headless server frame rendering.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.KineticMotion = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ── Analytical Spring-Damper Physics Solver ───────────────────────────────────

  const SpringSolver = {
    /**
     * Compute displacement and velocity at elapsed time tSec using analytical closed-form solution.
     * 
     * @param {number} x0 - Starting value
     * @param {number} x1 - Target equilibrium value
     * @param {number} tSec - Elapsed time in seconds (t >= 0)
     * @param {Object} config - Spring configuration { tension, friction, mass, initialVelocity }
     * @returns {{ value: number, velocity: number }}
     */
    solve(x0, x1, tSec, config = {}) {
      if (tSec <= 0) return { value: x0, velocity: config.initialVelocity || 0 };

      const k = config.tension !== undefined ? config.tension : 240.0; // Stiffness
      const c = config.friction !== undefined ? config.friction : 16.0; // Damping
      const m = Math.max(0.001, config.mass !== undefined ? config.mass : 1.0); // Mass
      const v0 = config.initialVelocity || 0; // Initial velocity

      const D = x0 - x1; // Initial displacement from target
      if (Math.abs(D) < 1e-6 && Math.abs(v0) < 1e-6) {
        return { value: x1, velocity: 0 };
      }

      const w0 = Math.sqrt(k / m); // Natural angular frequency
      const zeta = c / (2 * Math.sqrt(m * k)); // Damping ratio

      // Underdamped (0 <= zeta < 1): Oscillatory decay (gives spring overshoot)
      if (zeta < 0.9999) {
        const wd = w0 * Math.sqrt(1 - zeta * zeta);
        const A = D;
        const B = (v0 + zeta * w0 * D) / wd;
        const decay = Math.exp(-zeta * w0 * tSec);

        const cosVal = Math.cos(wd * tSec);
        const sinVal = Math.sin(wd * tSec);

        const val = x1 + decay * (A * cosVal + B * sinVal);
        const vel = decay * ((B * wd - A * zeta * w0) * cosVal - (A * wd + B * zeta * w0) * sinVal);

        return { value: val, velocity: vel };
      }

      // Critically damped (zeta ~ 1): Fastest settling without overshoot
      if (Math.abs(zeta - 1.0) <= 0.0001) {
        const decay = Math.exp(-w0 * tSec);
        const A = D;
        const B = v0 + w0 * D;

        const val = x1 + decay * (A + B * tSec);
        const vel = decay * (B - w0 * (A + B * tSec));

        return { value: val, velocity: vel };
      }

      // Overdamped (zeta > 1): Sluggish non-oscillatory decay
      const sqrtZeta = Math.sqrt(zeta * zeta - 1);
      const mu1 = -w0 * (zeta - sqrtZeta);
      const mu2 = -w0 * (zeta + sqrtZeta);

      const C1 = (v0 - mu2 * D) / (mu1 - mu2);
      const C2 = D - C1;

      const exp1 = Math.exp(mu1 * tSec);
      const exp2 = Math.exp(mu2 * tSec);

      const val = x1 + C1 * exp1 + C2 * exp2;
      const vel = C1 * mu1 * exp1 + C2 * mu2 * exp2;

      return { value: val, velocity: vel };
    },

    /**
     * Helper to return just the evaluated value.
     */
    evaluate(x0, x1, tSec, config) {
      return this.solve(x0, x1, tSec, config).value;
    },
  };

  // ── Text Metrics Cache ────────────────────────────────────────────────────────

  const metricsCache = new Map();
  function measureTextCached(ctx, text, font) {
    const key = `${font}::${text}`;
    let width = metricsCache.get(key);
    if (width === undefined) {
      width = ctx.measureText(text).width;
      if (metricsCache.size > 2000) metricsCache.clear();
      metricsCache.set(key, width);
    }
    return width;
  }

  // ── Kinetic Motion Generators ─────────────────────────────────────────────────

  const KineticGenerators = {
    /**
     * 1. Pop / Bounce Generator
     * Spring-driven scale overshoot paired with synchronized Y-axis translation on active word.
     */
    evaluatePopBounce(word, currentMs, config = {}, scale = 1.0) {
      const springConfig = {
        tension: config.tension !== undefined ? config.tension : 260.0,
        friction: config.friction !== undefined ? config.friction : 14.0,
        mass: config.mass !== undefined ? config.mass : 1.0,
      };

      const startMs = word.start_ms;
      const endMs = word.end_ms;
      const targetScale = word.highlight ? 1.22 : 1.15;
      const bounceDistance = Math.max(4, 8 * scale);

      // (a) Upcoming
      if (currentMs < startMs) {
        return {
          scaleX: 1.0,
          scaleY: 1.0,
          translateY: 0.0,
          opacity: 0.70,
          isActive: false,
          isSpoken: false,
        };
      }

      // (b) Active Speaking Window
      if (currentMs >= startMs && currentMs < endMs) {
        const tSec = (currentMs - startMs) / 1000.0;

        // Spring scale from 1.0 to targetScale (with overshoot peak)
        const scaleVal = SpringSolver.evaluate(1.0, targetScale, tSec, springConfig);

        // Synchronized Y-axis pop: punch up with spring overshoot, settle slightly elevated
        const ySpring = SpringSolver.evaluate(bounceDistance, -bounceDistance * 0.4, tSec, springConfig);

        return {
          scaleX: scaleVal,
          scaleY: scaleVal,
          translateY: ySpring,
          opacity: 1.0,
          isActive: true,
          isSpoken: false,
        };
      }

      // (c) Post-Speaking Window (smoothly settle back to resting state 1.0)
      const tOutSec = (currentMs - endMs) / 1000.0;
      if (tOutSec < 0.35) {
        const scaleVal = SpringSolver.evaluate(targetScale, 1.0, tOutSec, { tension: 220, friction: 18, mass: 1.0 });
        const ySpring = SpringSolver.evaluate(-bounceDistance * 0.4, 0, tOutSec, { tension: 220, friction: 18, mass: 1.0 });
        return {
          scaleX: scaleVal,
          scaleY: scaleVal,
          translateY: ySpring,
          opacity: 1.0,
          isActive: false,
          isSpoken: true,
        };
      }

      return {
        scaleX: 1.0,
        scaleY: 1.0,
        translateY: 0.0,
        opacity: 1.0,
        isActive: false,
        isSpoken: true,
      };
    },

    /**
     * 2. Slide-Up Word Wave Generator
     * Progressive staggered entry and active wave crest effect across words in the phrase.
     */
    evaluateWordWave(phrase, wordIndex, currentMs, config = {}, scale = 1.0) {
      const springConfig = {
        tension: config.tension !== undefined ? config.tension : 220.0,
        friction: config.friction !== undefined ? config.friction : 18.0,
        mass: config.mass !== undefined ? config.mass : 1.0,
      };

      const words = phrase.words || [];
      const word = words[wordIndex];
      if (!word) return { scaleX: 1, scaleY: 1, translateY: 0, opacity: 1, isActive: false };

      const slideDist = Math.max(16, 28 * scale);
      const phraseStartMs = phrase.start_ms;
      const staggerDelayMs = 60; // 60ms stagger per word in phrase
      const wordEntryMs = phraseStartMs + wordIndex * staggerDelayMs;

      // Staggered Slide-Up Entry
      let entryY = 0;
      let opacity = 1.0;
      let baseScale = 1.0;

      if (currentMs < wordEntryMs) {
        return {
          scaleX: 0.85,
          scaleY: 0.85,
          translateY: slideDist,
          opacity: 0.0,
          isActive: false,
          isSpoken: false,
        };
      }

      const tEntrySec = (currentMs - wordEntryMs) / 1000.0;
      const entrySpring = SpringSolver.evaluate(0.0, 1.0, tEntrySec, springConfig);
      entryY = slideDist * (1.0 - Math.min(1.0, entrySpring));
      opacity = Math.min(1.0, Math.max(0.0, entrySpring));
      baseScale = 0.88 + 0.12 * Math.min(1.0, entrySpring);

      // Active Wave Crest on currently spoken word
      const isActive = currentMs >= word.start_ms && currentMs < word.end_ms;
      let waveY = 0;
      let waveScale = 1.0;

      if (isActive) {
        const tWaveSec = (currentMs - word.start_ms) / 1000.0;
        const crestSpring = SpringSolver.evaluate(0.0, 1.0, tWaveSec, { tension: 280, friction: 15, mass: 1.0 });
        waveY = -Math.max(6, 12 * scale) * crestSpring;
        waveScale = 1.0 + 0.16 * crestSpring;
      } else if (currentMs >= word.end_ms) {
        const tSettleSec = (currentMs - word.end_ms) / 1000.0;
        if (tSettleSec < 0.3) {
          const settleSpring = SpringSolver.evaluate(1.0, 0.0, tSettleSec, springConfig);
          waveY = -Math.max(6, 12 * scale) * settleSpring;
          waveScale = 1.0 + 0.16 * settleSpring;
        }
      }

      const finalScale = baseScale * waveScale;
      const finalY = entryY + waveY;

      return {
        scaleX: finalScale,
        scaleY: finalScale,
        translateY: finalY,
        opacity: opacity,
        isActive: isActive,
        isSpoken: currentMs >= word.end_ms,
      };
    },

    /**
     * 3. Elastic Pill Glider Generator
     * Continuous background rounded pill that dynamically interpolates its width, height,
     * and center coordinates between consecutive active words with elastic stretch and squash.
     */
    evaluatePillGlider(phrase, currentMs, wordBoxes, config = {}, scale = 1.0) {
      if (!wordBoxes || wordBoxes.length === 0) return null;

      const springConfig = {
        tension: config.tension !== undefined ? config.tension : 200.0,
        friction: config.friction !== undefined ? config.friction : 18.0,
        mass: config.mass !== undefined ? config.mass : 1.0,
      };

      const words = phrase.words || [];
      let activeIdx = words.findIndex((w) => currentMs >= w.start_ms && currentMs < w.end_ms);
      if (activeIdx === -1) {
        // Between words or before phrase starts
        if (currentMs < words[0].start_ms) activeIdx = 0;
        else activeIdx = words.length - 1;
      }

      const prevIdx = Math.max(0, activeIdx - 1);
      const currBox = wordBoxes[activeIdx];
      const prevBox = wordBoxes[prevIdx];

      if (!currBox) return null;

      const padX = Math.max(12, 16 * scale);
      const padY = Math.max(6, 9 * scale);

      // Target bounds
      const targetW = currBox.width + padX * 2;
      const targetH = currBox.height + padY * 2;
      const targetCX = currBox.x + currBox.width / 2;
      const targetCY = currBox.y + currBox.height / 2;

      // Previous bounds
      const prevW = prevBox ? prevBox.width + padX * 2 : targetW;
      const prevCX = prevBox ? prevBox.x + prevBox.width / 2 : targetCX;

      const curWord = words[activeIdx];
      const tSec = Math.max(0, (currentMs - curWord.start_ms) / 1000.0);

      // Interpolate center X with spring
      const springResult = SpringSolver.solve(prevCX, targetCX, tSec, springConfig);
      const currentCX = springResult.value;
      const velocity = springResult.velocity;

      // Base width interpolation
      const baseW = prevW + (targetW - prevW) * Math.min(1.0, Math.max(0.0, tSec * 6));

      // Elastic stretch: velocity horizontally elongates the pill during motion
      const stretch = Math.min(targetW * 0.35, Math.abs(velocity) * 0.05 * scale);
      const finalW = baseW + stretch;
      const finalH = targetH;

      return {
        x: currentCX - finalW / 2,
        y: targetCY - finalH / 2,
        width: finalW,
        height: finalH,
        radius: finalH * 0.44,
      };
    },
  };

  return {
    SpringSolver,
    KineticGenerators,
    measureTextCached,
  };
}));

