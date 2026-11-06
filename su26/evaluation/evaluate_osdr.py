#!/usr/bin/env python3
# coding=utf-8
"""
Zero-shot OSDR evaluation for ExpressionPerformer checkpoints.

Downloads raw NASA OSDR mouse RNA-seq counts, preprocesses them to match
the bridge-rna training gene space, then evaluates each checkpoint using
masked-gene imputation at multiple mask ratios.

Usage:
  python evaluate_osdr.py \\
    --checkpoints checkpoints/human_5k/best_model.pt \\
                  checkpoints/mouse_5k/best_model.pt \\
                  checkpoints/mixed_5k/best_model.pt \\
    --output-dir results/osdr_eval

  # Skip download if cached parquet already exists:
  python evaluate_osdr.py \\
    --checkpoints checkpoints/human_5k/best_model.pt \\
    --osdr-parquet data/osdr/osdr_expression_v3.parquet \\
    --osdr-coverage data/osdr/osdr_coverage_v3.npz \\
    --output-dir results/osdr_eval
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import scipy.stats as stats
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from slim_performer_model import SLiMPerformerLayer

# ── Inline model definition (mirrors train_single.py) ─────────────────────────

class RotaryExpressionEmbedding(torch.nn.Module):
    def __init__(self, dim, base=100.0, mask_token_id=-10):
        super().__init__()
        self.dim = dim
        self.mask_token_id = mask_token_id
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)

    def forward(self, x):
        x_mask_idx = (x == self.mask_token_id).nonzero(as_tuple=False)
        freqs = torch.einsum("bi,j->bij", x, self.inv_freq)
        emb = torch.cat([freqs.sin(), freqs.cos()], dim=-1)
        if len(x_mask_idx) > 0:
            emb[x_mask_idx[:, 0], x_mask_idx[:, 1], :] = 0
        return emb


class ExpressionPerformer(torch.nn.Module):
    def __init__(
        self,
        num_genes,
        hidden_dim=256,
        n_heads=8,
        n_layers=4,
        ffn_dim=1024,
        ree_base=100.0,
        mask_token_id=-10,
        feature_type="sqr",
        compute_type="iter",
        gradient_checkpointing=False,
    ):
        super().__init__()
        self.num_genes = num_genes
        self.gene_embedding = torch.nn.Embedding(num_genes, hidden_dim)
        self.ree = RotaryExpressionEmbedding(hidden_dim, base=ree_base, mask_token_id=mask_token_id)
        self.layers = torch.nn.ModuleList(
            [
                SLiMPerformerLayer(hidden_dim, ffn_dim, n_heads, feature_type, compute_type, on_gptln=True)
                for _ in range(n_layers)
            ]
        )
        self.output_map = torch.nn.Linear(hidden_dim, 1)

    def forward(self, x):
        _, g = x.shape
        device = x.device
        gene_ids = torch.arange(g, device=device)
        gene_emb = self.gene_embedding(gene_ids)
        ree_emb = self.ree(x)
        h = gene_emb.unsqueeze(0) + ree_emb
        for layer in self.layers:
            rfs = layer.attention.sample_rfs(device)
            h = layer.full_forward(h, rfs)
        return self.output_map(h).squeeze(-1)


# ── Data paths ─────────────────────────────────────────────────────────────────

BRIDGE_RNA_DATA = Path(__file__).resolve().parent.parent / "data"
ORTHOLOG_FILE = BRIDGE_RNA_DATA / "ensembl" / "orthologs_one2one.txt"
CANONICAL_GENES_FILE = BRIDGE_RNA_DATA / "ensembl" / "canonical_genes_shared.txt"
MOUSE_EXON_FILE = BRIDGE_RNA_DATA / "gencode" / "gencode_v49_mouse_gene_exon_lengths.csv"

# NASA OSDR metadata (committed to this repo directly under data/osdr/)
# Users can override with --metadata-csv
DEFAULT_METADATA_CSV = BRIDGE_RNA_DATA / "osdr" / "metadata_new.csv"
DEFAULT_OSDR_CACHE = BRIDGE_RNA_DATA / "osdr"
OSDR_CACHE_SCHEMA_VERSION = 3
OSDR_EXPRESSION_FILENAME = "osdr_expression_v3.parquet"
OSDR_COVERAGE_FILENAME = "osdr_coverage_v3.npz"
OSDR_MANIFEST_FILENAME = "osdr_manifest_v3.json"
OSDR_EXPRESSION_SPACE = "log1p_tpm"
OSDR_NORMALIZATION_ORDER = "decode_valid_length_qc_map_aggregate_canonical_tpm_log1p"

# Mask ratios + block masking for evaluation
MASK_RATIOS = [0.15, 0.50, 0.80]
BLOCK_SIZES = []     # alphabetical vocabulary blocks are not a biological mask
BATCH_SIZE = 4      # inference batch size (conservative for 11GB 1080 Ti with 14k+ genes)


# ── Preprocessing helpers ──────────────────────────────────────────────────────

def load_ortholog_map() -> dict[str, str]:
    """Returns {mouse_gene_symbol → human_gene_symbol} for one-to-one orthologs."""
    df = pd.read_csv(ORTHOLOG_FILE, sep="\t")
    # columns: 'Gene name' (mouse), 'Human gene name' (human)
    df = df.dropna(subset=["Gene name", "Human gene name"])
    return dict(zip(df["Gene name"].str.strip(), df["Human gene name"].str.strip()))


def load_canonical_genes() -> list[str]:
    """Returns the ordered list of human gene symbols used in training."""
    df = pd.read_csv(CANONICAL_GENES_FILE, header=None)
    return [str(g).strip() for g in df.iloc[:, 0].tolist() if str(g).strip()]


def load_mouse_exon_lengths() -> pd.Series:
    """Returns Series indexed by mouse gene symbol with exon_length values."""
    df = pd.read_csv(MOUSE_EXON_FILE)
    # columns: gene_symbol, exon_length
    df = df.dropna(subset=["gene_symbol", "exon_length"])
    df = df.groupby("gene_symbol")["exon_length"].max()
    return df


def tpm_normalize_mouse(counts_df: pd.DataFrame, exon_lengths: pd.Series) -> pd.DataFrame:
    """
    TPM normalize mouse raw counts.
    counts_df: rows = genes (mouse symbols), cols = samples
    Returns TPM DataFrame, same shape.
    """
    L = exon_lengths.reindex(counts_df.index)
    if L.isna().any() or (L <= 0).any():
        missing = L.index[L.isna() | (L <= 0)].tolist()
        raise ValueError(f"missing/invalid exon lengths for genes: {missing[:5]}")
    L = L / 1000.0
    rpk = counts_df.div(L, axis=0)
    scaling = rpk.sum(axis=0)
    if scaling.isna().any() or (scaling <= 0).any():
        raise ValueError("TPM denominator is nonfinite or zero")
    tpm = rpk.div(scaling, axis=1) * 1e6
    return tpm.astype("float32")


def build_mouse_canonical_reference(
    canonical_genes: list[str],
    exon_lengths: pd.Series,
    ortholog_map: dict[str, str],
    osdr_mapping_path: Optional[Path] = None,
) -> tuple[dict[str, str], dict[str, str], pd.Series]:
    """Return training-exact symbol mappings plus ENSMUSG ID resolution."""
    canonical_set = set(canonical_genes)
    training_pairs = [
        (str(mouse).strip(), str(human).strip())
        for mouse, human in ortholog_map.items()
        if str(human).strip() in canonical_set
    ]
    symbol_to_human = dict(training_pairs)
    human_to_symbols: dict[str, list[str]] = {}
    for mouse, human in training_pairs:
        human_to_symbols.setdefault(human, []).append(mouse)
    missing = [gene for gene in canonical_genes if gene not in human_to_symbols]
    ambiguous = [gene for gene, symbols in human_to_symbols.items() if len(symbols) != 1]
    if missing or ambiguous:
        raise ValueError(
            "training ortholog map is not one-to-one for canonical genes: "
            f"missing={missing[:5]}, ambiguous={ambiguous[:5]}"
        )

    mouse_symbols = [human_to_symbols[gene][0] for gene in canonical_genes]
    if len(set(mouse_symbols)) != len(mouse_symbols):
        raise ValueError("training mouse symbols are not unique in canonical space")
    canonical_lengths = exon_lengths.reindex(mouse_symbols)
    canonical_lengths.index = canonical_genes
    if canonical_lengths.isna().any() or (canonical_lengths <= 0).any():
        bad = canonical_lengths.index[canonical_lengths.isna() | (canonical_lengths <= 0)].tolist()
        raise ValueError(f"canonical mouse exon lengths are missing: {bad[:5]}")

    # This table only decodes stable IDs to mouse symbols. Canonical identity
    # and normalization lengths stay pinned to the training ortholog table.
    path = osdr_mapping_path or (BRIDGE_RNA_DATA / "osdr" / "human_mouse_orthologs.csv")
    table = pd.read_csv(path).dropna(subset=["Mouse gene stable ID", "Mouse gene name"])
    table = table[table["Mouse homology type"] == "ortholog_one2one"].copy()
    table["Gene name"] = table["Gene name"].fillna("").astype(str).str.strip()
    table["Mouse gene stable ID"] = table["Mouse gene stable ID"].astype(str).str.strip()
    table["Mouse gene name"] = table["Mouse gene name"].astype(str).str.strip()
    human_to_mouse = {human: mouse for mouse, human in symbol_to_human.items()}
    table["resolved_mouse_symbol"] = [
        human_to_mouse.get(human, mouse)
        for human, mouse in zip(table["Gene name"], table["Mouse gene name"])
    ]
    conflicts = table.groupby("Mouse gene stable ID")["resolved_mouse_symbol"].nunique()
    conflicts = conflicts[conflicts > 1]
    if len(conflicts):
        raise ValueError(
            f"ENSMUSG IDs resolve to multiple mouse symbols: {conflicts.index[:5].tolist()}"
        )
    ensmusg_to_mouse = dict(zip(table["Mouse gene stable ID"], table["resolved_mouse_symbol"]))
    return symbol_to_human, ensmusg_to_mouse, canonical_lengths


def decode_mouse_counts_for_qc(
    counts: pd.DataFrame,
    exon_lengths: pd.Series,
    ensmusg_to_mouse: dict[str, str],
) -> pd.DataFrame:
    """Decode IDs, aggregate duplicate symbols, and retain valid-length genes."""
    values = counts.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("raw OSDR counts contain nonfinite values")
    if values.size and float(values.min()) < 0:
        raise ValueError("raw OSDR counts contain negative values")

    decoded = []
    for raw_id in counts.index.astype(str):
        gene_id = raw_id.strip()
        if gene_id.startswith("ENSMUSG"):
            gene_id = gene_id.split(".", 1)[0]
            decoded.append(ensmusg_to_mouse.get(gene_id, ""))
        else:
            decoded.append(gene_id)
    valid_length_symbols = set(exon_lengths.index[exon_lengths.notna() & (exon_lengths > 0)])
    use = np.asarray([symbol in valid_length_symbols for symbol in decoded], dtype=bool)
    if not use.any():
        raise ValueError("OSDR count table has no mouse genes with valid exon lengths")
    filtered = counts.loc[use].copy()
    filtered.index = np.asarray(decoded, dtype=object)[use]
    return filtered.groupby(level=0, sort=False).sum()


def canonicalize_mouse_counts(
    counts: pd.DataFrame,
    canonical_genes: list[str],
    symbol_to_human: dict[str, str],
    ensmusg_to_mouse: dict[str, str],
) -> tuple[pd.DataFrame, np.ndarray]:
    """Map and aggregate raw mouse counts in canonical human-symbol space."""
    values = counts.to_numpy(dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("raw OSDR counts contain nonfinite values")
    if values.size and float(values.min()) < 0:
        raise ValueError("raw OSDR counts contain negative values")
    mapped = []
    for raw_id in counts.index.astype(str):
        gene_id = raw_id.strip()
        if gene_id.startswith("ENSMUSG"):
            gene_id = gene_id.split(".", 1)[0]
            mouse_symbol = ensmusg_to_mouse.get(gene_id, "")
        else:
            mouse_symbol = gene_id
        mapped.append(symbol_to_human.get(mouse_symbol, ""))
    use = np.asarray([bool(gene) for gene in mapped])
    if not use.any():
        raise ValueError("OSDR count table has no strict canonical ortholog mappings")
    canonical = counts.loc[use].copy()
    canonical.index = np.asarray(mapped, dtype=object)[use]
    canonical = canonical.groupby(level=0, sort=False).sum()
    coverage = np.asarray([gene in canonical.index for gene in canonical_genes], dtype=bool)
    canonical = canonical.reindex(canonical_genes, fill_value=0.0)
    return canonical, coverage


def parse_spaceflight_condition(value) -> tuple[str, float]:
    """Preserve condition text and map only exact flight/ground labels."""
    if pd.isna(value):
        return "", float("nan")
    condition = " ".join(str(value).strip().split())
    normalized = condition.casefold()
    if normalized == "space flight":
        return condition, 1.0
    if normalized == "ground control":
        return condition, 0.0
    return condition, float("nan")


def validate_spaceflight_labels(frame: pd.DataFrame) -> np.ndarray:
    """Return numeric flight labels, rejecting missing columns or invalid states."""
    if "spaceflight" not in frame.columns:
        raise ValueError("OSDR expression is missing required 'spaceflight' labels")
    try:
        labels = pd.to_numeric(frame["spaceflight"], errors="raise").to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("OSDR spaceflight labels must be numeric 0, 1, or NaN") from exc
    invalid = ~(np.isnan(labels) | (labels == 0.0) | (labels == 1.0))
    if invalid.any():
        values = np.unique(labels[invalid]).tolist()
        raise ValueError(f"OSDR spaceflight labels contain invalid values: {values[:5]}")
    return labels


def validate_log1p_tpm(values: np.ndarray, context: str = "OSDR expression") -> None:
    """Reject raw TPM and other expression spaces before model inference."""
    values = np.asarray(values)
    if values.ndim != 2 or not values.shape[0] or not values.shape[1]:
        raise ValueError(f"{context} must be a nonempty 2D matrix")
    if not np.isfinite(values).all():
        raise ValueError(f"{context} contains nonfinite values")
    if float(values.min()) < -1e-6:
        raise ValueError(f"{context} contains negative log1p-TPM values")
    max_log_tpm = float(np.log1p(1e6))
    if float(values.max()) > max_log_tpm + 1e-3:
        raise ValueError(f"{context} is not log1p TPM (value exceeds log1p(1e6))")
    with np.errstate(over="ignore", invalid="ignore"):
        tpm_sums = np.expm1(values.astype(np.float64)).sum(axis=1)
    if not np.isfinite(tpm_sums).all() or not np.allclose(
        tpm_sums, 1e6, rtol=1e-3, atol=100.0
    ):
        raise ValueError(
            f"{context} is not log1p TPM (reconstructed TPM rows do not sum to 1e6)"
        )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_osdr_cache_fingerprint(
    metadata_csv: Path,
    canonical_genes: list[str],
    symbol_to_human: dict[str, str],
    ensmusg_to_mouse: dict[str, str],
    canonical_lengths: pd.Series,
    qc_min_nonzero: int,
) -> tuple[str, dict]:
    """Fingerprint lightweight inputs that determine the processed cache."""
    human_to_mouse = {human: mouse for mouse, human in symbol_to_human.items()}
    canonical_rows = [
        (gene, human_to_mouse[gene], float(canonical_lengths.loc[gene]))
        for gene in canonical_genes
    ]
    inputs = {
        "metadata_sha256": _sha256_bytes(Path(metadata_csv).read_bytes()),
        "canonical_reference_sha256": _sha256_bytes(
            json.dumps(canonical_rows, separators=(",", ":")).encode()
        ),
        "ensmusg_resolution_sha256": _sha256_bytes(
            json.dumps(sorted(ensmusg_to_mouse.items()), separators=(",", ":")).encode()
        ),
        "qc_min_nonzero": int(qc_min_nonzero),
        "expression_space": OSDR_EXPRESSION_SPACE,
        "normalization_order": OSDR_NORMALIZATION_ORDER,
    }
    fingerprint = _sha256_bytes(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    )
    return fingerprint, inputs


def _expression_sha256(values: np.ndarray, sample_ids: np.ndarray, genes: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(genes, separators=(",", ":")).encode())
    digest.update(json.dumps(sample_ids.astype(str).tolist(), separators=(",", ":")).encode())
    digest.update(np.ascontiguousarray(values, dtype="<f4").tobytes())
    return digest.hexdigest()


def download_osdr_study(study_id: str, counts_filename: str, cache_dir: Path) -> Optional[pd.DataFrame]:
    """
    Download a single OSDR study counts CSV from NASA OSDR.

    NASA retired the old genelab-data.ndc.nasa.gov static file server (now
    redirects to osdr.nasa.gov) in favor of a JSON file-listing API plus a
    signed-URL download endpoint. We look up the study's file list, find the
    entry matching counts_filename, and download its (redirect-chained,
    presigned S3) URL.
    Returns DataFrame indexed by gene, columns = samples, or None on failure.
    """
    import re
    import json
    import urllib.request

    osd_m = re.match(r"OSD-(\d+)", study_id)
    if not osd_m:
        print(f"    SKIP: could not parse OSD number from study_id={study_id}", flush=True)
        return None
    osd_num = osd_m.group(1)
    osd_key = f"OSD-{osd_num}"

    out_path = cache_dir / "raw" / counts_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists():
        print(f"    [cache hit] {counts_filename}", flush=True)
        return pd.read_csv(out_path, index_col=0)

    try:
        listing_url = f"https://osdr.nasa.gov/osdr/data/osd/files/{osd_num}"
        with urllib.request.urlopen(listing_url, timeout=30) as resp:
            listing = json.load(resp)
        study_files = listing["studies"][osd_key]["study_files"]
        match = next((f for f in study_files if f["file_name"] == counts_filename), None)
        if match is None:
            print(f"    SKIP: {counts_filename} not in OSDR file listing for {osd_key}", flush=True)
            return None
        download_url = "https://osdr.nasa.gov" + match["remote_url"]
        print(f"    Downloading {counts_filename} from {download_url} ...", flush=True)
        urllib.request.urlretrieve(download_url, out_path)
        df = pd.read_csv(out_path, index_col=0)
        print(f"    OK: {df.shape}", flush=True)
        return df
    except Exception as e:
        print(f"    WARN: {counts_filename} failed: {e}", flush=True)
        if out_path.exists():
            out_path.unlink()

    print(f"    SKIP: could not download {counts_filename}", flush=True)
    return None


def preprocess_osdr(
    metadata_csv: Path,
    osdr_raw_dir: Optional[Path],
    cache_dir: Path,
    ortholog_map: dict,
    canonical_genes: list[str],
    exon_lengths: pd.Series,
    download: bool = True,
    force_rebuild: bool = False,
    qc_min_nonzero: int = 14_000,
) -> pd.DataFrame:
    """
    Build (or reload from cache) an OSDR expression matrix aligned to bridge-rna gene space.

    Returns DataFrame: rows = samples, cols = canonical_genes (human symbols), values = log1p(TPM).
    Missing genes filled with 0.
    """
    cache_parquet = cache_dir / OSDR_EXPRESSION_FILENAME
    coverage_path = cache_dir / OSDR_COVERAGE_FILENAME
    manifest_path = cache_dir / OSDR_MANIFEST_FILENAME
    symbol_to_human, ensmusg_to_mouse, canonical_lengths = build_mouse_canonical_reference(
        canonical_genes, exon_lengths, ortholog_map
    )
    cache_fingerprint, cache_inputs = make_osdr_cache_fingerprint(
        metadata_csv,
        canonical_genes,
        symbol_to_human,
        ensmusg_to_mouse,
        canonical_lengths,
        qc_min_nonzero,
    )
    if cache_parquet.exists() and coverage_path.exists() and manifest_path.exists() and not force_rebuild:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("schema_version") != OSDR_CACHE_SCHEMA_VERSION:
            raise ValueError("OSDR cache schema is stale; rebuild with --force-rebuild")
        if manifest.get("expression_space") != OSDR_EXPRESSION_SPACE:
            raise ValueError("OSDR cache expression space is invalid; rebuild with --force-rebuild")
        if manifest.get("cache_fingerprint") != cache_fingerprint:
            raise ValueError("OSDR cache inputs changed; rebuild with --force-rebuild")
        cached = pd.read_parquet(cache_parquet)
        gene_values = cached[canonical_genes].to_numpy(dtype=np.float32)
        validate_log1p_tpm(gene_values, "corrected OSDR cache")
        validate_spaceflight_labels(cached)
        sample_ids = cached.index.astype(str).to_numpy()
        expression_sha256 = _expression_sha256(gene_values, sample_ids, canonical_genes)
        if manifest.get("expression_sha256") != expression_sha256:
            raise ValueError("OSDR cache expression hash differs from its manifest")
        load_coverage_artifact(
            coverage_path,
            sample_ids,
            canonical_genes,
            expected_cache_fingerprint=cache_fingerprint,
            expected_expression_sha256=expression_sha256,
        )
        print(f"[OSDR] Loading corrected cache: {cache_parquet}", flush=True)
        return cached

    print(f"[OSDR] Building expression matrix from {metadata_csv} ...", flush=True)
    meta = pd.read_csv(metadata_csv)

    # Reconstruction uses all bulk mouse RNA-seq samples. Binary downstream
    # analyses can select only exact Space Flight / Ground Control labels.
    required_cols = {"id.sample name", "id.accession", "counts_file", "counts_path",
                     "study.factor value.spaceflight", "study.characteristics.organism",
                     "has_rna_sequencing_rna_seq"}
    missing = required_cols - set(meta.columns)
    if missing:
        raise ValueError(f"Metadata CSV missing columns: {missing}")

    meta = meta[meta["study.characteristics.organism"] == "Mus musculus"]
    meta = meta[meta["has_rna_sequencing_rna_seq"] == 1]
    if "has_single_cell_rna_sequencing" in meta.columns:
        meta = meta[meta["has_single_cell_rna_sequencing"].fillna(0).astype(int) != 1]
    meta = meta.dropna(subset=["counts_file", "id.accession"])
    print(f"[OSDR] {len(meta)} bulk mouse RNA-seq metadata rows across "
          f"{meta['id.accession'].nunique()} studies", flush=True)

    study_frames = []
    coverage_frames = []

    for (study_id, counts_filename), grp in meta.groupby(["id.accession", "counts_file"]):

        # Try to load from local raw dir first
        counts_df = None
        if osdr_raw_dir is not None:
            local_path = osdr_raw_dir / counts_filename
            if local_path.exists():
                print(f"  [{study_id}] Loading local {counts_filename}", flush=True)
                counts_df = pd.read_csv(local_path, index_col=0)

        if counts_df is None and download:
            counts_df = download_osdr_study(study_id, counts_filename, cache_dir)

        if counts_df is None:
            print(f"  [{study_id}] SKIPPED (no data)", flush=True)
            continue

        # Normalize known filename-specific sample suffixes before matching.
        counts_df.columns = counts_df.columns.astype(str).str.strip()
        if "GLDS-462" in counts_filename:
            counts_df.columns = counts_df.columns.str.replace("_mRNA", "", regex=False)

        sample_names = grp["id.sample name"].tolist()
        available = [s for s in sample_names if s in counts_df.columns]
        if not available:
            print(f"  [{study_id}] WARN: no matching sample columns found", flush=True)
            continue

        sub = counts_df[available].copy()
        sub = sub.apply(pd.to_numeric, errors="raise")
        try:
            mouse_counts = decode_mouse_counts_for_qc(sub, exon_lengths, ensmusg_to_mouse)
        except ValueError as exc:
            print(f"  [{study_id}] WARN: {exc}", flush=True)
            continue
        nonzero = (mouse_counts > 0).sum(axis=0)
        mouse_counts = mouse_counts.loc[:, nonzero >= qc_min_nonzero]
        if mouse_counts.shape[1] == 0:
            print(f"  [{study_id}] WARN: all samples failed QC", flush=True)
            continue

        try:
            canonical_counts, coverage = canonicalize_mouse_counts(
                mouse_counts, canonical_genes, symbol_to_human, ensmusg_to_mouse
            )
        except ValueError as exc:
            print(f"  [{study_id}] WARN: {exc}", flush=True)
            continue
        tpm = tpm_normalize_mouse(canonical_counts, canonical_lengths)
        log_tpm = np.log1p(tpm).T.astype("float32")
        if not np.isfinite(log_tpm.to_numpy()).all():
            raise ValueError(f"{study_id} preprocessing produced nonfinite log1p TPM")

        metadata_by_sample = grp.drop_duplicates("id.sample name").set_index("id.sample name")
        parsed = [
            parse_spaceflight_condition(
                metadata_by_sample.loc[sample, "study.factor value.spaceflight"]
            )
            for sample in log_tpm.index
        ]
        original_names = log_tpm.index.astype(str).tolist()
        sample_uids = [f"{study_id}::{sample}" for sample in original_names]
        log_tpm.index = sample_uids
        log_tpm["sample_name"] = original_names
        log_tpm["condition"] = [condition for condition, _ in parsed]
        log_tpm["spaceflight"] = [label for _, label in parsed]
        log_tpm["study_id"] = study_id
        log_tpm["species"] = "mouse"
        study_frames.append(log_tpm)
        coverage_frames.append(np.broadcast_to(coverage, (len(log_tpm), len(coverage))).copy())
        print(f"  [{study_id}] {log_tpm.shape[0]} samples, {int(coverage.sum())} genes measured", flush=True)

    if not study_frames:
        raise RuntimeError("No OSDR studies loaded — check metadata, raw data dir, and download flag.")

    aligned = pd.concat(study_frames, axis=0)
    if aligned.index.duplicated().any():
        raise ValueError("corrected OSDR sample UIDs are not unique")
    gene_values = aligned[canonical_genes].to_numpy(dtype=np.float32)
    validate_log1p_tpm(gene_values, "corrected OSDR expression")
    validate_spaceflight_labels(aligned)
    coverage_matrix = np.concatenate(coverage_frames, axis=0).astype(bool, copy=False)
    if coverage_matrix.shape != gene_values.shape:
        raise RuntimeError("OSDR coverage and expression shapes differ")
    aligned.index.name = "sample_id"
    sample_ids = aligned.index.astype(str).to_numpy()
    expression_sha256 = _expression_sha256(gene_values, sample_ids, canonical_genes)

    cache_dir.mkdir(parents=True, exist_ok=True)
    aligned.to_parquet(cache_parquet)
    np.savez_compressed(
        coverage_path,
        schema_version=np.int64(OSDR_CACHE_SCHEMA_VERSION),
        expression_space=np.asarray(OSDR_EXPRESSION_SPACE),
        cache_fingerprint=np.asarray(cache_fingerprint),
        expression_sha256=np.asarray(expression_sha256),
        coverage=coverage_matrix,
        genes=np.asarray(canonical_genes, dtype="U"),
        sample_ids=sample_ids.astype("U"),
    )
    manifest = {
        "schema_version": OSDR_CACHE_SCHEMA_VERSION,
        "expression_space": OSDR_EXPRESSION_SPACE,
        "normalization_order": OSDR_NORMALIZATION_ORDER,
        "cache_fingerprint": cache_fingerprint,
        "cache_inputs": cache_inputs,
        "expression_sha256": expression_sha256,
        "qc_min_nonzero": qc_min_nonzero,
        "n_samples": len(aligned),
        "n_genes": len(canonical_genes),
        "n_studies": int(aligned["study_id"].nunique()),
        "flight": int((aligned["spaceflight"] == 1).sum()),
        "ground_control": int((aligned["spaceflight"] == 0).sum()),
        "unlabeled_or_other": int(aligned["spaceflight"].isna().sum()),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"[OSDR] Cached corrected expression to {cache_parquet}  shape={aligned.shape}", flush=True)
    print(f"[OSDR] Coverage: {coverage_path}; labels: "
          f"{manifest['flight']} flight / {manifest['ground_control']} exact ground / "
          f"{manifest['unlabeled_or_other']} other", flush=True)
    return aligned


def load_coverage_artifact(
    coverage_path: Path,
    sample_ids: np.ndarray,
    gene_order: list[str],
    expected_cache_fingerprint: Optional[str] = None,
    expected_expression_sha256: Optional[str] = None,
) -> np.ndarray:
    with np.load(coverage_path, allow_pickle=False) as z:
        required = {
            "coverage", "genes", "sample_ids", "schema_version", "expression_space",
            "cache_fingerprint", "expression_sha256",
        }
        if not required.issubset(z.files):
            raise ValueError(f"coverage artifact must contain {sorted(required)}")
        if int(z["schema_version"]) != OSDR_CACHE_SCHEMA_VERSION:
            raise ValueError("OSDR coverage artifact uses a stale schema")
        if str(z["expression_space"].item()) != OSDR_EXPRESSION_SPACE:
            raise ValueError("OSDR coverage artifact has the wrong expression space")
        if (
            expected_cache_fingerprint is not None
            and str(z["cache_fingerprint"].item()) != expected_cache_fingerprint
        ):
            raise ValueError("OSDR coverage and manifest cache fingerprints differ")
        if (
            expected_expression_sha256 is not None
            and str(z["expression_sha256"].item()) != expected_expression_sha256
        ):
            raise ValueError("OSDR coverage and expression hashes differ")
        if not np.array_equal(z["sample_ids"].astype(str), sample_ids.astype(str)):
            raise ValueError("OSDR coverage sample order differs from expression parquet")
        artifact_genes = z["genes"].astype(str).tolist()
        if len(set(artifact_genes)) != len(artifact_genes):
            raise ValueError("OSDR coverage artifact contains duplicate genes")
        gene_to_idx = {gene: i for i, gene in enumerate(artifact_genes)}
        missing = [gene for gene in gene_order if gene not in gene_to_idx]
        if missing:
            raise ValueError(f"OSDR coverage is missing evaluation genes: {missing[:5]}")
        coverage = np.asarray(z["coverage"], dtype=bool)
        if coverage.shape != (len(sample_ids), len(artifact_genes)):
            raise ValueError("OSDR coverage shape does not match its labels")
        return coverage[:, [gene_to_idx[gene] for gene in gene_order]]


def load_gene_mean_artifact(path: Path, gene_order: list[str]) -> np.ndarray:
    z = np.load(path, allow_pickle=False)
    if not {"genes", "mean"}.issubset(z.files):
        raise ValueError("gene-mean artifact must contain genes and mean")
    genes = z["genes"].astype(str).tolist()
    mean = np.asarray(z["mean"], dtype=np.float32)
    gene_to_idx = {gene: i for i, gene in enumerate(genes)}
    missing = [gene for gene in gene_order if gene not in gene_to_idx]
    if missing:
        raise ValueError(f"gene-mean artifact is missing evaluation genes: {missing[:5]}")
    aligned = mean[[gene_to_idx[gene] for gene in gene_order]]
    if not np.isfinite(aligned).all():
        raise ValueError("gene-mean artifact contains nonfinite values")
    return aligned


# ── Checkpoint loading ─────────────────────────────────────────────────────────

def load_checkpoint(ckpt_path: Path, device: torch.device) -> tuple[ExpressionPerformer, dict, list[str]]:
    """
    Load ExpressionPerformer from a checkpoint saved by train_single.py.
    Returns (model, config, gene_list) where gene_list is ordered gene symbols.
    """
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg = dict(ckpt.get("config", {}))
    sd = {k.replace("module.", "", 1): v for k, v in ckpt["model_state_dict"].items()}

    num_genes = int(cfg.get("num_genes") or sd["gene_embedding.weight"].shape[0])

    model = ExpressionPerformer(
        num_genes=num_genes,
        hidden_dim=int(cfg.get("hidden_dim", 768)),
        n_heads=int(cfg.get("num_heads", 8)),
        n_layers=int(cfg.get("num_layers", 2)),
        ffn_dim=int(cfg.get("ffn_dim", cfg.get("hidden_dim", 768) * 4)),
        ree_base=float(cfg.get("ree_base", 100.0)),
        mask_token_id=int(cfg.get("mask_token", -10)),
        feature_type=str(cfg.get("feature_type", "sqr")),
        compute_type=str(cfg.get("compute_type", "iter")),
    )
    model.load_state_dict(sd, strict=True)
    model.to(device)
    model.eval()

    # Recover gene list from training parquet if path stored in config
    gene_list = []
    parquet_path = cfg.get("expression_parquet", "")
    if parquet_path and Path(parquet_path).exists():
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(parquet_path)
        gene_list = [c for c in pf.schema_arrow.names
                     if c not in ("geo_accession", "__index_level_0__", "sample_id")]
    elif num_genes == 15448:
        # v2 experts all train on the shared canonical vocabulary in canonical
        # order (verified directly against each variant's training parquet
        # schema -- see progress.md), so when the parquet itself isn't present
        # on this machine (multi-instance training split across VMs) we can
        # recover the same gene list from the canonical file instead of
        # failing alignment entirely.
        print(f"    [WARN] training parquet {parquet_path!r} not found locally; "
              f"falling back to canonical_genes_shared.txt order (verified match "
              f"for v2 experts)", flush=True)
        gene_list = load_canonical_genes()

    return model, cfg, gene_list


# ── Evaluation ─────────────────────────────────────────────────────────────────

def pearson_per_sample(pred: np.ndarray, true: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    """Per-sample Pearson r, computed only on masked positions."""
    rs = []
    for i in range(len(pred)):
        p = pred[i, mask_idx[i]]
        t = true[i, mask_idx[i]]
        if len(p) < 3 or np.std(t) < 1e-9:
            rs.append(float("nan"))
        elif np.std(p) < 1e-9:
            rs.append(0.0)
        else:
            rs.append(float(np.corrcoef(p, t)[0, 1]))
    return np.array(rs)


def spearman_per_sample(pred: np.ndarray, true: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    rs = []
    for i in range(len(pred)):
        p = pred[i, mask_idx[i]]
        t = true[i, mask_idx[i]]
        if len(p) < 3 or np.std(p) < 1e-9 or np.std(t) < 1e-9:
            rs.append(float("nan"))
        else:
            r, _ = stats.spearmanr(p, t)
            rs.append(float(r))
    return np.array(rs)


def mse_per_sample(pred: np.ndarray, true: np.ndarray, mask_idx: np.ndarray) -> np.ndarray:
    mses = []
    for i in range(len(pred)):
        p = pred[i, mask_idx[i]]
        t = true[i, mask_idx[i]]
        mses.append(float(np.mean((p - t) ** 2)))
    return np.array(mses)


def make_mask_random(num_genes: int, num_mask: int, n: int, rng: np.random.Generator) -> np.ndarray:
    mask_idx = np.stack([rng.choice(num_genes, num_mask, replace=False) for _ in range(n)])
    return mask_idx


def make_mask_random_coverage(
    coverage: np.ndarray, num_mask: int, rng: np.random.Generator
) -> np.ndarray:
    coverage = np.asarray(coverage, dtype=bool)
    if coverage.ndim != 2:
        raise ValueError("coverage must have shape (samples, genes)")
    if np.any(coverage.sum(axis=1) < num_mask):
        raise ValueError("at least one sample has insufficient measured genes for masking")
    return np.stack([
        rng.choice(np.flatnonzero(coverage[i]), num_mask, replace=False)
        for i in range(len(coverage))
    ])


def make_mask_block(num_genes: int, block_size: int, n: int, rng: np.random.Generator) -> np.ndarray:
    starts = rng.integers(0, num_genes - block_size + 1, size=n)
    mask_idx = np.stack([np.arange(s, s + block_size) for s in starts])
    return mask_idx


def evaluate_model(
    model: ExpressionPerformer,
    x_true: np.ndarray,   # (N, num_train_genes) — aligned to training gene space
    osdr_gene_mask: np.ndarray,  # bool (num_train_genes,) — True where OSDR has data
    mask_ratios: list[float],
    block_sizes: list[int],
    batch_size: int,
    device: torch.device,
    mask_token: float = -10.0,
    rng_seed: int = 42,
    gene_mean_reference: np.ndarray | None = None,
) -> dict:
    """
    Runs zero-shot imputation on x_true.
    x_true: log1p(TPM) in training gene order (missing genes already zeroed).
    Returns dict of metrics per masking strategy.
    """
    rng = np.random.default_rng(rng_seed)
    N, G = x_true.shape
    results = {}

    if not np.isfinite(x_true).all():
        raise ValueError("evaluation expression contains nonfinite values")
    coverage = np.asarray(osdr_gene_mask, dtype=bool)
    if coverage.ndim == 1:
        coverage = np.broadcast_to(coverage, (N, G)).copy()
    if coverage.shape != (N, G):
        raise ValueError("OSDR coverage must have shape (genes,) or (samples, genes)")
    min_available = int(coverage.sum(axis=1).min())
    if gene_mean_reference is not None:
        gene_mean_reference = np.asarray(gene_mean_reference, dtype=np.float32)
        if gene_mean_reference.shape != (G,) or not np.isfinite(gene_mean_reference).all():
            raise ValueError("gene_mean_reference must be a finite vector in model gene order")

    strategies = (
        [(f"random_{int(r*100)}pct", "random", max(3, int(min_available * r)))
         for r in mask_ratios]
        + [(f"block_{b}", "block", b) for b in block_sizes]
    )

    for strat_name, strat_type, param in strategies:
        print(f"    masking: {strat_name} ...", flush=True)
        all_pearson, all_spearman, all_mse = [], [], []
        all_pearson_gene_mean, all_pearson_sample_mean = [], []
        all_mse_gene_mean, all_mse_sample_mean = [], []

        n_batches = (N + batch_size - 1) // batch_size
        for batch_idx, batch_start in enumerate(range(0, N, batch_size)):
            if batch_idx % max(1, n_batches // 5) == 0:
                print(f"      batch {batch_idx+1}/{n_batches}", flush=True)
            batch = x_true[batch_start : batch_start + batch_size]
            b = len(batch)

            batch_coverage = coverage[batch_start : batch_start + b]
            if strat_type == "random":
                mask_idx = make_mask_random_coverage(batch_coverage, param, rng)
            else:
                if not np.all(batch_coverage):
                    raise ValueError("block masks are unsupported with incomplete per-sample coverage")
                mask_idx = make_mask_block(G, param, b, rng)

            # Build masked input
            x_masked = batch.copy()
            x_masked[~batch_coverage] = mask_token
            for i in range(b):
                x_masked[i, mask_idx[i]] = mask_token

            # Model prediction
            with torch.no_grad():
                x_t = torch.from_numpy(x_masked).to(device)
                pred_t = model(x_t).cpu().numpy()
            if not np.isfinite(pred_t).all():
                raise ValueError("model produced nonfinite OSDR predictions")

            # Metrics (model)
            all_pearson.append(pearson_per_sample(pred_t, batch, mask_idx))
            all_spearman.append(spearman_per_sample(pred_t, batch, mask_idx))
            all_mse.append(mse_per_sample(pred_t, batch, mask_idx))

            # Baselines — for masked positions, predict gene mean or sample mean
            # Gene mean baseline: for each masked gene j, predict gene_mean[j]
            if gene_mean_reference is not None:
                pred_gm = np.broadcast_to(gene_mean_reference, (b, G)).copy()
                all_pearson_gene_mean.append(pearson_per_sample(pred_gm, batch, mask_idx))
                all_mse_gene_mean.append(mse_per_sample(pred_gm, batch, mask_idx))

            # Sample mean uses observed, unmasked genes only; masked truths never
            # contribute to their own baseline prediction.
            sample_means = np.empty((b, 1), dtype=np.float32)
            for i in range(b):
                visible = batch_coverage[i].copy()
                visible[mask_idx[i]] = False
                sample_means[i, 0] = float(batch[i, visible].mean())
            pred_sm = np.broadcast_to(sample_means, (b, G)).copy()
            all_pearson_sample_mean.append(pearson_per_sample(pred_sm, batch, mask_idx))
            all_mse_sample_mean.append(mse_per_sample(pred_sm, batch, mask_idx))

        def cat(lst):
            return np.concatenate(lst)

        def nanmean(arr):
            return float(np.nanmean(arr))

        def nanmedian(arr):
            return float(np.nanmedian(arr))

        results[strat_name] = {
            "n_samples": N,
            "pearson_mean":        nanmean(cat(all_pearson)),
            "pearson_median":      nanmedian(cat(all_pearson)),
            "spearman_mean":       nanmean(cat(all_spearman)),
            "spearman_median":     nanmedian(cat(all_spearman)),
            "mse_mean":            nanmean(cat(all_mse)),
            "baseline_gene_mean_pearson":   nanmean(cat(all_pearson_gene_mean)) if all_pearson_gene_mean else float("nan"),
            "baseline_sample_mean_pearson": nanmean(cat(all_pearson_sample_mean)),
            "baseline_gene_mean_mse":       nanmean(cat(all_mse_gene_mean)) if all_mse_gene_mean else float("nan"),
            "baseline_sample_mean_mse":     nanmean(cat(all_mse_sample_mean)),
        }

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Zero-shot OSDR evaluation")
    parser.add_argument("--checkpoints", nargs="+", required=True,
                        help="Paths to best_model.pt checkpoints (one per variant)")
    parser.add_argument("--output-dir", default="results/osdr_eval",
                        help="Directory to write results CSV and JSON")
    parser.add_argument("--osdr-parquet", default=None,
                        help="Pre-built OSDR expression parquet (skips download+preprocess)")
    parser.add_argument("--osdr-coverage", default=None,
                        help="Corrected per-sample coverage NPZ paired with --osdr-parquet")
    parser.add_argument("--metadata-csv", default=None,
                        help="OSDR metadata CSV (default: data/osdr/metadata_new.csv)")
    parser.add_argument("--osdr-raw-dir", default=None,
                        help="Directory containing pre-downloaded GLDS-*.csv raw count files")
    parser.add_argument("--no-download", action="store_true",
                        help="Do not download OSDR data from NASA (requires --osdr-parquet or --osdr-raw-dir)")
    parser.add_argument("--force-rebuild", action="store_true",
                        help="Ignore and rebuild the versioned corrected OSDR cache")
    parser.add_argument("--baseline-mean-npz", default=None,
                        help="Disjoint training-derived log1p-TPM gene means")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--device", default="auto",
                        help="cuda / cpu / auto")
    parser.add_argument("--wandb", action="store_true", help="Log results to W&B")
    args = parser.parse_args()

    # Device
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)

    if device.type == "cpu":
        n_threads = int(os.environ.get("OMP_NUM_THREADS", torch.get_num_threads()))
        torch.set_num_threads(n_threads)
        print(f"[EVAL] Device: cpu ({n_threads} threads)", flush=True)
    else:
        print(f"[EVAL] Device: {device}", flush=True)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load gene reference data ────────────────────────────────────────────────
    print("[EVAL] Loading reference gene data...", flush=True)
    ortholog_map = load_ortholog_map()
    canonical_genes = load_canonical_genes()
    exon_lengths = load_mouse_exon_lengths()
    print(f"  + {len(ortholog_map):,} mouse→human ortholog pairs")
    print(f"  + {len(canonical_genes):,} canonical genes")

    # ── Build / load OSDR expression matrix ────────────────────────────────────
    if args.osdr_parquet:
        osdr_parquet = Path(args.osdr_parquet)
        if not osdr_parquet.exists():
            raise FileNotFoundError(f"OSDR parquet not found: {osdr_parquet}")
        print(f"[EVAL] Loading OSDR parquet: {osdr_parquet}", flush=True)
        osdr_df = pd.read_parquet(osdr_parquet)
        if not args.osdr_coverage:
            raise ValueError(
                "--osdr-coverage is required with a pre-built OSDR parquet; "
                "measured zeros cannot be distinguished from absent genes otherwise"
            )
        coverage_path = Path(args.osdr_coverage)
    else:
        metadata_csv = Path(args.metadata_csv) if args.metadata_csv else DEFAULT_METADATA_CSV
        if not metadata_csv.exists():
            raise FileNotFoundError(
                f"OSDR metadata not found at {metadata_csv}.\n"
                "Supply --metadata-csv or ensure data/osdr/metadata_new.csv exists."
            )

        raw_dir = Path(args.osdr_raw_dir) if args.osdr_raw_dir else None
        osdr_df = preprocess_osdr(
            metadata_csv=metadata_csv,
            osdr_raw_dir=raw_dir,
            cache_dir=DEFAULT_OSDR_CACHE,
            ortholog_map=ortholog_map,
            canonical_genes=canonical_genes,
            exon_lengths=exon_lengths,
            download=not args.no_download,
            force_rebuild=args.force_rebuild,
        )
        coverage_path = DEFAULT_OSDR_CACHE / OSDR_COVERAGE_FILENAME

    print(f"[EVAL] OSDR shape: {osdr_df.shape}", flush=True)

    # Separate expression from metadata columns
    x_osdr = osdr_df[canonical_genes].values.astype("float32")  # (N, num_canonical_genes)
    validate_log1p_tpm(x_osdr)
    sample_ids = osdr_df.index.astype(str).to_numpy()
    expression_sha256 = _expression_sha256(x_osdr, sample_ids, canonical_genes)
    osdr_gene_mask = load_coverage_artifact(
        coverage_path,
        sample_ids,
        canonical_genes,
        expected_expression_sha256=expression_sha256,
    )
    baseline_mean = (
        load_gene_mean_artifact(Path(args.baseline_mean_npz), canonical_genes)
        if args.baseline_mean_npz else None
    )

    spaceflight_labels = validate_spaceflight_labels(osdr_df)
    n_flight   = int(np.nansum(spaceflight_labels == 1))
    n_control  = int(np.nansum(spaceflight_labels == 0))
    n_unlabeled = int(np.sum(np.isnan(spaceflight_labels.astype(float))))

    print(f"[EVAL] {x_osdr.shape[0]} samples: {n_flight} spaceflight, "
          f"{n_control} control, {n_unlabeled} unlabeled", flush=True)
    coverage_counts = osdr_gene_mask.sum(axis=1)
    print(f"[EVAL] Per-sample gene coverage: min={coverage_counts.min()}, "
          f"median={int(np.median(coverage_counts))}, max={coverage_counts.max()} "
          f"of {len(canonical_genes)}", flush=True)

    # ── W&B ────────────────────────────────────────────────────────────────────
    wandb_run = None
    if args.wandb:
        try:
            import wandb as wb
            wandb_run = wb.init(
                project=os.environ.get("WANDB_PROJECT", "bridge-rna"),
                name="osdr_eval",
                group="osdr_benchmark",
                config={
                    "n_samples": x_osdr.shape[0],
                    "n_genes": x_osdr.shape[1],
                    "osdr_gene_coverage_min": int(coverage_counts.min()),
                    "osdr_gene_coverage_median": int(np.median(coverage_counts)),
                    "mask_ratios": MASK_RATIOS,
                    "block_sizes": BLOCK_SIZES,
                    "spaceflight_samples": n_flight,
                    "control_samples": n_control,
                },
            )
        except Exception as e:
            print(f"[WARN] W&B init failed: {e}", flush=True)

    # ── Evaluate each checkpoint ───────────────────────────────────────────────
    all_results = []

    for ckpt_path_str in args.checkpoints:
        ckpt_path = Path(ckpt_path_str)
        if not ckpt_path.exists():
            print(f"[WARN] Checkpoint not found: {ckpt_path} — skipping", flush=True)
            continue

        # Infer variant name from path
        variant = ckpt_path.parent.name
        if variant == ckpt_path.stem:
            variant = ckpt_path.parent.parent.name
        print(f"\n[EVAL] === Evaluating {variant} ({ckpt_path}) ===", flush=True)

        t0 = time.time()
        model, cfg, train_gene_list = load_checkpoint(ckpt_path, device)

        # If we have training gene list, verify alignment
        if train_gene_list:
            if train_gene_list != canonical_genes:
                print(f"  [WARN] Training gene list ({len(train_gene_list)}) differs from canonical ({len(canonical_genes)})")
                # Re-align OSDR to training gene order
                gene_order = train_gene_list
                x_aligned = pd.DataFrame(x_osdr, columns=canonical_genes).reindex(columns=gene_order, fill_value=0.0).values.astype("float32")
                canonical_to_idx = {gene: i for i, gene in enumerate(canonical_genes)}
                missing = [gene for gene in gene_order if gene not in canonical_to_idx]
                if missing:
                    raise ValueError(f"checkpoint genes are absent from OSDR canonical space: {missing[:5]}")
                gene_mask_aligned = osdr_gene_mask[:, [canonical_to_idx[g] for g in gene_order]]
                baseline_aligned = (
                    baseline_mean[[canonical_to_idx[g] for g in gene_order]]
                    if baseline_mean is not None else None
                )
            else:
                x_aligned = x_osdr
                gene_mask_aligned = osdr_gene_mask
                baseline_aligned = baseline_mean
        else:
            x_aligned = x_osdr
            gene_mask_aligned = osdr_gene_mask
            baseline_aligned = baseline_mean

        print(f"  Model: {sum(p.numel() for p in model.parameters()):,} params", flush=True)
        print(f"  Evaluating {x_aligned.shape[0]} samples, {x_aligned.shape[1]} genes ...", flush=True)

        mask_token = float(cfg.get("mask_token", -10.0))

        metrics = evaluate_model(
            model=model,
            x_true=x_aligned,
            osdr_gene_mask=gene_mask_aligned,
            mask_ratios=MASK_RATIOS,
            block_sizes=BLOCK_SIZES,
            batch_size=args.batch_size,
            device=device,
            mask_token=mask_token,
            gene_mean_reference=baseline_aligned,
        )

        elapsed = time.time() - t0
        print(f"  Done in {elapsed:.1f}s", flush=True)

        # Pretty-print summary
        print(f"\n  {'Masking':<20} {'Pearson':>10} {'Spearman':>10} {'MSE':>10} {'BL_GeneMean':>12} {'BL_SampMean':>12}")
        print(f"  {'-'*76}")
        for strat, m in metrics.items():
            print(f"  {strat:<20} {m['pearson_mean']:>10.4f} {m['spearman_mean']:>10.4f} "
                  f"{m['mse_mean']:>10.4f} {m['baseline_gene_mean_pearson']:>12.4f} "
                  f"{m['baseline_sample_mean_pearson']:>12.4f}")

        for strat, m in metrics.items():
            row = {
                "variant": variant,
                "checkpoint": str(ckpt_path),
                "masking_strategy": strat,
                **m,
            }
            all_results.append(row)

        # W&B logging
        if wandb_run is not None:
            for strat, m in metrics.items():
                wb.log({f"{variant}/{strat}/{k}": v for k, v in m.items()})

    # ── Save results ───────────────────────────────────────────────────────────
    if not all_results:
        print("\n[WARN] No results to save.", flush=True)
        return

    results_df = pd.DataFrame(all_results)
    results_csv = output_dir / "osdr_eval_results.csv"
    results_json = output_dir / "osdr_eval_results.json"
    results_df.to_csv(results_csv, index=False)
    with open(results_json, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n[EVAL] Results saved:")
    print(f"  CSV:  {results_csv}")
    print(f"  JSON: {results_json}")

    # Summary table
    print("\n[EVAL] === SUMMARY: Pearson correlation by variant and masking strategy ===")
    pivot = results_df.pivot_table(
        index="variant", columns="masking_strategy", values="pearson_mean", aggfunc="first"
    )
    print(pivot.to_string())

    if wandb_run is not None:
        wandb_run.log({"summary_table": wb.Table(dataframe=results_df)})
        wandb_run.finish()


if __name__ == "__main__":
    main()
