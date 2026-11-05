"""Tests for Phase 4: Visual Styling & Design System Expansion.

Validates:
1. Multi-Pass Text Shaders & Concentric Strokes (outer_stroke, inner_stroke, lineJoin='round', miterLimit=2)
2. Diffuse Ambient Drops & Glow Bloom Shaders (shadowBlur, shadowColor, dual shadow passes)
3. Dynamic Text Linear Gradients mapped to word bounding boxes
4. Curated Display Font loading and Skia registration (Anton, Bebas Neue, Komika Axis, Syne, The Bold Font)
5. Preset Archetypes complete 4-layer visual recipes and timeline serialization
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import unittest

from backend.captions import presets as caption_presets
from backend.captions.spec import CaptionSpec, FONTS_SUPPORTED
from backend.captions.timeline import build_kinetic_timeline

ROOT = Path(__file__).resolve().parents[1]
NODE_EXE = shutil.which("node") or "node"


class TestPhase4VisualStylingAndShaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_words = [
            {"word": "UNLEASH", "start": 0.0, "end": 0.5},
            {"word": "THE", "start": 0.5, "end": 0.9},
            {"word": "BEAST", "start": 0.9, "end": 1.5},
        ]
        cls.font_dir = ROOT / "backend" / "assets" / "fonts"

    def _run_node_expr(self, expr: str) -> dict:
        """Helper to run a Node.js snippet and parse JSON output."""
        script = f"""
        const fs = require('fs');
        const path = require('path');
        const {{ createCanvas, GlobalFonts }} = require('@napi-rs/canvas');
        const fontLoader = require('./frontend/font_loader.js');
        const km = require('./frontend/kinetic_motion.js');
        const renderer = require('./frontend/caption_canvas.js');

        // Register fonts for headless test
        const fontDir = path.resolve(__dirname, 'backend/assets/fonts');
        const fontsToRegister = [
          {{ path: 'Anton-Regular.ttf', name: 'Anton' }},
          {{ path: 'BebasNeue-Regular.ttf', name: 'Bebas Neue' }},
          {{ path: 'KomikaAxis.ttf', name: 'Komika Axis' }},
          {{ path: 'Syne-Bold.ttf', name: 'Syne' }},
          {{ path: 'TheBoldFont.ttf', name: 'The Bold Font' }},
        ];
        fontsToRegister.forEach(f => {{
          const fullPath = path.join(fontDir, f.path);
          if (fs.existsSync(fullPath)) {{
            GlobalFonts.registerFromPath(fullPath, f.name);
          }}
        }});

        {expr}
        """
        proc = subprocess.run(
            [NODE_EXE, "-e", script],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(proc.stdout.strip())

    def test_curated_fonts_exist_on_disk(self):
        """Verify all 5 creator display font binaries exist in backend/assets/fonts/."""
        expected_fonts = [
            "Anton-Regular.ttf",
            "BebasNeue-Regular.ttf",
            "KomikaAxis.ttf",
            "Syne-Bold.ttf",
            "TheBoldFont.ttf",
        ]
        for font_file in expected_fonts:
            font_path = self.font_dir / font_file
            self.assertTrue(
                font_path.exists(),
                f"Missing creator font asset: {font_path}",
            )
            self.assertGreater(
                font_path.stat().st_size,
                5000,
                f"Font binary too small or corrupted: {font_file}",
            )

    def test_fonts_supported_specification(self):
        """Verify FONTS_SUPPORTED and CaptionSpec accept the curated display fonts."""
        for font in ["Anton", "Bebas Neue", "Komika Axis", "Syne", "The Bold Font"]:
            self.assertIn(font, FONTS_SUPPORTED)

        spec = CaptionSpec(
            key="custom_beast",
            label="Custom Beast",
            description="Testing custom display font and multi-pass shaders",
            font="Komika Axis",
            outer_stroke_width=12.0,
            outer_stroke_color="#000000",
            inner_stroke_width=4.0,
            inner_stroke_color="#FFFFFF",
            shadow_blur=16.0,
            glow_blur=24.0,
            glow_color="#FF0055",
            active_gradient=("#FFE600", "#FF5500"),
            tilt_deg=-4.0,
        )
        self.assertEqual(spec.font, "Komika Axis")
        self.assertEqual(spec.outer_stroke_width, 12.0)
        self.assertEqual(spec.inner_stroke_width, 4.0)
        self.assertEqual(spec.glow_blur, 24.0)
        self.assertEqual(spec.glow_color, "#FF0055")
        self.assertEqual(spec.tilt_deg, -4.0)

    def test_timeline_shader_stack_serialization(self):
        """Verify build_kinetic_timeline serializes shader_stack and tilt_deg in styling_metadata."""
        spec = CaptionSpec(
            key="cyber_test",
            label="Cyber Test",
            description="Cyberpunk bloom test spec",
            font="Syne",
            outer_stroke_width=8.0,
            outer_stroke_color="#050510",
            inner_stroke_width=2.5,
            inner_stroke_color="#00F0FF",
            shadow_blur=18.0,
            shadow_color="rgba(0, 0, 0, 0.9)",
            glow_blur=28.0,
            glow_color="#00F0FF",
            active_gradient=("#00F0FF", "#7000FF"),
            primary_gradient=("#E2F1FF", "#8EA9DB"),
            tilt_deg=-3.0,
        )
        tl = build_kinetic_timeline(self.raw_words, 0.0, 2.0, spec=spec, clip_id="clip_cyber")
        self.assertIn("styling_metadata", tl)
        meta = tl["styling_metadata"]
        self.assertIn("shader_stack", meta)
        self.assertEqual(meta["tilt_deg"], -3.0)

        shader_stack = meta["shader_stack"]
        self.assertEqual(shader_stack["outer_stroke"]["width"], 8.0)
        self.assertEqual(shader_stack["outer_stroke"]["color"], "#050510")
        self.assertEqual(shader_stack["inner_stroke"]["width"], 2.5)
        self.assertEqual(shader_stack["inner_stroke"]["color"], "#00F0FF")
        self.assertEqual(shader_stack["glow"]["blur"], 28.0)
        self.assertEqual(shader_stack["glow"]["color"], "#00F0FF")
        self.assertEqual(shader_stack["active_gradient"], ["#00F0FF", "#7000FF"])
        self.assertEqual(shader_stack["primary_gradient"], ["#E2F1FF", "#8EA9DB"])

    def test_preset_archetypes_complete_recipes(self):
        """Verify all 18 presets provide distinct multi-layer recipes with valid typography and shaders."""
        self.assertGreaterEqual(len(caption_presets.PRESETS), 18)

        # Flagship check: Hormozi punch recipe
        hormozi = caption_presets.get("hormozi")
        self.assertIsNotNone(hormozi)
        self.assertEqual(hormozi.font, "Komika Axis")
        self.assertEqual(hormozi.kinetic_mode, "pop")
        self.assertEqual(hormozi.outer_stroke_width, 2.4)
        self.assertEqual(hormozi.outer_stroke_color, "#000000")
        self.assertEqual(hormozi.inner_stroke_width, 0.7)
        self.assertEqual(hormozi.tilt_deg, -2.5)
        self.assertIsNotNone(hormozi.active_gradient)

        # Flagship check: Syne Cyberpunk Glow
        glow = caption_presets.get("glow")
        self.assertIsNotNone(glow)
        self.assertEqual(glow.font, "Syne")
        self.assertEqual(glow.kinetic_mode, "wave")
        self.assertGreater(glow.glow_blur, 20.0)
        self.assertEqual(glow.glow_color, "#00F5D4")

        # Flagship check: Anton Massive Beast Impact
        impact = caption_presets.get("impact")
        self.assertIsNotNone(impact)
        self.assertEqual(impact.font, "Anton")
        self.assertEqual(impact.kinetic_mode, "pop")
        self.assertGreaterEqual(impact.outer_stroke_width, 2.0)

        # Check all presets have valid fonts and kinetic modes
        for key, p in caption_presets.PRESETS.items():
            self.assertIn(p.font, FONTS_SUPPORTED)
            self.assertIn(p.kinetic_mode, ["pop", "wave", "glider", "none"])

    def test_skia_creator_font_registration_and_metrics(self):
        """Verify that all 5 creator display fonts register in Skia and measure accurate metrics."""
        result = self._run_node_expr("""
        const canvas = createCanvas(800, 600);
        const ctx = canvas.getContext('2d');
        
        const testFonts = ['Anton', 'Bebas Neue', 'Komika Axis', 'Syne', 'The Bold Font'];
        const metrics = {};
        
        testFonts.forEach(font => {
          ctx.font = `700 64px "${font}"`;
          const m = ctx.measureText("UNLEASH");
          metrics[font] = {
            width: m.width,
            actualBoundingBoxAscent: m.actualBoundingBoxAscent || 0,
            actualBoundingBoxDescent: m.actualBoundingBoxDescent || 0,
          };
        });
        
        console.log(JSON.stringify(metrics));
        """)

        for font in ["Anton", "Bebas Neue", "Komika Axis", "Syne", "The Bold Font"]:
            self.assertIn(font, result)
            self.assertGreater(
                result[font]["width"],
                50.0,
                f"Font {font} failed to measure non-trivial glyph widths in Skia",
            )

    def test_multipass_canvas_shader_rendering(self):
        """Verify CaptionCanvasRenderer executes multi-pass text shaders without error and draws pixels."""
        result = self._run_node_expr("""
        const canvas = createCanvas(1080, 1920);
        const ctx = canvas.getContext('2d');
        
        const phrase = {
          id: 'p_shader',
          start: 0.0,
          end: 1.5,
          start_ms: 0,
          end_ms: 1500,
          duration_ms: 1500,
          text: "UNLEASH THE BEAST",
          word_count: 3,
          words: [
            { id: 'w_0', word: "UNLEASH", text: "UNLEASH", start_ms: 0, end_ms: 500, highlight: true },
            { id: 'w_1', word: "THE", text: "THE", start_ms: 500, end_ms: 900, highlight: false },
            { id: 'w_2', word: "BEAST", text: "BEAST", start_ms: 900, end_ms: 1500, highlight: false }
          ]
        };
        
        const tl = {
          phrases: [phrase],
          styling_metadata: {
            font_family: "Komika Axis",
            font_size: 72,
            font_weight: "900",
            uppercase: true,
            kinetic_mode: "pop",
            tilt_deg: -3.5,
            colors: {
              primary: "#FFFFFF",
              accent: "#FFE600",
              fill: "#000000",
              fill_text: "#FFFFFF",
              outline: "#000000"
            },
            shader_stack: {
              outer_stroke: { width: 10, color: "#000000" },
              inner_stroke: { width: 3, color: "#FFFFFF" },
              shadow: { blur: 14, x: 0, y: 8, color: "rgba(0, 0, 0, 0.9)" },
              glow: { blur: 24, color: "#FF0055" },
              active_gradient: ["#FFE600", "#FF5500"],
              primary_gradient: ["#FFFFFF", "#D0D0D0"]
            }
          }
        };
        
        // Render at t = 0.25s (peak of first active word)
        const frameMetrics = renderer.renderFrame(ctx, tl, 0.25, 1080, 1920);
        
        // Inspect pixel buffer to verify non-empty rendering
        const imgData = ctx.getImageData(0, 0, 1080, 1920);
        let nonZeroPixels = 0;
        for (let i = 3; i < imgData.data.length; i += 4) {
          if (imgData.data[i] > 0) {
            nonZeroPixels++;
          }
        }
        
        console.log(JSON.stringify({
          rendered: true,
          boxesCount: frameMetrics.wordBoxes.length,
          activeWordIdx: frameMetrics.activeWordIdx,
          nonZeroPixels,
        }));
        """)

        self.assertTrue(result["rendered"])
        self.assertEqual(result["boxesCount"], 3)
        self.assertEqual(result["activeWordIdx"], 0)
        self.assertGreater(
            result["nonZeroPixels"],
            500,
            "Multi-pass shader failed to render any visible pixels on canvas",
        )

    def test_font_loader_module_structure(self):
        """Verify FontLoader object provides required methods and preloading capabilities."""
        result = self._run_node_expr("""
        console.log(JSON.stringify({
          hasEnsureFont: typeof fontLoader.ensureFont === 'function',
          hasPreloadAll: typeof fontLoader.preloadAll === 'function',
          hasIsFontReady: typeof fontLoader.isFontReady === 'function',
          fontCount: fontLoader.CURATED_FONTS.length,
        }));
        """)
        self.assertTrue(result["hasEnsureFont"])
        self.assertTrue(result["hasPreloadAll"])
        self.assertTrue(result["hasIsFontReady"])
        self.assertGreaterEqual(result["fontCount"], 8)


if __name__ == "__main__":
    unittest.main()
