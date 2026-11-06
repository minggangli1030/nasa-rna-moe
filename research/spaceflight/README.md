# Spaceflight representation analysis

This directory has one canonical copy of each selected analysis. The old compatibility symlinks and nested workstream/run layout have been removed from the portfolio.

| Area | Implementation |
| --- | --- |
| Input contracts and TPM normalization | [audit_bridge_contract.py](audit_bridge_contract.py) |
| Frozen encoder inference | [bridge_infer_gtex.py](bridge_infer_gtex.py) |
| Group-aware response diagnostics | [analyze_general_survey.py](analyze_general_survey.py) |
| Pathway scoring and sensitivity | [pathway_onboard_survey.py](pathway_onboard_survey.py), [review_pathway_onboard.py](review_pathway_onboard.py) |
| Frozen-head baseline | [space_head_pilot.py](space_head_pilot.py) |
| Source/label/normalization diagnostics | [space_head_diagnostics.py](space_head_diagnostics.py) |
| Gradient attribution and perturbation checks | [space_head_attribution.py](space_head_attribution.py) |
| Offline normalization, inference, and statistics tests | [tests/](tests/) |

The test suite uses synthetic fixtures. Full analysis scripts require the original authorized model/reference assets and artifact contracts; this source-only subset is not a complete experiment reproduction bundle. No helper should be interpreted as a causal exposure estimator.
