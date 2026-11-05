"""Tests for Phase 3: Spring Physics & Kinetic Motion Core.

Validates:
1. Analytical closed-form damped harmonic oscillator math (SpringSolver)
2. Time-indexed determinism and O(1) evaluation
3. Kinetic Typography Generators (Pop/Bounce, Slide-Up Wave, Elastic Pill Glider)
4. Integration into CaptionCanvasRenderer and timeline styling metadata
5. 1:1 Parity in headless Skia frame export
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import unittest

from backend.captions import presets as caption_presets
from backend.captions.spec import CaptionSpec
from backend.captions.timeline import build_kinetic_timeline

ROOT = Path(__file__).resolve().parents[1]
NODE_EXE = shutil.which("node") or "node"


class TestSpringPhysicsAndKineticMotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Sample Whisper-like word tokens
        cls.raw_words = [
            {"word": "This", "start": 0.0, "end": 0.4},
            {"word": "kinetic", "start": 0.4, "end": 0.9},
            {"word": "engine", "start": 0.9, "end": 1.4},
            {"word": "pops", "start": 1.4, "end": 1.8},
        ]

    def _run_node_expr(self, expr: str) -> dict:
        """Helper to run a Node.js snippet and parse JSON output."""
        script = f"""
        const km = require('./frontend/kinetic_motion.js');
        const renderer = require('./frontend/caption_canvas.js');
        const {{ createCanvas }} = require('@napi-rs/canvas');
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

    def test_spring_solver_analytical_underdamped_overshoot(self):
        """Test underdamped harmonic oscillator (zeta < 1) exhibits overshoot and convergence."""
        result = self._run_node_expr("""
        const k = 260.0;
        const c = 14.0;
        const m = 1.0;
        const config = { tension: k, friction: c, mass: m };
        
        // Target: move from 1.0 to 1.25
        const t0 = km.SpringSolver.solve(1.0, 1.25, 0.0, config);
        const tPeak = km.SpringSolver.solve(1.0, 1.25, 0.22, config);
        const tSettled = km.SpringSolver.solve(1.0, 1.25, 1.5, config);
        
        console.log(JSON.stringify({
            t0,
            tPeak,
            tSettled,
        }));
        """)

        # At t=0, value must strictly equal starting value
        self.assertAlmostEqual(result["t0"]["value"], 1.0, places=4)
        self.assertEqual(result["t0"]["velocity"], 0.0)

        # At peak overshoot (~120ms), value must overshoot target 1.25
        self.assertGreater(result["tPeak"]["value"], 1.25)

        # At t=1.5s, spring must asymptotically settle at target equilibrium
        self.assertAlmostEqual(result["tSettled"]["value"], 1.25, places=2)
        self.assertAlmostEqual(result["tSettled"]["velocity"], 0.0, places=1)

    def test_spring_solver_determinism_o1(self):
        """Spring evaluation at identical t must yield bitwise identical values without state drift."""
        result = self._run_node_expr("""
        const config = { tension: 220, friction: 18, mass: 1.0 };
        const v1 = km.SpringSolver.solve(0, 100, 0.185, config);
        const v2 = km.SpringSolver.solve(0, 100, 0.185, config);
        console.log(JSON.stringify({ v1, v2 }));
        """)
        self.assertEqual(result["v1"]["value"], result["v2"]["value"])
        self.assertEqual(result["v1"]["velocity"], result["v2"]["velocity"])

    def test_pop_bounce_generator(self):
        """Test evaluatePopBounce returns correct scale overshoot, Y bounce, and settle states."""
        result = self._run_node_expr("""
        const word = { start_ms: 400, end_ms: 900, highlight: true };
        const config = { tension: 260, friction: 14, mass: 1.0 };

        const upcoming = km.KineticGenerators.evaluatePopBounce(word, 200, config, 1.0);
        const activeOnset = km.KineticGenerators.evaluatePopBounce(word, 520, config, 1.0);
        const settling = km.KineticGenerators.evaluatePopBounce(word, 1050, config, 1.0);
        const fullySettled = km.KineticGenerators.evaluatePopBounce(word, 1600, config, 1.0);

        console.log(JSON.stringify({ upcoming, activeOnset, settling, fullySettled }));
        """)

        # Upcoming word: scale 1.0, resting Y
        self.assertFalse(result["upcoming"]["isActive"])
        self.assertEqual(result["upcoming"]["scaleX"], 1.0)
        self.assertEqual(result["upcoming"]["translateY"], 0.0)

        # Active word during speaking window: active flag true, scale elevated > 1.15
        self.assertTrue(result["activeOnset"]["isActive"])
        self.assertGreater(result["activeOnset"]["scaleX"], 1.15)
        # Synchronized bounce Y elevation
        self.assertNotEqual(result["activeOnset"]["translateY"], 0.0)

        # Settling post-word: spoken flag true, scale decaying back towards 1.0
        self.assertTrue(result["settling"]["isSpoken"])
        self.assertFalse(result["settling"]["isActive"])
        self.assertLess(result["settling"]["scaleX"], result["activeOnset"]["scaleX"])

        # Fully settled post-word: scale strictly back at 1.0, translateY at 0.0
        self.assertEqual(result["fullySettled"]["scaleX"], 1.0)
        self.assertEqual(result["fullySettled"]["translateY"], 0.0)

    def test_word_wave_generator_staggered_entry(self):
        """Test evaluateWordWave progressive staggered entry and active wave crest."""
        result = self._run_node_expr("""
        const phrase = {
            start_ms: 0,
            end_ms: 1200,
            words: [
                { word: "Alpha", start_ms: 0, end_ms: 400 },
                { word: "Beta", start_ms: 400, end_ms: 800 },
                { word: "Gamma", start_ms: 800, end_ms: 1200 },
            ]
        };
        const config = { tension: 220, friction: 18, mass: 1.0 };

        // At t=0ms: word 0 enters immediately, word 2 (stagger delay 120ms) is still hidden
        const w0_at_0 = km.KineticGenerators.evaluateWordWave(phrase, 0, 0, config, 1.0);
        const w2_at_0 = km.KineticGenerators.evaluateWordWave(phrase, 2, 0, config, 1.0);

        // At t=550ms: word 1 is actively spoken, crests upward with negative Y offset
        const w1_active = km.KineticGenerators.evaluateWordWave(phrase, 1, 550, config, 1.0);

        console.log(JSON.stringify({ w0_at_0, w2_at_0, w1_active }));
        """)

        # Word 2 at t=0 has not reached its staggered entry time -> opacity 0.0, offset downwards
        self.assertEqual(result["w2_at_0"]["opacity"], 0.0)
        self.assertGreater(result["w2_at_0"]["translateY"], 0.0)

        # Word 1 at t=550ms is actively spoken -> isActive true, wave crests upward (negative translateY)
        self.assertTrue(result["w1_active"]["isActive"])
        self.assertLess(result["w1_active"]["translateY"], 0.0)
        self.assertGreater(result["w1_active"]["scaleX"], 1.0)

    def test_elastic_pill_glider_morphing_and_stretch(self):
        """Test evaluatePillGlider dynamically interpolates center coordinates and elongates with velocity."""
        result = self._run_node_expr("""
        const phrase = {
            start_ms: 0,
            end_ms: 1000,
            words: [
                { word: "First", start_ms: 0, end_ms: 400 },
                { word: "Second", start_ms: 400, end_ms: 800 },
            ]
        };
        const boxes = [
            { x: 100, y: 500, width: 80, height: 40 },
            { x: 260, y: 500, width: 120, height: 40 },
        ];
        const config = { tension: 200, friction: 18, mass: 1.0 };

        // While resting on word 0
        const settled_word0 = km.KineticGenerators.evaluatePillGlider(phrase, 150, boxes, config, 1.0);

        // During transition to word 1 (high velocity stretch)
        const in_flight = km.KineticGenerators.evaluatePillGlider(phrase, 460, boxes, config, 1.0);

        // Settling on word 1
        const settled_word1 = km.KineticGenerators.evaluatePillGlider(phrase, 750, boxes, config, 1.0);

        console.log(JSON.stringify({ settled_word0, in_flight, settled_word1 }));
        """)

        # Settled pill on word 0 covers word 0
        self.assertAlmostEqual(result["settled_word0"]["x"], 100 - 16, delta=5)

        # In flight: x position has moved towards word 1, width has elastic stretch
        self.assertGreater(result["in_flight"]["x"], result["settled_word0"]["x"])
        self.assertGreater(result["in_flight"]["width"], result["settled_word0"]["width"])

        # Settled pill on word 1 center aligns with word 1 (box.x = 260)
        self.assertGreater(result["settled_word1"]["x"], 200)

    def test_presets_kinetic_modes_and_styling_metadata(self):
        """Verify that presets correctly declare kinetic_mode and configure spring physics in timeline."""
        # 1. Pop preset
        pop_spec = caption_presets.get("pop")
        self.assertIsNotNone(pop_spec)
        self.assertEqual(pop_spec.kinetic_mode, "pop")

        pop_tl = build_kinetic_timeline(self.raw_words, 0.0, 2.0, spec=pop_spec, clip_id="clip_pop")
        self.assertEqual(pop_tl["styling_metadata"]["kinetic_mode"], "pop")
        self.assertIn("tension", pop_tl["styling_metadata"]["spring_physics"])

        # 2. Wave preset (pulse)
        pulse_spec = caption_presets.get("pulse")
        self.assertIsNotNone(pulse_spec)
        self.assertEqual(pulse_spec.kinetic_mode, "wave")

        pulse_tl = build_kinetic_timeline(self.raw_words, 0.0, 2.0, spec=pulse_spec, clip_id="clip_pulse")
        self.assertEqual(pulse_tl["styling_metadata"]["kinetic_mode"], "wave")

        # 3. Glider preset (paper / evo)
        paper_spec = caption_presets.get("paper")
        self.assertIsNotNone(paper_spec)
        self.assertEqual(paper_spec.kinetic_mode, "glider")

        paper_tl = build_kinetic_timeline(self.raw_words, 0.0, 2.0, spec=paper_spec, clip_id="clip_paper")
        self.assertEqual(paper_tl["styling_metadata"]["kinetic_mode"], "glider")

    def test_canvas_renderer_executes_all_kinetic_modes(self):
        """Verify CaptionCanvasRenderer successfully renders frames under pop, wave, and glider modes."""
        result = self._run_node_expr("""
        const canvas = createCanvas(1080, 1920);
        const ctx = canvas.getContext('2d');

        const phrase = {
            id: 'p_0',
            start: 0.0,
            end: 2.0,
            start_ms: 0,
            end_ms: 2000,
            duration_ms: 2000,
            text: 'This kinetic engine pops',
            word_count: 4,
            words: [
                { id: 'w_0', word: 'This', text: 'This', start_ms: 0, end_ms: 400, highlight: false },
                { id: 'w_1', word: 'kinetic', text: 'kinetic', start_ms: 400, end_ms: 900, highlight: true },
                { id: 'w_2', word: 'engine', text: 'engine', start_ms: 900, end_ms: 1400, highlight: false },
                { id: 'w_3', word: 'pops', text: 'pops', start_ms: 1400, end_ms: 1800, highlight: true },
            ]
        };

        const modes = ['pop', 'wave', 'glider'];
        const outcomes = {};

        for (const mode of modes) {
            const tl = {
                phrases: [phrase],
                styling_metadata: {
                    kinetic_mode: mode,
                    active_pop: true,
                    caption_box: mode === 'glider' ? 'pill' : 'none',
                    colors: { primary: '#ffffff', accent: '#ffff00', fill: '#221832', fill_text: '#ffffff', outline: '#000000' }
                }
            };
            const frameMetrics = renderer.renderFrame(ctx, tl, 0.65, 1080, 1920);
            outcomes[mode] = {
                boxesCount: frameMetrics.wordBoxes.length,
                activeWordIdx: frameMetrics.activeWordIdx,
            };
        }

        console.log(JSON.stringify(outcomes));
        """)

        for mode in ("pop", "wave", "glider"):
            self.assertEqual(result[mode]["boxesCount"], 4)
            # At t=0.65s (650ms), word 1 ("kinetic", 400ms-900ms) must be active
            self.assertEqual(result[mode]["activeWordIdx"], 1)


if __name__ == "__main__":
    unittest.main()
