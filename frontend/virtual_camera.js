/**
 * Dynamic Virtual Camera Controller (Phase 5).
 * 
 * Provides time-indexed virtual camera transformation matrices (scale, translation,
 * rotation, motion blur) for camera punches and whip-pan transitions.
 * Isomorphic: Shared between browser Canvas preview and server-side Skia frame exporter.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    let km = null;
    try {
      km = require('./kinetic_motion.js');
    } catch (e) {
      // Ignore
    }
    module.exports = factory(km);
  } else {
    root.VirtualCamera = factory(root.KineticMotion);
  }
}(typeof self !== 'undefined' ? self : this, function (KineticMotionModule) {
  'use strict';

  function getKineticMotion() {
    if (KineticMotionModule) return KineticMotionModule;
    if (typeof window !== 'undefined' && window.KineticMotion) return window.KineticMotion;
    if (typeof globalThis !== 'undefined' && globalThis.KineticMotion) return globalThis.KineticMotion;
    return null;
  }

  const VirtualCamera = {
    /**
     * Evaluate camera transform state at current millisecond timestamp.
     * 
     * @param {Array} cameraEvents - List of camera punch and whip-pan events
     * @param {number} currentMs - Playback timestamp in ms
     * @param {number} width - Canvas width in px
     * @param {number} height - Canvas height in px
     * @returns {Object} Camera transform state
     */
    evaluateCamera(cameraEvents, currentMs, width, height) {
      const defaultState = {
        scale: 1.0,
        translateX: 0.0,
        translateY: 0.0,
        rotation: 0.0,
        motionBlur: 0.0,
        isPunch: false,
        isWhipPan: false,
      };

      if (!cameraEvents || !cameraEvents.length) {
        return defaultState;
      }

      const km = getKineticMotion();
      let scale = 1.0;
      let translateX = 0.0;
      let translateY = 0.0;
      let rotation = 0.0;
      let motionBlur = 0.0;
      let isPunch = false;
      let isWhipPan = false;

      for (let i = 0; i < cameraEvents.length; i++) {
        const ev = cameraEvents[i];

        // ── Camera Punch Zooms (Scale Overshoot & Snap-back) ───────────────────
        if (ev.type === 'punch') {
          const startMs = ev.start_ms;
          const endMs = ev.end_ms;
          const targetScale = ev.scale || 1.12;

          if (currentMs >= startMs && currentMs <= endMs + 80) {
            isPunch = true;
            const tSec = (currentMs - startMs) / 1000.0;

            if (km && km.SpringSolver) {
              // Rapid spring punch from 1.0x up to 1.12x
              const spring = km.SpringSolver.solve(1.0, targetScale, tSec, {
                tension: 320.0,
                friction: 20.0,
                mass: 1.0,
              });
              scale = Math.max(scale, spring.value);

              // Subtle dynamic rotation wobble (-0.6deg to +0.6deg)
              const rotSpring = km.SpringSolver.solve(0.0, 0.75, tSec, {
                tension: 260.0,
                friction: 18.0,
                mass: 1.0,
              });
              rotation += rotSpring.value * (i % 2 === 0 ? 1 : -1);
            } else {
              scale = Math.max(scale, targetScale);
            }

            // Ease back down to 1.0 near word boundary
            if (currentMs > endMs) {
              const easeDown = (currentMs - endMs) / 80.0;
              scale = targetScale + (1.0 - targetScale) * easeDown;
              rotation *= (1.0 - easeDown);
            }
          }
        }

        // ── Whip-Pan Transitions (Directional Displacement & Motion Blur) ──────
        else if (ev.type === 'whip_pan') {
          const startMs = ev.start_ms;
          const durationMs = ev.duration_ms || 180;
          const endMs = startMs + durationMs;

          if (currentMs >= startMs && currentMs <= endMs) {
            isWhipPan = true;
            const progress = (currentMs - startMs) / durationMs;
            const dir = ev.direction || 1;
            const maxDisp = (ev.displacement_px || 44.0) * (width / 1080.0);

            // Sine bell displacement curve: accelerates in, snaps across, settles out
            const bell = Math.sin(progress * Math.PI);
            translateX += dir * maxDisp * bell;

            // Velocity-based motion blur factor (highest at peak transition)
            motionBlur = Math.max(motionBlur, bell * 0.85);

            // Slight dynamic tilt during whip
            rotation += dir * bell * 1.2;
          }
        }
      }

      return {
        scale: Math.max(0.5, Math.min(2.0, scale)),
        translateX,
        translateY,
        rotation,
        motionBlur,
        isPunch,
        isWhipPan,
      };
    },

    /**
     * Apply virtual camera transformation matrix to the canvas 2D context.
     * 
     * @param {CanvasRenderingContext2D} ctx
     * @param {Object} cameraState
     * @param {number} width
     * @param {number} height
     */
    applyToContext(ctx, cameraState, width, height) {
      if (!ctx || !cameraState) return;

      const cx = width / 2;
      const cy = height / 2;

      ctx.translate(cx + cameraState.translateX, cy + cameraState.translateY);
      if (cameraState.rotation !== 0) {
        ctx.rotate((cameraState.rotation * Math.PI) / 180.0);
      }
      if (cameraState.scale !== 1.0) {
        ctx.scale(cameraState.scale, cameraState.scale);
      }
      ctx.translate(-cx, -cy);
    },

    /**
     * Simulate directional motion blur pass during whip-pan movements.
     * 
     * @param {CanvasRenderingContext2D} ctx
     * @param {Object} cameraState
     * @param {number} width
     * @param {number} height
     */
    applyMotionBlur(ctx, cameraState, width, height) {
      if (!ctx || !cameraState || cameraState.motionBlur <= 0.05) return;

      // In browser or Skia, simulated by drawing a low-opacity shifted pass
      ctx.save();
      ctx.globalAlpha = cameraState.motionBlur * 0.28;
      const shiftX = (cameraState.translateX > 0 ? 8 : -8) * cameraState.motionBlur;
      ctx.drawImage(ctx.canvas, shiftX, 0);
      ctx.restore();
    },
  };

  return VirtualCamera;
}));

