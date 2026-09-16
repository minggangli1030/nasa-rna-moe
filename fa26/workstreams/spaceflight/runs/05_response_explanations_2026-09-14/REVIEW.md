# Reviewed interpretation — September 14, 2026 (Pacific)

**The pilot now gives a partial response-level explanation. Its clearest tested BRIDGE
contributor is the myogenesis-associated muscle differentiation/remodeling program. It
does not establish a radiation or microgravity explanation.**

Among the six predefined programs, replacing the myogenesis genes reduces the flight–ground
logit gap by 0.562–0.821 across the two heads and two references. Its direction survives
both references and TPM-renormalization checks. The effect exceeds 18–19 of the 20 matched
random panels in the four primary comparisons; this is a descriptive rank, not 90–95%
confidence. Chip deletion preserves the within-case sign in 47/48 sensitivity comparisons.
These are repeated checks on two biological pools, not 48 independent experiments.

Mitochondrial-expression scores increase in both evaluation pools (+0.158 to +0.178 mean
log1p TPM), but their net contribution slightly opposes BRIDGE's flight/ground separation.
Their replacement effects do not exceed most matched controls. The direct expression
classifier uses these inputs differently, supporting its flight separation. Thus an
observed expression response is not automatically a response used positively by BRIDGE.

DNA-repair reliance changes sign across the fitted heads. Its 100% within-case chip-deletion
sign retention does not resolve that cross-head disagreement. Oxidative-stress-associated
and inflammatory inputs have consistent positive gap contributions, but their effects are
small relative to matched random panels. The unfolded-protein-response contribution is
sensitive to renormalization. None supports an exposure-specific radiation/gravity claim.

For the six held-out flight samples, **91.2–92.9% of positive IG attribution is outside
these six programs**, using equal splitting of overlapping memberships. This is incomplete
coverage by the selected program vocabulary, not evidence that the remaining signal is
necessarily meaningless. It also prevents presenting the current output as a complete
stress-response breakdown. Adding gene sets merely to inflate coverage would not validate
their biological interpretation.

## Useful downstream output today

The [worked sample](EXAMPLE.md) reports flight prediction, response-associated expression,
model reliance and supporting-gene access. For GSM9013410, replacing the myogenesis
program lowers the flight logit by 0.866; inflammatory-program replacement lowers it by
0.533. These are model sensitivities in logit units, not biological causal fractions.
The inflammatory effect in this one chip does not override the weaker cohort-level
comparison with matched controls. Use `supporting_genes.csv` for the genes underneath
each named program.

## Next decision

Preserve this frozen-head case as a baseline. The next scientific step is to define and
validate response concepts using independent, controlled exposure/perturbation datasets,
then test whether the flight head relies on the validated concepts. Prioritize myogenesis/
muscle-state evidence as a context-specific lead and radiation/gravity signatures as
separate unvalidated hypotheses. Suitable tissue, exposure, time and control labels are
needed before training exposure-specific probes. If a new flight head must explicitly
reason through response scores, evaluate that concept-based architecture separately.

No additional dataset acquisition, training or GPU run is queued. The existing cross-flight
failure remains unresolved; this run does not improve or independently validate the head.

## Review checks

- All 6,048 replacement rows and 24 original/reference score rows are present and unique.
- Original BRIDGE logits reproduce to a maximum absolute error of 8.9e-16.
- Analytic expression-head replacement checks pass; all output scores are finite.
- Exact random-panel matching, input/panel/script hashes and retrieved file hashes pass.
- The figure was visually inspected: labels and axes are readable and each classifier's
  own logit scale is identified. No cross-model raw-logit superiority is claimed.
- A100 execution took 32.8 minutes; peak allocated memory was 1.93 GB. The VM is idle.
