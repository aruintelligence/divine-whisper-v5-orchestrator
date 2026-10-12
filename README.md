> [!NOTE]
> **Divine Whisper lineage repository.** This is a preserved experimental stage. See the [ecosystem index](https://github.com/aruintelligence/divine-whisper-ecosystem) for the version map and research scope.

# Divine Whisper v5 Eternal: synthetic orchestration loop

This repository has one Python script, `divine_whisper_v5_eternal_orchestrator.py`. It updates a 256-dimensional synthetic vector, evaluates formulas called clarity and safety, runs a one-position council barrier and a recommendation rule, and logs each step. It does not call language models, access external evidence, measure real-world safety, or learn a decision policy. The optional Ray, Neo4j, and FAISS integrations described in earlier documentation were never wired into this script.

The scripted anchor uses an all-ones vector as "evidence." A uniform vector has nearly **maximum normalized Shannon entropy**, where entropy is calculated over the absolute vector components. Earlier code multiplied the stored entropy by 0.8 on anchoring without measuring the resulting vector, which made step 0 report 0.7591 even though the anchored vector's entropy is almost 1.0. The code now recomputes entropy from the actual vector after anchoring.

## Run

```bash
python -m pip install numpy
python divine_whisper_v5_eternal_orchestrator.py --seed 42 --steps 8 --out-dir artifacts
python divine_whisper_v5_eternal_orchestrator.py --compare-anchor --seed 42 --steps 8 --out-dir artifacts
python -m unittest discover -s tests -v
```

The comparison replays the same generated deltas with the scripted anchor enabled and disabled. `artifacts/anchor_comparison.json` contains both entropy trajectories, anchor steps, and the first-step difference; `artifacts/with_anchor.jsonl` and `artifacts/without_anchor.jsonl` are event logs. A normal run writes `artifacts/heaven_ledger.jsonl`. Event logs include timestamps and normal runs append; the comparison clears its two dedicated log files before running. The comparison JSON is reproducible for the same seed and step count.

At seed 42 with eight steps, the corrected step-0 entropy is about **1.0000** with anchoring and **0.9489** without it (difference **+0.0511**). The anchor increased this concentration-based entropy proxy in this example. The result is a check on the script's own mechanics, not a finding about external evidence or reasoning quality. Further seeds and genuine outcome data would be needed to evaluate a useful anchoring policy.

The clarity, safety, budget, and entropy fields are deterministic or seeded formulas over synthetic values. `safety` is a proxy name used by the existing code, not a safety assessment. The council receives one scripted position; the ledger is a local JSONL file.

Original concept and authors: Daniel Jacob Read IV and Shane Travis Horman. MIT licensed.
