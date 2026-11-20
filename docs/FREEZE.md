# Freeze manifest

Written 2026-11-20T09:10:46Z, before any rule, model or prompt read these files.
A later edit to a frozen file changes its hash; the release run must use these exact files.

| File | SHA-256 |
|---|---|
| `data/handwritten/dev.json` | `5d1f6ff8a817e1f41c8dea3e14371d937c870aed2ddb85f461ca823195f4e5ef` |
| `data/handwritten/holdout.json` | `a945e46d09c2597e6af1853b0d2f10259752d816403be577a331336d168a0d19` |
| `docs/LABELLING.md` | `bf1496fdd80801c219537f821908c699f7512895b69bea5c538f583e772f4b5f` |
| `docs/PRD.md` | `8960611bbeb5e085af97619a649f0c0145c74b1a2a90848b09830df63854b75b` |

## Release configuration

Recorded 2026-11-20T09:24:09Z, after the dev runs and before the one held-out release run.
Model `gemini-3.1-flash-lite`, prompt v1, temperature 1.0, two runs must agree; ML threshold 0.92 (tuned on generated dev).

| File | SHA-256 |
|---|---|
| `prompts/extract_v1.md` | `01ab945c1492ebb066851c72e0a6691f2de4b609a2d57aa305421b2bbcdcf38b` |
| `safe_to_bill/mdm.py` | `36c9c01f4df8a70e2b88fa0bb3ce8b1ec24014fa457eb378576a63e535be3f44` |
| `safe_to_bill/rules_extractor.py` | `66d16e3a280e0ef88c46c74313cd3084691d4eb9f5099ab424fdb2aa9d88fb8c` |
| `safe_to_bill/llm_extractor.py` | `02d1f78dc5f9c6725ba3675c7f658f00ca57b337bf1e8f016821029d6543343d` |
| `safe_to_bill/check.py` | `04c125c078656983882feae7e6a55e4b7af6cde5a186531f60f83863dc92c0d1` |
| `safe_to_bill/decide.py` | `e0781068b3bbc3d1293fe22cc25f1039ec78e8c5750a27db01b224bd25598811` |
| `safe_to_bill/verify.py` | `16f0bbe381c6a3814ed22454460017045911392a49806ba1760ba343dbdcc250` |

## Release run 2 freeze

Recorded 2026-11-20T10:34:02Z, before any rule, model or prompt read `holdout2.json`. Only change since the run-1 configuration: the verifier (stitched quotes).

| File | SHA-256 |
|---|---|
| `data/handwritten/holdout2.json` | `d790cf6ca001561eb922fd3752b1179323367ada48b5db70d4b576a4b8235bd5` |
| `docs/RELEASE_2.md` | `d7462b742a0a8e37b71bf51627ee921d89f8225a4a903daf0b08a2136aceac57` |
| `safe_to_bill/verify.py` | `32fca93aa3fafc042e836c5eb8407d275f3eaed66e3c672083a0e72d4ac369a3` |
| `prompts/extract_v1.md` | `01ab945c1492ebb066851c72e0a6691f2de4b609a2d57aa305421b2bbcdcf38b` |
| `safe_to_bill/rules_extractor.py` | `66d16e3a280e0ef88c46c74313cd3084691d4eb9f5099ab424fdb2aa9d88fb8c` |
| `safe_to_bill/llm_extractor.py` | `b6d8e738cdf45e0c6e4d678d98bab9d702ec83d5162235c5db80be9c639aae86` |
| `safe_to_bill/check.py` | `04c125c078656983882feae7e6a55e4b7af6cde5a186531f60f83863dc92c0d1` |
