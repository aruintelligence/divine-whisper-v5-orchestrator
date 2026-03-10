"""
Divine Whisper v5 Eternal – Final Runnable Orchestrator Blueprint
-----------------------------------------------------------------
One-file eternal prototype that implements the Divine Whisper control loop:

• Clarity Ψ(t) master function + stabilized dynamics
• Archangel contract validation
• Oversight edge simulation
• Heaven Ledger persistent logging
• Remiel node with active recommendations
• BeliefState threading with anchoring
• BudgetOracle + EarlyExitEvaluator
• CouncilClock quorum barrier
• Smoke test + CLI entry point

Copyright (c) 2026 Daniel Jacob Read IV & Shane Travis Horman – ĀRU Intelligence
MIT License – fork & extend freely
"""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Optional heavy deps – graceful fallback
try:
    import ray  # noqa: F401
except ImportError:
    ray = None

try:
    from neo4j import GraphDatabase  # noqa: F401
except ImportError:
    GraphDatabase = None

try:
    import faiss  # noqa: F401
except ImportError:
    faiss = None


# ────────────────────────────────────────────────────────────────────────────────
# Utilities
# ────────────────────────────────────────────────────────────────────────────────

def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_ms() -> float:
    return time.time() * 1000.0


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ────────────────────────────────────────────────────────────────────────────────
# Core Formulas
# ────────────────────────────────────────────────────────────────────────────────

def clarity(lam: float, coherence: float, signal: float, distortion: float, friction: float, eps: float = 1e-6) -> float:
    """
    Master clarity function Ψ(t), stabilized to a 0..1 range.
    """
    raw = (lam * coherence * signal) / ((distortion + eps) ** 2 * (friction + eps))
    if distortion < 0.14:
        boost = 1.0 + 1.8 * ((0.14 - distortion) / 0.14) ** 2
        raw *= boost
    return clamp(raw / (1.0 + abs(raw)))


def step_dynamics(
    A: float,
    D: float,
    C: float,
    F: float,
    lam: float,
    S: float,
    U: float,
    Xa: float,
    MW: float,
    conflict: float,
    Reg: float,
    L: float,
    SA: float,
    Rm: float,
    align: float,
    rel: float,
    nov: float,
    drift: float,
    dt: float = 0.05,
) -> tuple[float, float, float, float, float, float]:
    """
    Stabilized state update dynamics for attention, distortion, coherence,
    friction, lambda, and signal.
    """
    dA = U - 0.70 * A - 0.25 * D
    dD = -1.10 * A * D + 0.60 * Xa + 0.45 * MW + 0.55 * conflict
    dC = 0.90 * A + 0.55 * Reg - 0.40 * C - 0.60 * D
    dF = 0.45 * 0.5 + 0.35 * 0.5 - 0.65 * L - 0.75 * SA
    dLam = 0.55 * Rm + 0.50 * align - 0.35 * drift
    dS = 0.65 * rel + 0.22 * nov + 0.50 * C - 0.70 * 0.5

    next_A = A + dt * dA
    next_D = D + dt * dD
    next_C = C + dt * dC
    next_F = max(0.05, F + dt * dF)
    next_lam = max(0.05, lam + dt * dLam)
    next_S = max(0.05, S + dt * dS)

    return next_A, next_D, next_C, next_F, next_lam, next_S


# ────────────────────────────────────────────────────────────────────────────────
# CouncilClock
# ────────────────────────────────────────────────────────────────────────────────

class CouncilClock:
    """
    Quorum barrier that waits for k-of-N positions or timeout.
    """

    def __init__(self, quorum_factor: float = 0.6, timeout_ms: int = 1500, eps: float = 0.25):
        self.q = quorum_factor
        self.timeout_ms = timeout_ms
        self.eps = eps
        self.positions: List[Dict[str, Any]] = []

    def add(self, position: Dict[str, Any]) -> None:
        self.positions.append(position)

    def ready(self, expected_n: int) -> bool:
        needed = max(1, math.ceil(self.q * expected_n))
        if len(self.positions) < needed:
            return False

        confidences = [float(p.get("confidence", 0.0)) for p in self.positions]
        return (max(confidences) - min(confidences)) <= self.eps

    def wait(self, expected_n: int) -> List[Dict[str, Any]]:
        start = now_ms()
        while now_ms() - start < self.timeout_ms:
            if self.ready(expected_n):
                break
            time.sleep(0.01)
        return list(self.positions)


# ────────────────────────────────────────────────────────────────────────────────
# Archangel Contract
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class ArchangelContract:
    name: str
    managed_agents: List[str]
    success_metrics: List[str]
    governance_policy: str
    adaptation_hook: str

    def validate(self) -> bool:
        return all(
            [
                bool(self.name.strip()),
                len(self.managed_agents) > 0,
                len(self.success_metrics) > 0,
                bool(self.governance_policy.strip()),
                bool(self.adaptation_hook.strip()),
            ]
        )


