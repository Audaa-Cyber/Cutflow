/**
 * Shared Caption Canvas Renderer Core (Phase 2).
 * 
 * Isomorphic 2D canvas rendering engine shared between browser WYSIWYG
 * interactive preview and server-side headless Skia export pipeline.
 * Guarantees strict 1:1 pixel parity, identical text metrics, and synchronized frame rendering.
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    // Node.js / CommonJS
    let km = null;
    let sc = null;
    let vc = null;
    try {
      km = require('./kinetic_motion.js');
      sc = require('./sticker_compositor.js');
      vc = require('./virtual_camera.js');
    } catch (e) {
      // Ignore
    }
    module.exports = factory(km, sc, vc);
  } else {
    // Browser Global
    root.CaptionCanvasRenderer = factory(root.KineticMotion, root.StickerCompositor, root.VirtualCamera);
  }
}(typeof self !== 'undefined' ? self : this, function (KineticMotionModule, StickerCompositorModule, VirtualCameraModule) {
  'use strict';

  function getKineticMotion() {
    if (KineticMotionModule) return KineticMotionModule;
    if (typeof window !== 'undefined' && window.KineticMotion) return window.KineticMotion;
    if (typeof globalThis !== 'undefined' && globalThis.KineticMotion) return globalThis.KineticMotion;
    return null;
  }

  function getStickerCompositor() {
    if (StickerCompositorModule) return StickerCompositorModule;
    if (typeof window !== 'undefined' && window.StickerCompositor) return window.StickerCompositor;
    if (typeof globalThis !== 'undefined' && globalThis.StickerCompositor) return globalThis.StickerCompositor;
    return null;
  }

  function getVirtualCamera() {
    if (VirtualCameraModule) return VirtualCameraModule;
    if (typeof window !== 'undefined' && window.VirtualCamera) return window.VirtualCamera;
    if (typeof globalThis !== 'undefined' && globalThis.VirtualCamera) return globalThis.VirtualCamera;
    return null;
  }

  function drawRoundRect(ctx, x, y, width, height, radius) {
    radius = Math.min(Math.min(width / 2, height / 2), Math.max(0, radius));
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }

  function parseHexAlpha(hex, defaultAlpha) {
    if (!hex) return 'rgba(255, 255, 255, 1)';
    if (hex.startsWith('rgba')) return hex;
    let clean = hex.replace('#', '');
    if (clean.length === 6) {
      const r = parseInt(clean.substring(0, 2), 16);
      const g = parseInt(clean.substring(2, 4), 16);
      const b = parseInt(clean.substring(4, 6), 16);
      return `rgba(${r}, ${g}, ${b}, ${defaultAlpha !== undefined ? defaultAlpha : 1})`;
    }
    return hex;
  }

  function measureText(ctx, text, font) {
    const km = getKineticMotion();
    if (km && typeof km.measureTextCached === 'function') {
      return km.measureTextCached(ctx, text, font);
    }
    return ctx.measureText(text).width;
  }

  const CaptionCanvasRenderer = {
    /**
     * Render a single synchronized caption frame at `currentTimeSec`.
     * 
     * @param {CanvasRenderingContext2D} ctx - 2D rendering context
     * @param {Object} timeline - Phase 1 KineticTimeline payload
     * @param {number} currentTimeSec - Playhead time in seconds
     * @param {number} width - Render target canvas width in px
     * @param {number} height - Render target canvas height in px
     * @param {Object} options - Optional rendering controls
     * @returns {Object} Render metrics and word bounding boxes for WYSIWYG interactions
     */
    renderFrame(ctx, timeline, currentTimeSec, width, height, options = {}) {
      if (!ctx || !timeline) return { wordBoxes: [] };

      const currentMs = Math.round(currentTimeSec * 1000);
      const meta = timeline.styling_metadata || {};
      const colors = meta.colors || {
        primary: '#ffffff',
        accent: '#ffff00',
        upcoming: '#999999',
        outline: '#141414',
        fill: '#ffffff',
        fill_text: '#000000',
      };

      // Relative resolution scaling factor based on base 1080p
      const baseDim = 1080;
      const scale = width / baseDim;

      // Clear the frame buffer
      ctx.clearRect(0, 0, width, height);

      ctx.save();

      // (Phase 5) Virtual Camera Transformation
      const vc = getVirtualCamera();
      let cameraState = null;
      if (vc && timeline.camera_events && timeline.camera_events.length) {
        cameraState = vc.evaluateCamera(timeline.camera_events, currentMs, width, height);
        vc.applyToContext(ctx, cameraState, width, height);
      }

      // (0) Frame Treatments (Letterbox / Polaroid / Grid / Rules)
      const frameType = meta.frame || 'none';
      if (frameType === 'letterbox') {
        const barH = height * 0.12;
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, width, barH);
        ctx.fillRect(0, height - barH, width, barH);
      } else if (frameType === 'rules') {
        ctx.strokeStyle = parseHexAlpha(colors.outline, 0.4);
        ctx.lineWidth = Math.max(2, 2.5 * scale);
        ctx.beginPath();
        ctx.moveTo(width * 0.14, height * 0.055);
        ctx.lineTo(width * 0.86, height * 0.055);
        ctx.moveTo(width * 0.14, height * 0.945);
        ctx.lineTo(width * 0.86, height * 0.945);
        ctx.stroke();
      }

      // (1) Locate active phrase & active word token
      const phrases = timeline.phrases || [];
      let activePhrase = null;
      let activePhraseIdx = -1;

      for (let i = 0; i < phrases.length; i++) {
        const p = phrases[i];
        // Allow brief visual hold of 180ms after phrase ends for natural reading flow
        if (currentMs >= p.start_ms && currentMs <= (p.end_ms + 180)) {
          activePhrase = p;
          activePhraseIdx = i;
          break;
        }
      }

      // If between phrases but within clip boundaries, find nearest previous phrase within 400ms
      if (!activePhrase && phrases.length > 0) {
        for (let i = phrases.length - 1; i >= 0; i--) {
          if (currentMs >= phrases[i].start_ms && currentMs - phrases[i].end_ms <= 400) {
            activePhrase = phrases[i];
            activePhraseIdx = i;
            break;
          }
        }
      }

      // (2) Render Hook Headline (if configured)
      const headlineType = meta.headline || 'none';
      const headlineText = activePhrase?.headline || options.headlineText || '';
      if (headlineType !== 'none' && headlineText.trim()) {
        const hFont = meta.headline_font || meta.font || 'Montserrat';
        const hSize = Math.max(18, (meta.headline_size_px || 56) * scale);
        ctx.font = `700 ${hSize}px "${hFont}", sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        const hY = height * 0.06;
        const hX = width / 2;
        const hTextFormatted = meta.uppercase ? headlineText.toUpperCase() : headlineText;
        const hMetrics = ctx.measureText(hTextFormatted);

        if (headlineType === 'banner') {
          const padX = hSize * 0.6;
          const padY = hSize * 0.28;
          const bannerW = hMetrics.width + padX * 2;
          const bannerH = hSize + padY * 2;
          ctx.fillStyle = colors.accent;
          drawRoundRect(ctx, hX - bannerW / 2, hY - padY, bannerW, bannerH, bannerH * 0.35);
          ctx.fill();

          ctx.fillStyle = '#141414';
          ctx.fillText(hTextFormatted, hX, hY);
        } else if (headlineType === 'badge') {
          const padX = hSize * 0.45;
          const padY = hSize * 0.2;
          const badgeW = hMetrics.width + padX * 2;
          const badgeH = hSize + padY * 2;
          ctx.fillStyle = '#ffffff';
          drawRoundRect(ctx, hX - badgeW / 2, hY - padY, badgeW, badgeH, 6 * scale);
          ctx.fill();

          ctx.fillStyle = '#141414';
          ctx.fillText(hTextFormatted, hX, hY);
        } else {
          // Plain / Kicker / Serif
          ctx.lineWidth = Math.max(2, 3.5 * scale);
          ctx.strokeStyle = colors.outline || '#141414';
          ctx.strokeText(hTextFormatted, hX, hY);
          ctx.fillStyle = colors.primary || '#ffffff';
          ctx.fillText(hTextFormatted, hX, hY);
        }
      }

      if (!activePhrase) return { wordBoxes: [] };

      // (3) Measure & layout caption words
      const words = activePhrase.words || [];
      if (words.length === 0) return { wordBoxes: [] };

      const fontName = meta.font || 'Montserrat';
      const fontSize = Math.max(20, (meta.font_size_px || 86) * scale);
      ctx.font = `700 ${fontSize}px "${fontName}", sans-serif`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';

      const spaceWidth = measureText(ctx, ' ', ctx.font);
      const wordLayouts = [];
      let totalLineWidth = 0;

      for (let i = 0; i < words.length; i++) {
        const w = words[i];
        const displayText = meta.uppercase ? w.text.toUpperCase() : w.text;
        const wWidth = measureText(ctx, displayText, ctx.font);
        wordLayouts.push({
          word: w,
          text: displayText,
          width: wWidth,
          index: i,
        });
        totalLineWidth += wWidth;
        if (i < words.length - 1) totalLineWidth += spaceWidth;
      }

      // Calculate baseline anchor coordinates
      const zone = meta.zone || 'lower';
      let anchorY = height * 0.82; // Default lower third
      if (zone === 'center') anchorY = height * 0.58;
      else if (zone === 'upper') anchorY = height * 0.28;
      else if (zone === 'letterbox') anchorY = height - (height * 0.12 * 0.5);

      const startX = (width - totalLineWidth) / 2;
      let curX = startX;
      const wordBoxes = [];

      // Precompute word layout boxes for kinetic solvers (e.g. pill glider)
      let tempX = startX;
      const precomputedBoxes = [];
      for (let i = 0; i < wordLayouts.length; i++) {
        const layout = wordLayouts[i];
        precomputedBoxes.push({
          x: tempX,
          y: anchorY - fontSize / 2,
          width: layout.width,
          height: fontSize,
          index: i,
          word: layout.word,
        });
        tempX += layout.width + spaceWidth;
      }

      const km = getKineticMotion();
      const kineticMode = meta.kinetic_mode || (meta.active_pop ? 'pop' : 'none');
      const springConfig = meta.spring_physics || {};

      // (4) Render Container Backing Pill or Dynamic Elastic Glider
      const captionBox = meta.caption_box || 'none';

      if (kineticMode === 'glider' && km && km.KineticGenerators) {
        // If caption_box is pill, render soft track background
        if (captionBox === 'pill') {
          const padX = fontSize * 0.42;
          const padY = fontSize * 0.28;
          const pillW = totalLineWidth + padX * 2;
          const pillH = fontSize + padY * 2;
          const pillX = curX - padX;
          const pillY = anchorY - pillH / 2;

          ctx.fillStyle = parseHexAlpha(colors.fill, 0.22);
          drawRoundRect(ctx, pillX, pillY, pillW, pillH, pillH * 0.46);
          ctx.fill();
        }

        // Evaluate continuous spring-interpolated elastic pill
        const glider = km.KineticGenerators.evaluatePillGlider(
          activePhrase,
          currentMs,
          precomputedBoxes,
          springConfig,
          scale
        );

        if (glider) {
          ctx.fillStyle = parseHexAlpha(colors.fill, 0.94);
          drawRoundRect(ctx, glider.x, glider.y, glider.width, glider.height, glider.radius);
          ctx.fill();
        }
      } else if (captionBox === 'pill') {
        const padX = fontSize * 0.42;
        const padY = fontSize * 0.28;
        const pillW = totalLineWidth + padX * 2;
        const pillH = fontSize + padY * 2;
        const pillX = curX - padX;
        const pillY = anchorY - pillH / 2;

        ctx.fillStyle = parseHexAlpha(colors.fill, 0.45);
        drawRoundRect(ctx, pillX, pillY, pillW, pillH, pillH * 0.46);
        ctx.fill();
      }

      // (5) Render Individual Words with Kinetic Physics
      const activeWordIdx = words.findIndex((w) => currentMs >= w.start_ms && currentMs < w.end_ms);

      for (let i = 0; i < wordLayouts.length; i++) {
        const layout = wordLayouts[i];
        const wToken = layout.word;
        const isSpoken = currentMs >= wToken.end_ms;
        const isActive = (i === activeWordIdx) || (activeWordIdx === -1 && i === 0 && currentMs < words[0].start_ms);
        const isUpcoming = currentMs < wToken.start_ms;

        const wX = curX;
        const wY = anchorY;
        const wW = layout.width;
        const wH = fontSize;

        // Store screen-space bounding box for interactive WYSIWYG editing
        wordBoxes.push({
          id: wToken.id,
          index: i,
          word: wToken.word,
          text: layout.text,
          start: wToken.start,
          end: wToken.end,
          start_ms: wToken.start_ms,
          end_ms: wToken.end_ms,
          x: wX,
          y: wY - wH / 2,
          width: wW,
          height: wH,
          isActive: isActive,
        });

        // Evaluate time-indexed kinetic motion values
        let scaleX = 1.0;
        let scaleY = 1.0;
        let translateY = 0.0;
        let opacity = 1.0;

        if (km && km.KineticGenerators) {
          if (kineticMode === 'pop') {
            const motion = km.KineticGenerators.evaluatePopBounce(wToken, currentMs, springConfig, scale);
            scaleX = motion.scaleX;
            scaleY = motion.scaleY;
            translateY = motion.translateY;
            opacity = motion.opacity;
          } else if (kineticMode === 'wave') {
            const motion = km.KineticGenerators.evaluateWordWave(activePhrase, i, currentMs, springConfig, scale);
            scaleX = motion.scaleX;
            scaleY = motion.scaleY;
            translateY = motion.translateY;
            opacity = motion.opacity;
          } else if (kineticMode === 'glider') {
            if (isActive) {
              scaleX = 1.06;
              scaleY = 1.06;
            }
          }
        } else {
          // Fallback to Phase 2 pop if kinetic motion is not loaded
          if (isActive && meta.active_pop) {
            scaleX = 1.14;
            scaleY = 1.14;
          }
        }

        ctx.save();

        // Apply kinetic affine transformation & tilt centered on the word
        const centerX = wX + wW / 2;
        const centerY = wY;
        ctx.translate(centerX, centerY + translateY);
        if (meta.tilt_deg) {
          ctx.rotate((meta.tilt_deg * Math.PI) / 180);
        }
        ctx.scale(scaleX, scaleY);
        ctx.translate(-centerX, -centerY);
        ctx.globalAlpha = opacity;

        // Active Word Box / Underline / Marker Backings
        const activeDec = meta.active_decoration || 'accent';
        if (captionBox === 'per_word') {
          const bPadX = fontSize * 0.22;
          const bPadY = fontSize * 0.16;
          const badgeW = wW + bPadX * 2;
          const badgeH = wH + bPadY * 2;
          ctx.fillStyle = isActive ? colors.accent : colors.fill;
          drawRoundRect(ctx, wX - bPadX, wY - badgeH / 2, badgeW, badgeH, 6 * scale);
          ctx.fill();
        } else if (isActive && activeDec === 'marker') {
          const mPadX = fontSize * 0.16;
          const mPadY = fontSize * 0.12;
          ctx.fillStyle = parseHexAlpha(colors.accent, 0.40);
          drawRoundRect(ctx, wX - mPadX, wY - (wH + mPadY * 2) / 2, wW + mPadX * 2, wH + mPadY * 2, 4 * scale);
          ctx.fill();
        } else if (isActive && activeDec === 'underline') {
          const uH = Math.max(3, 4 * scale);
          const uY = wY + fontSize * 0.52;
          ctx.fillStyle = colors.accent;
          ctx.fillRect(wX, uY, wW, uH);
        }

        // Color & Typography Resolution
        let textColor = colors.primary;
        if (captionBox === 'per_word') {
          textColor = colors.fill_text || '#000000';
        } else if (kineticMode === 'glider' && isActive) {
          textColor = colors.fill_text || '#000000';
        } else if (isActive) {
          textColor = colors.accent;
        } else if (isUpcoming) {
          textColor = colors.upcoming;
        }

        // ── Phase 4 Multi-Pass Text Shader Pipeline ─────────────────────────────
        const shaderStack = meta.shader_stack || {};
        const outerStroke = shaderStack.outer_stroke;
        const innerStroke = shaderStack.inner_stroke;
        const shadowDef = shaderStack.shadow;
        const glowDef = shaderStack.glow;
        const activeGradient = shaderStack.active_gradient;
        const primaryGradient = shaderStack.primary_gradient;

        // Pass 1A: Wide Diffuse Neon / Ambient Bloom Glow
        if (isActive && glowDef && glowDef.blur > 0) {
          ctx.save();
          ctx.shadowColor = glowDef.color || colors.accent;
          ctx.shadowBlur = Math.max(4, glowDef.blur * scale);
          ctx.shadowOffsetX = 0;
          ctx.shadowOffsetY = 0;
          ctx.fillStyle = glowDef.color || colors.accent;
          ctx.fillText(layout.text, wX, wY);
          ctx.restore();
        }

        // Pass 1B: Tight Legibility Drop Shadow
        if (shadowDef && (shadowDef.blur > 0 || shadowDef.y > 0)) {
          ctx.save();
          ctx.shadowColor = shadowDef.color || 'rgba(0, 0, 0, 0.85)';
          ctx.shadowBlur = Math.max(1, shadowDef.blur * scale);
          ctx.shadowOffsetX = (shadowDef.x || 0) * scale;
          ctx.shadowOffsetY = (shadowDef.y || 2) * scale;
          ctx.fillStyle = 'rgba(0, 0, 0, 0.90)';
          ctx.fillText(layout.text, wX, wY);
          ctx.restore();
        }

        // Pass 2A: Concentric Outer Stroke
        if (captionBox !== 'per_word' && !(kineticMode === 'glider' && isActive)) {
          if (outerStroke && outerStroke.width > 0) {
            const outW = Math.max(2, outerStroke.width * scale * 5.0);
            ctx.lineWidth = outW;
            ctx.strokeStyle = outerStroke.color || colors.outline || '#000000';
            ctx.lineJoin = 'round';
            ctx.miterLimit = 2;
            ctx.strokeText(layout.text, wX, wY);
          } else {
            const baseOutW = Math.max(2, (meta.outline_width || 1.0) * 4.2 * scale);
            ctx.lineWidth = baseOutW;
            ctx.strokeStyle = colors.outline || '#141414';
            ctx.lineJoin = 'round';
            ctx.miterLimit = 2;
            ctx.strokeText(layout.text, wX, wY);
          }

          // Pass 2B: Concentric Inner Stroke (Sticker Rim)
          if (innerStroke && innerStroke.width > 0) {
            const inW = Math.max(1, innerStroke.width * scale * 3.2);
            ctx.lineWidth = inW;
            ctx.strokeStyle = innerStroke.color || '#ffffff';
            ctx.lineJoin = 'round';
            ctx.miterLimit = 2;
            ctx.strokeText(layout.text, wX, wY);
          }
        }

        // Pass 3: Dynamic Multi-Stop Gradient or Color Fill (Glyph Core)
        let fillPaint = textColor;
        if (isActive && activeGradient && activeGradient.length >= 2) {
          const grad = ctx.createLinearGradient(wX, wY - wH / 2, wX, wY + wH / 2);
          const stopStep = 1.0 / (activeGradient.length - 1);
          activeGradient.forEach((color, idx) => {
            grad.addColorStop(Math.min(1.0, idx * stopStep), color);
          });
          fillPaint = grad;
        } else if (!isActive && !isUpcoming && primaryGradient && primaryGradient.length >= 2) {
          const grad = ctx.createLinearGradient(wX, wY - wH / 2, wX, wY + wH / 2);
          const stopStep = 1.0 / (primaryGradient.length - 1);
          primaryGradient.forEach((color, idx) => {
            grad.addColorStop(Math.min(1.0, idx * stopStep), color);
          });
          fillPaint = grad;
        }

        ctx.fillStyle = fillPaint;
        ctx.fillText(layout.text, wX, wY);

        ctx.restore();

        curX += wW + spaceWidth;
      }

      // (Phase 5) Spatial Sticker Compositor Layer
      const sc = getStickerCompositor();
      if (sc && timeline.stickers && timeline.stickers.length && wordBoxes.length) {
        sc.renderActiveStickers(ctx, timeline.stickers, wordBoxes, currentMs, scale, meta.spring_physics);
      }

      ctx.restore();

      return {
        activePhraseIdx,
        activeWordIdx,
        wordBoxes,
        cameraState,
      };
    },
  };

  return CaptionCanvasRenderer;
}));

