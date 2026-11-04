# Dispatch: E2E Test Writer

## Role
E2E Test Writer for Cutflow (Tiers 1-4 Test Suite)

## Working Directory
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\test_writer_e2e

## Task
Read ORIGINAL_REQUEST.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md`

Read PROJECT.md at:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md`

Design and create automated test cases covering:
- Tier 1: Feature coverage for Canvas framing default (R1), Caption styles schema and rendering across all 18 styles (R2), and Bulk job deletion (R3).
- Tier 2: Boundary & corner cases (empty jobs, sparse caption styles, invalid fit_mode).
- Tier 3: Cross-feature combinations (Evo preset with Canvas framing, job creation followed by bulk delete).
- Tier 4: Real-world workflows.

Integrate or co-locate these tests into `tests/test_cutflow.py` (or a dedicated test file in `tests/`) using the existing unittest framework.
Verify tests with:
`.\.venv\Scripts\python.exe -m unittest discover tests/`

When all tests are ready, publish:
`c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\TEST_READY.md`
and `c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\TEST_INFRA.md`.
Write `handoff.md` and send a message when finished.


## 2026-10-30T21:30:39Z
You are the E2E Test Writer for Cutflow.
Your working directory is:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\test_writer_e2e

Read ORIGINAL_REQUEST.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\ORIGINAL_REQUEST.md

Read PROJECT.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\PROJECT.md

Read DISPATCH.md at:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\test_writer_e2e\DISPATCH.md

Your scope:
Design and implement comprehensive automated test cases for Cutflow covering:
- Tier 1: Feature coverage for Canvas framing default (R1), Caption styles schema and rendering across all 18 styles (R2), and Bulk job deletion (R3).
- Tier 2: Boundary & corner cases (empty jobs, sparse caption styles, invalid fit_mode).
- Tier 3: Cross-feature combinations (Evo preset with Canvas framing, job creation followed by bulk delete).
- Tier 4: Real-world workflows.

Integrate the tests into tests/test_cutflow.py or a dedicated test file tests/test_e2e_features.py using python unittest.
Run tests using:
.\.venv\Scripts\python.exe -m unittest discover tests/

Publish:
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\TEST_INFRA.md
c:\Users\Nimox\OneDrive\Documents\cutflow\Cutflow\.agents\teamwork\TEST_READY.md
Write handoff.md in your working directory.
When finished, send a message to your parent with a concise summary.
