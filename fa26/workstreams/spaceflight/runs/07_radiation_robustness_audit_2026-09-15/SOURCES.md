# Public source inputs

New files are in `sources/`; GSE242706 counts and prior family SOFT records remain in
run06's `sources/`. This run contains derived public expression, no private uploads.

- GSE230181 counts: https://www.ncbi.nlm.nih.gov/geo/download/?type=rnaseq_counts&acc=GSE230181&format=file&file=GSE230181_raw_counts_GRCh38.p13_NCBI.tsv.gz
- GSE111437 counts: https://www.ncbi.nlm.nih.gov/geo/download/?type=rnaseq_counts&acc=GSE111437&format=file&file=GSE111437_raw_counts_GRCh38.p13_NCBI.tsv.gz
- GSE111437 metadata: https://ftp.ncbi.nlm.nih.gov/geo/series/GSE111nnn/GSE111437/soft/GSE111437_family.soft.gz
- GSE242706 counts: https://www.ncbi.nlm.nih.gov/geo/download/?type=rnaseq_counts&acc=GSE242706&format=file&file=GSE242706_raw_counts_GRCh38.p13_NCBI.tsv.gz

GSE111437 contains multiple assay types; only the 12 RNA-seq GSMs in the NCBI count
matrix were eligible. Title dose/time agreed with characteristics for all 12. No
methylation profiles were treated as RNA expression. The encoder catalog includes all
12, so this is a new head-transfer challenge rather than fully unseen-model validation.
