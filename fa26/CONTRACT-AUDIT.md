# BridgeRNA input audit — 2026-09-11

**Update:** The [completed OSDR pilot](artifacts/osdr_liver_pilot_2026-09-11/REPORT.md)
resolved the source/vocabulary questions for this exploratory run and corrected a
pre-normalization versus post-normalization error in the draft model. Full-length
masked/unmasked parity passed. GTEx coverage remains unresolved. The original audit
below records the earlier state.

The first Fall step was partially verified. Do not interpret embeddings until the
symbol mapping and checkpoint-matched source provenance below are resolved.
No biological embeddings or predictive results were generated in this audit.

## Verified locally

- Checkpoint `r7hnr92k`, epoch 20, contains 45,593,601 parameters. Its embedded
  configuration agrees with the bundled configuration and specifies `log1p_tpm`.
- The canonical CSV has 15,165 unique symbols and contiguous token IDs 1–15,165.
  Sorting by token ID gives alphabetical symbols; their tensor positions are
  0–15,164. This establishes the bundled order, not its training provenance.
- Every canonical human gene has exactly one mouse partner; all 15,165 pairs are
  annotated one-to-one with orthology confidence 1.
- Both species have finite positive exon lengths for every canonical gene.
- The candidate inference model strictly loads every state tensor and matches the
  parameter count. This does not prove its activation, residual, masking, or
  pooling semantics match the original implementation.
- GTEx contains 9,662 samples by 25,150 unique symbols, with **14,656/15,165 exact
  canonical matches**. The 509 unmatched symbols are listed in the report.

Machine-readable results, full missing-symbol list, and SHA-256 hashes of the
checkpoint, configuration, references, and GTEx matrix are in
[`artifacts/bridge-contract-2026-09-11.json`](artifacts/bridge-contract-2026-09-11.json).

## Unresolved before biological inference

1. Obtain the model and preprocessing source associated with checkpoint `r7hnr92k`,
   plus a training gene-list artifact/hash or equivalent provenance. Neither
   tensor dimensions nor a `log1p_tpm` label authenticates the gene order or TPM
   denominator. The candidate denominator currently follows the summer source:
   final canonical genes, species-specific exon lengths, then one TPM/log1p pass.
2. Resolve GTEx names using a versioned alias/stable-ID reference. Distinguish
   unique historical renames, ambiguous mappings, and genuinely unmeasured genes.
   Do not silently zero-fill the 509 missing exact symbols or change the gene set.
3. Compare the candidate forward pass with the original implementation on fixed
   inputs before accepting embeddings. Then run a bounded reference-data smoke
   test and select flight/ground OSDR samples with explicit study/tissue labels.

## Inference utility changes

`bridge_infer_gtex.py` now checks coverage before loading the checkpoint, validates
positive exon lengths and finite nonnegative counts, excludes empty tissue labels,
uses bounded batches (default one sample), and exports embeddings from unmasked
inputs. Random masking is used only in a separate reconstruction pass. Output
metadata records seed, pooling, hashes, and the unverified forward-pass status.
The utility remains exploratory; it currently stops on GTEx's coverage gap.

Ten focused tests pass, including a lightweight test model that verifies unmasked
embedding export, separate masking, batching, and empty-tissue exclusion. A real
GTEx invocation stopped at `found=14656/15165` before model loading, as intended.
These checks do not validate the original model's numerical forward semantics.

## Reproduce

From the repository root, with Python packages torch, numpy, pandas, h5py, pytest:

```bash
python3 fa26/audit_bridge_contract.py \
  --root fa26/bridge-rna-latest \
  --output fa26/artifacts/bridge-contract-2026-09-11.json
python3 -m pytest -q fa26/tests
```

The audit command exits successfully when report generation succeeds; consult
`status` and `blockers` in the JSON for scientific readiness. The hashes describe
the bundled inputs and are not an independent authentication of their origin.
