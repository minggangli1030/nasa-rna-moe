# ARCHS4 downstream benchmark: implementation review and access firewall

**Reviewed:** 2026-08-04

**Scope now authorized:** metadata-only catalog and synthetic mechanical smoke

**ARCHS4 expression access:** not yet authorized

## Decision

Claude's two-family design is directionally sound. Family B (targeted-panel
imputation) is the cheapest first scientific test and most directly exercises the
validated reconstruction behavior. Family A (within-organ state classification) is
more independent and novel, but it requires deterministic label curation and human
validation before expression access. Both must retain raw/simple baselines, matched
controls, fixed seeds, grouped studies, per-organ reporting, and an untouched
confirmation partition.

The implementation begins with a metadata-only catalog and firewall. This is useful
work that cannot leak an efficacy outcome and can be mechanically tested on the VM.

## Corrections required before scientific outcome access

1. **Exclude the original Stage-1 cohort, not only the QC-retained cohort.** The
   original frozen manifest contains 827 samples in 64 connected study groups. Those
   groups contain 72 individual GEO series tokens because several connected groups
   join multiple GSE accessions. Every one of the 72 tokens is excluded, including
   studies/samples later removed by the post-access QC amendment.
2. **Freeze development and confirmation membership before expression access.** The
   study exclusions, eligible membership, target gene panel, mask schedules, scoring
   rules, seeds, and development/confirmation partition must be hash-bound first.
3. **Do not reuse Stage-1 lockbox outcomes for development.** The old expression and
   results remain evidence, not a source for selecting the new cohort or settings.
4. **Bound the Family-B claim.** Masked-panel imputation is a practical downstream
   utility, but it is close to the masked-reconstruction training objective and is not
   independent validation of biological state prediction.
5. **State the raw-expression baseline correctly.** Full raw targets are unavailable
   by definition, but the observed raw genes are inputs to gene-mean, PCA-completion,
   and kNN baselines. The task is not baseline-free.
6. **Freeze generic-K8 construction before outcomes.** Expression-cluster K8 is not a
   metadata-only control. Its training data, centroids, preprocessing, assignment
   contract, and hyperparameters must be fixed using only the allowed development
   lineage. Confirmation studies cannot influence them.
7. **Use deterministic eligibility, not outcome-guided search.** The ten Family-A
   task priorities may be frozen in advance; metadata counts then determine pass/fail
   eligibility without re-ranking by measured model performance. Human validation is
   mandatory and cannot be replaced by automated confidence.
8. **Apply headroom to the simple imputation baselines too.** Mask fractions that are
   trivial ceiling or unusable floor settings are rejected before the model ladder,
   under thresholds frozen before outcomes.
9. **GTEx overlap is fail-closed but identity-bounded.** Explicit GTEx markers and
   donor identifiers are excluded. Title-derived donor keys are not verified identity
   and cannot support a claim of donor-level disjointness.

## First executable milestone

The metadata-only implementation:

- binds the exact original Stage-1 manifest SHA256;
- verifies all 64 connected groups and 72 GEO series tokens;
- excludes those tokens and explicit GTEx overlap;
- maps only high-confidence samples in the eight frozen organs using the existing
  ontology implementation;
- emits organ/study and metadata-key inventories for deterministic rule drafting;
- records `expression_accessed: false` and immutable output checksums.

The VM smoke uses synthetic metadata. It proves mechanics and portability only; it is
not a scientific result. Real ARCHS4 expression remains sealed until the complete
benchmark contract is frozen.

## Mechanical smoke result

The focused local suite passed 24 tests, including the existing organ-recovery tests.
The dependency-light end-to-end smoke then passed on the primary VM at exact detached
commit `1532ea78159bc8faa03a14bab395cbd3333e1be9`.

- protocol SHA256: `0e09c5dc3f840aa5a00136511251027aa9824865790afbe204dbda2ef1543771`;
- VM result: `/media/volume/moe-reboot/results/archs4_downstream_metadata_smoke_1532ea7_retry1`;
- result SHA256: `9221ca8cb4245a2c54077aa3c082f12325c0399c9c0dee6291eb53bea3c61e8e`;
- decisions: one prior-Stage-1 exclusion, one explicit-GTEx exclusion, one eligible
  target-organ row, and one outside-organ exclusion;
- all 64 connected Stage-1 groups and all 72 constituent GSE tokens were bound;
- eligible prior-Stage-1 overlaps: zero;
- eligible explicit-GTEx overlaps: zero;
- expression accessed: false.

The earlier `4cfd52b` VM attempt is preserved as an implementation-only failure. It
stopped before producing a report because the original Stage-1 manifest is intentionally
not tracked in Git. The retry added an explicit input path, transferred the compact
manifest separately, and verified its frozen SHA256 before execution. No cohort,
threshold, mapping rule, or scientific gate changed.
