import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from divine_whisper_v5_eternal_orchestrator import (
    AnchorAgent,
    BeliefState,
    compare_anchor,
    orchestrate_task,
)


class AnchoringTests(unittest.TestCase):
    def test_entropy_is_recomputed_from_anchored_vector(self):
        belief = BeliefState.new(dim=8)
        sparse = np.zeros(8, dtype=np.float32)
        sparse[0] = 1.0
        belief.update(sparse)
        before = belief.entropy
        self.assertLess(before, 0.01)
        self.assertTrue(AnchorAgent().maybe_anchor(belief, np.ones(8, dtype=np.float32)))
        self.assertGreater(belief.entropy, 0.999)
        self.assertGreater(belief.entropy, before)

    def test_invalid_evidence_cannot_be_an_anchor(self):
        belief = BeliefState.new(dim=4)
        for evidence in (np.zeros(4), np.ones(3), np.array([np.nan, 1, 1, 1])):
            with self.assertRaises(ValueError):
                AnchorAgent().maybe_anchor(belief, evidence)

    def test_paired_comparison_is_reproducible_and_exposes_gap(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = compare_anchor(42, 8, Path(first))
            two = compare_anchor(42, 8, Path(second))
            self.assertEqual(one, two)
            self.assertEqual(
                (Path(first) / "anchor_comparison.json").read_bytes(),
                (Path(second) / "anchor_comparison.json").read_bytes(),
            )
            self.assertEqual(one["with_anchor"]["anchored_steps"], [0])
            self.assertGreater(one["first_step_entropy_difference"], 0.05)
            self.assertAlmostEqual(one["with_anchor"]["entropy_trajectory"][0], 1.0, places=5)
            self.assertEqual(json.loads((Path(first) / "anchor_comparison.json").read_text()), one)

    def test_invalid_step_count(self):
        with self.assertRaises(ValueError):
            orchestrate_task(max_steps=0)


if __name__ == "__main__":
    unittest.main()