# ────────────────────────────────────────────────────────────────────────────────
# BeliefState + AnchorAgent
# ────────────────────────────────────────────────────────────────────────────────

@dataclass
class BeliefState:
    vector: np.ndarray
    entropy: float
    last_anchor_ts: float = field(default_factory=time.time)

    @staticmethod
    def new(dim: int = 256) -> "BeliefState":
        return BeliefState(vector=np.zeros(dim, dtype=np.float32), entropy=1.0)

    def update(self, delta: np.ndarray, penalty: float = 0.0) -> None:
        self.vector += delta - penalty
        norm = np.linalg.norm(self.vector) + 1e-6
        self.vector /= norm

        probs = np.abs(self.vector) + 1e-6
        probs /= probs.sum()
        entropy = float(-np.sum(probs * np.log(probs)))
        max_entropy = math.log(len(probs))
        self.entropy = clamp(entropy / max_entropy)


class AnchorAgent:
    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    def maybe_anchor(self, belief: BeliefState, evidence: np.ndarray) -> bool:
        belief_vec = belief.vector / (np.linalg.norm(belief.vector) + 1e-6)
        evidence_vec = evidence / (np.linalg.norm(evidence) + 1e-6)
        sim = float(np.dot(belief_vec, evidence_vec))

        if sim < self.threshold:
            belief.vector = evidence_vec.copy()
            belief.entropy = clamp(belief.entropy * 0.8)
            belief.last_anchor_ts = time.time()
            return True
        return False


# ────────────────────────────────────────────────────────────────────────────────
# BudgetOracle + EarlyExitEvaluator
# ────────────────────────────────────────────────────────────────────────────────

class BudgetOracle:
    """
    Simple cost / step predictor.
    """

    def __init__(self, base_budget: float = 1.0):
        self.base_budget = base_budget

    def predict_step_budget(self, ambiguity: float, entropy: float, step: int) -> float:
        complexity = 0.45 * ambiguity + 0.35 * entropy + 0.20 * min(step / 10.0, 1.0)
        return self.base_budget * (1.0 + complexity)


class EarlyExitEvaluator:
    """
    Halt when the system remains weak for too long or when the step budget runs too high.
    """

    def __init__(self, min_clarity: float = 0.12, max_low_clarity_steps: int = 3):
        self.min_clarity = min_clarity
        self.max_low_clarity_steps = max_low_clarity_steps
        self.low_clarity_steps = 0

    def should_halt(self, clarity_value: float, step_budget: float, max_budget: float = 2.25) -> bool:
        if clarity_value < self.min_clarity:
            self.low_clarity_steps += 1
        else:
            self.low_clarity_steps = 0

        over_budget = step_budget > max_budget
        exhausted = self.low_clarity_steps >= self.max_low_clarity_steps
        return over_budget or exhausted


# ────────────────────────────────────────────────────────────────────────────────
# Heaven Ledger
# ────────────────────────────────────────────────────────────────────────────────

