/**
 * Spatial Sticker Compositor Layer (Phase 5).
 * 
 * Anchors dynamic vector SVG/Lottie badges to word-level bounding boxes and
 * animates them using the Phase 3 deterministic spring-damper physics solver.
 * Shared between browser WYSIWYG canvas and server-side Skia renderer.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    let km = null;
    let canvasPkg = null;
    try {
      km = require('./kinetic_motion.js');
      canvasPkg = require('@napi-rs/canvas');
    } catch (e) {
      // Ignore
    }
    module.exports = factory(km, canvasPkg);
  } else {
    root.StickerCompositor = factory(root.KineticMotion, null);
  }
}(typeof self !== 'undefined' ? self : this, function (KineticMotionModule, CanvasPkg) {
  'use strict';

  function getKineticMotion() {
    if (KineticMotionModule) return KineticMotionModule;
    if (typeof window !== 'undefined' && window.KineticMotion) return window.KineticMotion;
    if (typeof globalThis !== 'undefined' && globalThis.KineticMotion) return globalThis.KineticMotion;
    return null;
  }

  const imageCache = new Map();

  const StickerCompositor = {
    /**
     * Get or load an SVG image asset for a sticker.
     * 
     * @param {string} category
     * @param {string} [assetName]
     * @returns {HTMLImageElement|Object|null}
     */
    getImage(category, assetName) {
      const filename = assetName || `${category}.svg`;
      if (imageCache.has(filename)) {
        return imageCache.get(filename);
      }

      // 1. Browser environment: DOM Image
      if (typeof Image !== 'undefined' && typeof window !== 'undefined') {
        const img = new Image();
        img.src = `/assets/stickers/${filename}`;
        imageCache.set(filename, img);
        return img;
      }

      // 2. Node.js environment: @napi-rs/canvas loadImage
      if (CanvasPkg && typeof CanvasPkg.loadImage === 'function') {
        try {
          const fs = require('fs');
          const path = require('path');
          const stickerPath = path.resolve(__dirname, '..', 'backend', 'assets', 'stickers', filename);
          if (fs.existsSync(stickerPath)) {
            const buf = fs.readFileSync(stickerPath);
            const img = CanvasPkg.loadImage(buf);
            imageCache.set(filename, img);
            return img;
          }
        } catch (err) {
          // Fallback or ignore
        }
      }

      return null;
    },

    /**
     * Preload all default sticker assets in Node Skia or browser environment.
     * 
     * @returns {Promise<void>}
     */
    async preloadAll() {
      const categories = [
        'fire', 'rocket', 'money', 'brain', 'warning', 'lightning',
        'trophy', 'chart_up', 'target', 'skull', 'heart', 'crown'
      ];

      if (typeof window !== 'undefined') {
        categories.forEach(cat => this.getImage(cat));
        return;
      }

      if (CanvasPkg && typeof CanvasPkg.loadImage === 'function') {
        const fs = require('fs');
        const path = require('path');
        const stickerDir = path.resolve(__dirname, '..', 'backend', 'assets', 'stickers');
        for (const cat of categories) {
          const fullPath = path.join(stickerDir, `${cat}.svg`);
          if (fs.existsSync(fullPath)) {
            try {
              const img = await CanvasPkg.loadImage(fullPath);
              imageCache.set(`${cat}.svg`, img);
            } catch (err) {
              // Ignore
            }
          }
        }
      }
    },

    /**
     * Evaluate spatial sticker transform (scale, translation, tilt, opacity) using spring physics.
     * 
     * @param {Object} sticker - Sticker event descriptor
     * @param {number} currentMs - Current playback timestamp in ms
     * @param {Object} springConfig - Spring tension, friction, mass
     * @returns {Object} { active, scale, tilt, opacity, offsetY }
     */
    evaluateStickerMotion(sticker, currentMs, springConfig = {}) {
      const startMs = sticker.start_ms;
      const endMs = sticker.end_ms;
      const km = getKineticMotion();

      // Active visibility window: starts at start_ms, lingers slightly past end_ms for settle
      const exitDurationMs = 120;
      if (currentMs < startMs || currentMs > endMs + exitDurationMs) {
        return { active: false, scale: 0, tilt: 0, opacity: 0, offsetY: 0 };
      }

      const cfg = {
        tension: springConfig.tension || 340.0,
        friction: springConfig.friction || 18.0,
        mass: springConfig.mass || 1.0,
      };

      const tEntrySec = Math.max(0, (currentMs - startMs) / 1000.0);
      let scale = 1.0;
      let opacity = 1.0;
      let offsetY = 0.0;

      if (km && km.SpringSolver) {
        // Pop-in spring from scale 0.0 to 1.0 with overshoot (~1.25)
        const spring = km.SpringSolver.solve(0.0, 1.0, tEntrySec, cfg);
        scale = Math.max(0, spring.value);

        // Elastic vertical bounce from -24px up into anchor position
        const ySpring = km.SpringSolver.solve(-20.0, 0.0, tEntrySec, cfg);
        offsetY = ySpring.value;
      } else {
        // Fallback linear interpolation
        scale = Math.min(1.0, tEntrySec * 6.0);
      }

      // Smooth exit dissolve when currentMs > endMs
      if (currentMs > endMs) {
        const exitT = (currentMs - endMs) / exitDurationMs;
        opacity = Math.max(0.0, 1.0 - exitT);
        scale *= (1.0 - exitT * 0.25);
      }

      const targetTilt = sticker.tilt_deg !== undefined ? sticker.tilt_deg : -6.0;
      // Gentle harmonic tilt wobble
      const tiltWobble = Math.sin(tEntrySec * 16.0) * Math.exp(-tEntrySec * 6.0) * 4.0;
      const tilt = targetTilt + tiltWobble;

      return {
        active: true,
        scale,
        tilt,
        opacity,
        offsetY,
      };
    },

    /**
     * Render all active spatial stickers anchored to word bounding boxes.
     * 
     * @param {CanvasRenderingContext2D} ctx - 2D context
     * @param {Array} stickers - Timeline stickers array
     * @param {Array} wordBoxes - Rendered word layout boxes
     * @param {number} currentMs - Timestamp in ms
     * @param {number} renderScale - Resolution scaling factor
     * @param {Object} [springConfig] - Optional physics overrides
     */
    renderActiveStickers(ctx, stickers, wordBoxes, currentMs, renderScale = 1.0, springConfig = {}) {
      if (!ctx || !stickers || !stickers.length || !wordBoxes || !wordBoxes.length) {
        return;
      }

      for (let i = 0; i < stickers.length; i++) {
        const sticker = stickers[i];
        // Match sticker to the corresponding word box on screen
        const targetBox = wordBoxes.find(b => b.id === sticker.word_id || b.word === sticker.word);
        if (!targetBox) continue;

        const motion = this.evaluateStickerMotion(sticker, currentMs, springConfig);
        if (!motion.active || motion.scale <= 0.001 || motion.opacity <= 0.001) {
          continue;
        }

        const img = this.getImage(sticker.category, sticker.asset);
        if (!img) continue;

        // Size sticker proportionally to word font size
        const baseSize = Math.max(36, targetBox.height * 1.08);
        const finalW = baseSize * motion.scale * (sticker.scale || 1.0);
        const finalH = finalW;

        // Anchor horizontally centered, vertically floating right above word cap-height
        const anchorX = targetBox.x + targetBox.width / 2 + (sticker.offset_x || 0) * renderScale;
        const anchorY = targetBox.y - baseSize * 0.44 + (sticker.offset_y || 0) * renderScale + motion.offsetY;

        ctx.save();
        ctx.translate(anchorX, anchorY);
        ctx.rotate((motion.tilt * Math.PI) / 180.0);
        ctx.globalAlpha = motion.opacity;

        try {
          ctx.drawImage(img, -finalW / 2, -finalH / 2, finalW, finalH);
        } catch (e) {
          // If image is still decoding or unavailable, fail gracefully
        }

        ctx.restore();
      }
    },
  };

  return StickerCompositor;
}));

