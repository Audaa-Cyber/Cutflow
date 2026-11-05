/**
 * Deterministic Font Loader & Metrics Synchronization (Phase 4).
 * 
 * Preloads and verifies browser font readiness via the FontFace / document.fonts API
 * before initial canvas draw to eliminate FOYT (Flash of Unstyled Text) and
 * guarantee 1:1 kerning and metrics parity with the server-side Skia renderer.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.FontLoader = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const CURATED_FONTS = [
    { family: 'Montserrat', weights: ['400', '700'] },
    { family: 'Merriweather', weights: ['400', '700'] },
    { family: 'JetBrains Mono', weights: ['400', '700'] },
    { family: 'Anton', weights: ['400'] },
    { family: 'Bebas Neue', weights: ['400'] },
    { family: 'Komika Axis', weights: ['700'] },
    { family: 'Syne', weights: ['700'] },
    { family: 'The Bold Font', weights: ['700'] },
  ];

  const loadedCache = new Set();

  const FontLoader = {
    CURATED_FONTS,

    /**
     * Ensure a specific font family is fully loaded and ready in the document.
     * 
     * @param {string} fontFamily
     * @returns {Promise<boolean>}
     */
    async ensureFont(fontFamily) {
      if (!fontFamily) return true;
      if (loadedCache.has(fontFamily)) return true;

      if (typeof document === 'undefined' || !document.fonts || !document.fonts.load) {
        // Headless Node environment handles font registration synchronously via Skia
        loadedCache.add(fontFamily);
        return true;
      }

      try {
        const def = CURATED_FONTS.find((f) => f.family.toLowerCase() === fontFamily.toLowerCase());
        const weights = def ? def.weights : ['400', '700'];

        const loadPromises = weights.map((w) =>
          document.fonts.load(`${w} 48px "${fontFamily}"`)
        );
        await Promise.all(loadPromises);
        await document.fonts.ready;
        loadedCache.add(fontFamily);
        return true;
      } catch (err) {
        console.warn(`[FontLoader] Warning: could not pre-verify font "${fontFamily}":`, err);
        return false;
      }
    },

    /**
     * Preload all curated display fonts upfront to guarantee zero-latency switching.
     * 
     * @returns {Promise<void>}
     */
    async preloadAll() {
      if (typeof document === 'undefined' || !document.fonts) return;

      const promises = CURATED_FONTS.map((def) => this.ensureFont(def.family));
      await Promise.allSettled(promises);
    },

    /**
     * Check if a font is marked as ready.
     * 
     * @param {string} fontFamily
     * @returns {boolean}
     */
    isFontReady(fontFamily) {
      if (!fontFamily) return true;
      if (loadedCache.has(fontFamily)) return true;
      if (typeof document !== 'undefined' && document.fonts && document.fonts.check) {
        return document.fonts.check(`700 48px "${fontFamily}"`) || document.fonts.check(`400 48px "${fontFamily}"`);
      }
      return false;
    },
  };

  return FontLoader;
}));

