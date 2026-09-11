# D3 metadata-only readiness inventory

**Status:** preliminary metadata inventory; no candidate expression has been
accessed and no headroom outcome has been measured.

**Frozen candidate family:** controlled human disuse or bed-rest skeletal-muscle
studies. This is the first family in the sequential D3 protocol. The inventory is
used only to decide whether a full cohort contract can be frozen; it is not an
efficacy result and does not authorize training.

## Preliminary study inventory

| Accession | Structured contrast visible in public metadata | Approximate primary pre/post observations | Platform/readiness note | Preliminary disposition |
|---|---|---:|---|---|
| GSE104999 | 21-day bed rest, paired vastus lateralis biopsies | 24 | human skeletal-muscle expression; exact subject pairing still to freeze | retain for contract audit |
| GSE148152 | 84/90-day bed rest, before/after, with exercise arms | 42 | RNA expression; intervention arms must be represented explicitly | retain for contract audit |
| GSE24215 | 9-day bed rest, before/after with insulin and retraining dimensions | about 40 for the simplest paired contrast | multifactor design; one deterministic contrast must be frozen | retain conditionally |
| GSE211204 | baseline and 10-day unilateral limb suspension, plus recovery | 22 for baseline/post suspension | RNA-seq; recovery is outside the primary binary contrast | retain for contract audit |
| GSE113165 | before/after 5-day bed rest in younger and older adults | 54 | age is a prespecified nuisance/stratum, not a replacement label | retain for contract audit |
| GSE130722 | before/after 10-day bed rest | 20 | small study, useful only inside study-grouped aggregate | retain for contract audit |
| GSE186045 | before/after 5-week bed rest | 26 | RNA-seq; exact retained subjects and QC must be frozen | retain for contract audit |
| GSE226973 | before/after 70-day bed rest with countermeasure groups | about 44 | countermeasure assignments require deterministic handling | retain conditionally |
| GSE21496 | baseline, 48-hour unloading, and reload | 14 for baseline/post unloading | small; reload excluded from the primary binary contrast | retain for contract audit |
| GSE33886 | unilateral suspension in healthy adults; separate SCI/FES arm | 12 for healthy baseline/post suspension | SCI/FES arm is a distinct biological question and must be excluded from the primary contrast | retain conditionally |
| GSE14798 | bed-rest muscle biopsies | not counted | custom 6,681-gene muscle array is below the frozen 14,000-gene coverage rule | exclude before expression access |

The retained metadata candidates appear capable of reaching roughly 250–300
primary pre/post observations across ten studies, but this is **not yet a gate
pass**. The exact count can decrease after deterministic subject pairing,
platform/gene-coverage checks, duplicate-accession firewalls, and structured-label
harmonization. No replacement study may be added after candidate expression access.

## Remaining blockers before a cohort can be frozen

1. Resolve every accession into exact sample and donor/subject membership using
   public metadata only, then hash that membership.
2. Freeze the binary state definition per study, including the handling of exercise,
   countermeasure, recovery, insulin, SCI, and retraining arms.
3. Verify that state varies within every retained study and that grouped evaluation
   never separates paired samples from one subject.
4. Verify assay type, mapped-gene coverage, normalization contract, and the exact
   common model-input gene panel without reading outcomes.
5. Run accession, study, sample, and donor overlap checks against GTEx and the 63
   accessed ARCHS4 studies; absence from repository text is not sufficient evidence.
6. Reserve an untouched grouped confirmation subset before any supervised training.
7. Only after all metadata gates pass may raw/PCA headroom be measured in the primary
   organ. The frozen acceptance band is 0.60–0.90 AUROC, with study-bootstrap and
   single-study-dominance checks.

## Metadata sources

The inventory was assembled from the public NCBI GEO series pages for
[GSE104999](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE104999),
[GSE148152](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE148152),
[GSE24215](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE24215),
[GSE211204](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE211204),
[GSE113165](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE113165),
[GSE130722](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE130722),
[GSE186045](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE186045),
[GSE226973](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE226973),
[GSE21496](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE21496),
[GSE33886](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE33886), and
[GSE14798](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE14798).

Counts above are planning estimates from series metadata, not analyzed expression
sample counts. Exact membership and all hashes remain unresolved.