class HeavenLedger:
    def __init__(self, path: Path = Path("./heaven_ledger.jsonl")):
        self.path = path
        self.path.parent.mkdir(exist_ok=True, parents=True)

    def log(self, archangel_id: str, step_id: str, metric_bundle: dict, notes: str = "") -> None:
        record = {
            "archangel_id": archangel_id,
            "step_id": step_id,
            "ts": time.time(),
            "metric_bundle": metric_bundle,
            "notes": notes,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


# ────────────────────────────────────────────────────────────────────────────────
# Oversight Edge Simulation
# ────────────────────────────────────────────────────────────────────────────────

def simulate_oversight_edge(clarity_value: float, entropy: float) -> float:
    """
    Higher is safer. Produces a 0..1 safety signal.
    """
    safety = 0.65 * clarity_value + 0.35 * (1.0 - entropy)
    return clamp(safety)


# ────────────────────────────────────────────────────────────────────────────────
# Remiel Node
# ────────────────────────────────────────────────────────────────────────────────

class Remiel:
    def __init__(self, ledger: HeavenLedger):
        self.ledger = ledger

    def run(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        clarity_value = trace.get("metrics", {}).get("clarity", 0.0)
        safety = trace.get("metrics", {}).get("safety", 0.0)
        score = clamp(clarity_value * safety)

        if score > 0.60:
            recommendation = "continue"
        elif score > 0.30:
            recommendation = "stabilize"
        else:
            recommendation = "pause_and_review"

        self.ledger.log(
            archangel_id="remiel",
            step_id=trace["id"],
            metric_bundle={"clarity_safety": score},
            notes=f"Recommendation: {recommendation}",
        )

        return {"recommendation": recommendation, "score": score}


# ────────────────────────────────────────────────────────────────────────────────
# Orchestrator Loop
# ────────────────────────────────────────────────────────────────────────────────

def orchestrate_task(task_id: str | None = None, max_steps: int = 8, seed: int = 42) -> Dict[str, Any]:
    if task_id is None:
        task_id = new_id("task")

    rng = np.random.default_rng(seed)

    ledger = HeavenLedger()
    belief = BeliefState.new()
    anchor = AnchorAgent()
    remiel = Remiel(ledger)
    oracle = BudgetOracle()
    halter = EarlyExitEvaluator()
    council = CouncilClock()

    contract = ArchangelContract(
        name="dw_v5_eternal_core",
        managed_agents=["anchor", "remiel", "oracle", "council"],
        success_metrics=["clarity", "safety", "entropy"],
        governance_policy="stability_first",
        adaptation_hook="belief_reanchor",
    )
    if not contract.validate():
        raise ValueError("Archangel contract validation failed.")

    A, D, C, F, lam, S = 0.45, 0.22, 0.40, 0.55, 0.60, 0.50
    trace = {
        "id": task_id,
        "metrics": {"clarity": 0.0, "safety": 0.0, "entropy": belief.entropy},
    }
    warnings: List[str] = []
    steps_run = 0

    for step in range(max_steps):
        steps_run += 1

        delta = rng.normal(0.0, 0.01, 256).astype(np.float32)
        belief.update(delta, penalty=0.002)

        evidence = np.ones(256, dtype=np.float32)
        anchored = anchor.maybe_anchor(belief, evidence)

        U = 0.55 + 0.03 * step
        Xa = 0.12 if anchored else 0.03
        MW = 0.10
        conflict = 0.08 if anchored else 0.16
        Reg = 0.42
        L = 0.18
        SA = 0.10
        Rm = 0.50
        align = 0.56
        rel = 0.60
        nov = 0.34
        drift = 0.10 if anchored else 0.18

        A, D, C, F, lam, S = step_dynamics(
            A,
            D,
            C,
            F,
            lam,
            S,
            U,
            Xa,
            MW,
            conflict,
            Reg,
            L,
            SA,
            Rm,
            align,
            rel,
            nov,
            drift,
        )

        clarity_value = clarity(lam, C, S, D, F)
        safety_value = simulate_oversight_edge(clarity_value, belief.entropy)
        step_budget = oracle.predict_step_budget(ambiguity=D, entropy=belief.entropy, step=step)

        council.add(
            {
                "agent": "remiel",
                "confidence": safety_value,
                "clarity": clarity_value,
            }
        )
        council_positions = council.wait(expected_n=1)

        trace["metrics"] = {
            "clarity": round(clarity_value, 6),
            "safety": round(safety_value, 6),
            "entropy": round(float(belief.entropy), 6),
            "budget": round(step_budget, 6),
        }

        rec = remiel.run(trace)

        ledger.log(
            archangel_id="orchestrator",
            step_id=f"{task_id}_step_{step}",
            metric_bundle={
                "anchored": anchored,
                "clarity": clarity_value,
                "safety": safety_value,
                "entropy": float(belief.entropy),
                "budget": step_budget,
                "council_positions": len(council_positions),
            },
            notes=f"step={step} recommendation={rec['recommendation']}",
        )

        print(
            f"step={step} "
            f"entropy={belief.entropy:.4f} "
            f"clarity={clarity_value:.4f} "
            f"safety={safety_value:.4f} "
            f"budget={step_budget:.4f} "
            f"anchored={anchored} "
            f"recommendation={rec['recommendation']}"
        )

        if halter.should_halt(clarity_value=clarity_value, step_budget=step_budget):
            warnings.append(f"Early exit at step {step}")
            print(warnings[-1])
            break

    result = {
        "task_id": task_id,
        "steps_run": steps_run,
        "final_entropy": round(float(belief.entropy), 6),
        "final_clarity": round(float(trace["metrics"]["clarity"]), 6),
        "final_safety": round(float(trace["metrics"]["safety"]), 6),
        "warnings": warnings,
        "ledger_path": str(ledger.path.resolve()),
    }

    print(f"Task {task_id} complete.")
    print(json.dumps(result, indent=2))
    return result


# ────────────────────────────────────────────────────────────────────────────────
# Smoke Test
# ────────────────────────────────────────────────────────────────────────────────

def test_v5_eternal_smoke() -> None:
    result = orchestrate_task(task_id="smoke_test_v5_eternal", max_steps=8, seed=42)
    assert "task_id" in result
    assert isinstance(result["final_entropy"], float)
    assert Path(result["ledger_path"]).exists()
    print("v5 eternal smoke test passed.")


if __name__ == "__main__":
    print("Running Divine Whisper v5 Eternal smoke test...")
    test_v5_eternal_smoke()
    print("Smoke test complete.")
