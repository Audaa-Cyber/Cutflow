"""Unit & Integration Tests for Phase 2: Hybrid Dual-Layer Rendering Architecture.

Validates:
1. Isomorphic CaptionCanvasRenderer Core (word layout, multi-layered strokes, zone positioning, frame rendering).
2. Static Font Serving (/assets/fonts/Montserrat-Bold.ttf).
3. Backend Headless Skia Renderer & Fallback Pipeline (render_clip_headless).
4. Re-export API endpoint (POST /api/jobs/{id}/clips/{filename}/export).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient

from backend.app import app, JOBS, LOCK, render_clip_headless
from backend.captions.presets import PRESETS
from backend.captions.timeline import build_kinetic_timeline


class TestPhase2Renderer(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    # ── 1. Static Font Mount ──────────────────────────────────────────────────

    def test_static_fonts_are_served_with_200(self):
        res = self.client.get("/assets/fonts/Montserrat-Bold.ttf")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 1000)

        res_mono = self.client.get("/assets/fonts/JetBrainsMono-Bold.ttf")
        self.assertEqual(res_mono.status_code, 200)

    # ── 2. Isomorphic CaptionCanvasRenderer in Node.js ────────────────────────

    def test_caption_canvas_renders_deterministic_frames_in_node(self):
        # Run node verification script executing frontend/caption_canvas.js
        node_script = """
        const { createCanvas, GlobalFonts } = require('@napi-rs/canvas');
        GlobalFonts.registerFromPath('backend/assets/fonts/Montserrat-Bold.ttf', 'Montserrat');
        const CaptionCanvasRenderer = require('./frontend/caption_canvas.js');

        const canvas = createCanvas(1080, 1920);
        const ctx = canvas.getContext('2d');

        const timeline = {
          start_ms: 0,
          end_ms: 3000,
          aspect_ratio: '9:16',
          styling_metadata: {
            preset_key: 'focus',
            font: 'Montserrat',
            font_size_px: 86,
            caption_box: 'per_word',
            colors: {
              primary: '#ffffff',
              accent: '#ffff00',
              upcoming: '#999999',
              outline: '#141414',
              fill: '#ffffff',
              fill_text: '#000000',
            }
          },
          phrases: [
            {
              start_ms: 0,
              end_ms: 2000,
              headline: 'TOP HOOK',
              words: [
                { id: 'w_0', word: 'First', text: 'FIRST', start_ms: 0, end_ms: 900 },
                { id: 'w_1', word: 'Second', text: 'SECOND', start_ms: 900, end_ms: 2000 }
              ]
            }
          ]
        };

        const res1 = CaptionCanvasRenderer.renderFrame(ctx, timeline, 0.45, 1080, 1920);
        if (res1.activeWordIdx !== 0 || res1.wordBoxes.length !== 2) {
          process.exit(1);
        }

        const res2 = CaptionCanvasRenderer.renderFrame(ctx, timeline, 1.20, 1080, 1920);
        if (res2.activeWordIdx !== 1 || res2.wordBoxes.length !== 2) {
          process.exit(2);
        }

        const png = canvas.toBuffer('image/png');
        if (png.length < 5000) {
          process.exit(3);
        }
        process.stdout.write('NODE_OK');
        """
        proc = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("NODE_OK", proc.stdout)

    # ── 3. Backend Headless Renderer Integration ──────────────────────────────

    def test_render_clip_headless_invokes_node_script_or_graceful_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / "source.mp4"
            source.write_bytes(b"dummy")
            output = Path(td) / "out.mp4"
            tl_path = Path(td) / "timeline.json"
            tl_path.write_text("{}", encoding="utf-8")

            with patch("backend.app.run_command") as mock_run:
                # Simulate output creation by headless script
                def fake_run(cmd, *a, **kw):
                    output.write_bytes(b"rendered_mp4_bytes")
                    return "ok"
                mock_run.side_effect = fake_run

                success = render_clip_headless(source, output, tl_path, 0.0, 3.0, "9:16")
                self.assertTrue(success)
                self.assertTrue(output.exists())
                cmd = mock_run.call_args.args[0]
                self.assertTrue(cmd[0].lower().endswith("node.exe") or cmd[0] == "node")
                self.assertIn("render_headless.js", cmd[1])
                self.assertIn("--timeline", cmd)

    # ── 4. Re-Export API Endpoint ─────────────────────────────────────────────

    def test_export_custom_clip_endpoint(self):
        job_id = "f0e1d2c3b4a5968778695041322110ff"
        spec = PRESETS["focus"]
        words = [
            {"start": 0.0, "end": 1.0, "word": "Edited"},
            {"start": 1.0, "end": 2.0, "word": "Captions"},
        ]
        timeline = build_kinetic_timeline(words, 0.0, 2.0, spec, aspect="9:16")

        with tempfile.TemporaryDirectory() as td:
            source_file = Path(td) / "source.mp4"
            source_file.write_bytes(b"source_video_data")

            clip_data = {
                "id": "clip_uuid_1",
                "filename": "cutflow-01.mp4",
                "download_url": f"/api/jobs/{job_id}/clips/cutflow-01.mp4",
                "start": 0.0,
                "end": 2.0,
                "duration": 2.0,
                "size": 100,
                "timeline": timeline,
                "words": timeline["words"],
            }

            with LOCK:
                JOBS[job_id] = {
                    "id": job_id,
                    "status": "completed",
                    "created_at": 1000.0,
                    "updated_at": 1001.0,
                    "source_path": str(source_file),
                    "aspect_ratio": "9:16",
                    "clips": [clip_data],
                    "candidates": [clip_data],
                }

            try:
                with patch("backend.app.render_clip_headless") as mock_headless:
                    def fake_headless(src, out_p, tl_p, *a, **kw):
                        out_p.write_bytes(b"new_rendered_bytes_456")
                        return True
                    mock_headless.side_effect = fake_headless

                    # Modify a word in timeline payload
                    edited_timeline = dict(timeline)
                    edited_timeline["words"][0]["text"] = "MODIFIED"

                    res = self.client.post(
                        f"/api/jobs/{job_id}/clips/cutflow-01.mp4/export",
                        json={"timeline": edited_timeline},
                    )
                    self.assertEqual(res.status_code, 200)
                    data = res.json()
                    self.assertTrue(data["ok"])
                    self.assertEqual(data["filename"], "cutflow-01.mp4")
                    self.assertEqual(data["timeline"]["words"][0]["text"], "MODIFIED")
                    self.assertEqual(data["size"], len(b"new_rendered_bytes_456"))

                    # Verify job state was updated in-memory
                    self.assertEqual(JOBS[job_id]["clips"][0]["timeline"]["words"][0]["text"], "MODIFIED")
            finally:
                with LOCK:
                    JOBS.pop(job_id, None)


if __name__ == "__main__":
    unittest.main()
