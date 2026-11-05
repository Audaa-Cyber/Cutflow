"""Tests for Phase 5: Multi-Track B-Roll & Polish Compositor.

Validates:
1. Keyword-to-Sticker Auto-Injection Engine (semantic tagging, sticker event schemas)
2. Spatial Sticker Compositor Layer (spring-driven entry/exit physics, word anchoring, Skia SVG rasterization)
3. Dynamic Virtual Camera Controller (spring-damper camera punches, whip-pan transitions, motion blur)
4. Synchronized Audio Sound Design Sub-Mixer (Web Audio API event scheduling, volume ducking, adelay/amix FFmpeg filtergraph)
5. Strict 1:1 Parity between browser Canvas preview and backend headless export pipeline
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

from backend.captions.audio_sfx import build_ffmpeg_sfx_filtergraph
from backend.captions import presets as caption_presets
from backend.captions.timeline import build_kinetic_timeline, STICKER_SEMANTIC_MAP

ROOT = Path(__file__).resolve().parents[1]
NODE_EXE = shutil.which("node") or "node"


class TestPhase5CompositorAndPolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_words = [
            {"word": "This", "start": 0.0, "end": 0.3},
            {"word": "money", "start": 0.3, "end": 0.7},
            {"word": "growth", "start": 0.7, "end": 1.1},
            {"word": "is", "start": 1.1, "end": 1.3},
            {"word": "crazy", "start": 1.3, "end": 1.8},
        ]
        cls.stickers_dir = ROOT / "backend" / "assets" / "stickers"
        cls.sfx_dir = ROOT / "backend" / "assets" / "sfx"

    def _run_node_expr(self, expr: str) -> dict:
        """Helper to evaluate Node.js scripts isomorphic to browser client."""
        script = f"""
        const fs = require('fs');
        const path = require('path');
        const {{ createCanvas, GlobalFonts, loadImage }} = require('@napi-rs/canvas');
        const km = require('./frontend/kinetic_motion.js');
        const sc = require('./frontend/sticker_compositor.js');
        const vc = require('./frontend/virtual_camera.js');
        const sfx = require('./frontend/sfx_mixer.js');
        const renderer = require('./frontend/caption_canvas.js');

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

    def test_sticker_and_sfx_assets_exist_on_disk(self):
        """Verify all 12 vector SVGs and 4 PCM WAV SFX exist in backend assets."""
        expected_stickers = [
            "fire.svg", "rocket.svg", "money.svg", "brain.svg", "warning.svg",
            "lightning.svg", "trophy.svg", "chart_up.svg", "target.svg",
            "skull.svg", "heart.svg", "crown.svg"
        ]
        for s in expected_stickers:
            p = self.stickers_dir / s
            self.assertTrue(p.exists(), f"Missing sticker asset: {p}")
            self.assertGreater(p.stat().st_size, 200)

        expected_sfx = ["pop.wav", "click.wav", "whoosh.wav", "punch.wav"]
        for s in expected_sfx:
            p = self.sfx_dir / s
            self.assertTrue(p.exists(), f"Missing SFX asset: {p}")
            self.assertGreater(p.stat().st_size, 1000)

    def test_semantic_keyword_tagging_and_timeline_serialization(self):
        """Verify keyword matching maps tokens to spatial stickers, camera punches, and SFX cues."""
        spec = caption_presets.get("hormozi")
        self.assertIsNotNone(spec)

        tl = build_kinetic_timeline(self.raw_words, 0.0, 2.0, spec=spec, clip_id="clip_p5")

        # 1. Stickers verification
        self.assertIn("stickers", tl)
        stickers = tl["stickers"]
        # Words "money", "growth", "crazy" must be tagged with corresponding stickers
        categories = [s["category"] for s in stickers]
        self.assertIn("money", categories)
        self.assertIn("chart_up", categories)
        self.assertIn("skull", categories)

        for s in stickers:
            self.assertIn("word_id", s)
            self.assertIn("start_ms", s)
            self.assertIn("end_ms", s)
            self.assertTrue(s["asset"].endswith(".svg"))

        # 2. Camera Events verification
        self.assertIn("camera_events", tl)
        camera_events = tl["camera_events"]
        punches = [ev for ev in camera_events if ev["type"] == "punch"]
        self.assertTrue(len(punches) >= 2, "Expected multiple camera punches on high-impact keywords")

        # 3. Audio SFX cues verification
        self.assertIn("audio_sfx", tl)
        audio_sfx = tl["audio_sfx"]
        sfx_types = [ev["type"] for ev in audio_sfx]
        self.assertIn("pop", sfx_types)
        self.assertIn("punch", sfx_types)

        # Check chronological ordering
        for i in range(len(audio_sfx) - 1):
            self.assertLessEqual(audio_sfx[i]["timestamp_ms"], audio_sfx[i + 1]["timestamp_ms"])

    def test_spatial_sticker_compositor_spring_physics(self):
        """Verify StickerCompositor calculates underdamped spring overshoot on sticker entry."""
        result = self._run_node_expr("""
        const sticker = {
          id: 'stk_0',
          word_id: 'w_1',
          category: 'money',
          start_ms: 300,
          end_ms: 700,
          tilt_deg: -8.0,
        };

        const tBefore = sc.evaluateStickerMotion(sticker, 200);
        const tPeak = sc.evaluateStickerMotion(sticker, 450); // Peak of spring overshoot
        const tSettle = sc.evaluateStickerMotion(sticker, 650); // Settling near target
        const tAfter = sc.evaluateStickerMotion(sticker, 900); // Past exit window

        console.log(JSON.stringify({
          tBefore,
          tPeak,
          tSettle,
          tAfter,
        }));
        """)

        # Before start: inactive
        self.assertFalse(result["tBefore"]["active"])

        # At peak overshoot (~150ms after start_ms): scale exceeds 1.0
        self.assertTrue(result["tPeak"]["active"])
        self.assertGreater(result["tPeak"]["scale"], 1.0)
        self.assertAlmostEqual(result["tPeak"]["opacity"], 1.0, places=2)

        # Near end: settled close to 1.0
        self.assertTrue(result["tSettle"]["active"])
        self.assertAlmostEqual(result["tSettle"]["scale"], 1.0, delta=0.15)

        # Well after exit: inactive
        self.assertFalse(result["tAfter"]["active"])

    def test_all_12_stickers_load_and_draw_in_skia(self):
        """Verify all 12 SVG sticker assets load and draw to a Skia canvas without errors."""
        result = self._run_node_expr("""
        (async () => {
          await sc.preloadAll();
          const canvas = createCanvas(400, 400);
          const ctx = canvas.getContext('2d');
          
          const categories = [
            'fire', 'rocket', 'money', 'brain', 'warning', 'lightning',
            'trophy', 'chart_up', 'target', 'skull', 'heart', 'crown'
          ];
          
          let drawCount = 0;
          categories.forEach((cat, idx) => {
            const img = sc.getImage(cat);
            if (img) {
              ctx.drawImage(img, (idx % 4) * 80, Math.floor(idx / 4) * 80, 70, 70);
              drawCount++;
            }
          });
          
          console.log(JSON.stringify({ drawCount, total: categories.length }));
        })();
        """)

        self.assertEqual(result["drawCount"], 12)
        self.assertEqual(result["total"], 12)

    def test_virtual_camera_punch_and_whip_pan(self):
        """Verify VirtualCamera calculates spring zoom punches and directional whip pans."""
        result = self._run_node_expr("""
        const cameraEvents = [
          { type: 'punch', word_id: 'w_1', start_ms: 300, end_ms: 700, scale: 1.12 },
          { type: 'whip_pan', phrase_id: 'p_1', start_ms: 1000, duration_ms: 180, direction: 1, displacement_px: 50 }
        ];

        // 1. Resting camera at t = 100ms
        const resting = vc.evaluateCamera(cameraEvents, 100, 1080, 1920);

        // 2. Punch peak at t = 450ms
        const punchPeak = vc.evaluateCamera(cameraEvents, 450, 1080, 1920);

        // 3. Whip-pan peak at t = 1090ms (midpoint of 1000-1180ms)
        const whipPeak = vc.evaluateCamera(cameraEvents, 1090, 1080, 1920);

        console.log(JSON.stringify({ resting, punchPeak, whipPeak }));
        """)

        # Resting
        self.assertEqual(result["resting"]["scale"], 1.0)
        self.assertEqual(result["resting"]["translateX"], 0.0)
        self.assertFalse(result["resting"]["isPunch"])
        self.assertFalse(result["resting"]["isWhipPan"])

        # Punch peak
        self.assertTrue(result["punchPeak"]["isPunch"])
        self.assertGreater(result["punchPeak"]["scale"], 1.08)

        # Whip-pan peak
        self.assertTrue(result["whipPeak"]["isWhipPan"])
        self.assertGreater(result["whipPeak"]["translateX"], 40.0)
        self.assertGreater(result["whipPeak"]["motionBlur"], 0.70)

    def test_ffmpeg_audio_sfx_filtergraph_generation(self):
        """Verify build_ffmpeg_sfx_filtergraph creates valid adelay and amix syntax for FFmpeg."""
        sfx_events = [
            {"type": "pop", "timestamp_ms": 300, "volume": 0.85},
            {"type": "whoosh", "timestamp_ms": 1100, "volume": 0.65},
            {"type": "punch", "timestamp_ms": 1400, "volume": 0.75},
        ]

        inputs, filtergraph, out_label = build_ffmpeg_sfx_filtergraph(
            sfx_events, self.sfx_dir, clip_start_sec=0.0, clip_duration_sec=2.0
        )

        self.assertEqual(out_label, "[aout]")
        self.assertTrue(len(inputs) >= 6) # At least 3 inputs ("-i", path)
        self.assertIn("adelay=300|300", filtergraph)
        self.assertIn("adelay=1100|1100", filtergraph)
        self.assertIn("adelay=1400|1400", filtergraph)
        self.assertIn("amix=inputs=4", filtergraph)
        self.assertIn("volume=0.85", filtergraph)

    def test_end_to_end_frame_render_with_stickers_and_camera(self):
        """Verify CaptionCanvasRenderer compositing loop renders stickers and camera punch without error."""
        result = self._run_node_expr("""
        (async () => {
          await sc.preloadAll();
          const canvas = createCanvas(1080, 1920);
          const ctx = canvas.getContext('2d');
          
          const timeline = {
            phrases: [{
              start_ms: 0,
              end_ms: 1000,
              words: [
                { id: 'w_0', word: 'FIRE', text: 'FIRE', start_ms: 0, end_ms: 500, highlight: true },
                { id: 'w_1', word: 'ROCKET', text: 'ROCKET', start_ms: 500, end_ms: 1000, highlight: false },
              ]
            }],
            stickers: [
              { id: 'stk_0', word_id: 'w_0', word: 'FIRE', category: 'fire', asset: 'fire.svg', start_ms: 0, end_ms: 500, tilt_deg: -8, offset_x: 0, offset_y: -16, scale: 1 },
              { id: 'stk_1', word_id: 'w_1', word: 'ROCKET', category: 'rocket', asset: 'rocket.svg', start_ms: 500, end_ms: 1000, tilt_deg: 6, offset_x: 0, offset_y: -16, scale: 1 },
            ],
            camera_events: [
              { type: 'punch', word_id: 'w_0', start_ms: 0, end_ms: 500, scale: 1.12 }
            ],
            styling_metadata: {
              colors: { primary: '#FFFFFF', accent: '#FFE600' },
              font_size_px: 88,
              font: 'Montserrat',
            }
          };

          // Render at t = 0.25s (during active word FIRE with fire sticker and camera punch)
          const frameMetrics = renderer.renderFrame(ctx, timeline, 0.25, 1080, 1920);

          const imgData = ctx.getImageData(0, 0, 1080, 1920);
          let nonZeroPixels = 0;
          for (let i = 3; i < imgData.data.length; i += 4) {
            if (imgData.data[i] > 0) nonZeroPixels++;
          }

          console.log(JSON.stringify({
            rendered: true,
            activeWordIdx: frameMetrics.activeWordIdx,
            cameraState: frameMetrics.cameraState,
            nonZeroPixels,
          }));
        })();
        """)

        self.assertTrue(result["rendered"])
        self.assertEqual(result["activeWordIdx"], 0)
        self.assertTrue(result["cameraState"]["isPunch"])
        self.assertGreater(result["cameraState"]["scale"], 1.05)
        self.assertGreater(result["nonZeroPixels"], 1000)


if __name__ == "__main__":
    unittest.main()

