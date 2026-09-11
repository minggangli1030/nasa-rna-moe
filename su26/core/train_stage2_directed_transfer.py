#!/usr/bin/env python3
"""Train schedule-bound K1 adapters for Stage 2 directed organ transfer.

Every arm starts from the same seed-specific semantic initialization and consumes
the exact source-paired schedule compiled before model fitting. The pooled trunk is
frozen. Evaluation is restricted to donor-disjoint GTEx calibration rows named in
each arm definition; no external or final-test data are accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Sampler


CORE_DIR = Path(__file__).resolve().parent
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from train_fixed_partition_moe import FixedGeneMaskDataset, _resolve_device
from train_latent_moe import ResidualExpert, _masked_row_mse, load_frozen_trunk
from train_manifest import (
    DeterministicMaskedExpressionDataset,
    load_expression_rows,
    read_manifest,
    seed_data_worker,
    seed_everything,
    select_manifest_rows,
    sha256_file,
    sha256_json,
    sha256_lines,
    stable_seed,
    validate_expression_metadata,
)


REQUIRED_SCHEDULE_COLUMNS = {
    "arm_id",
    "draw_number",
    "batch_number",
    "batch_position",
    "source_draw_number",
    "source_role",
    "source_label",
    "sample_id",
    "donor_id",
    "organ",
    "series_group_id",
}
PRESPECIFIED_SEEDS = (17, 42, 101)


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _tensor_state_sha256(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        value = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("utf-8"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def _initialize_expert(
    *,
    hidden_dim: int,
    adapter_dim: int,
    training_seed: int,
    initialization_key: str,
) -> ResidualExpert:
    expert_seed = stable_seed(
        training_seed, "fixed_semantic_expert", initialization_key
    ) % (2**63 - 1)
    with torch.random.fork_rng(devices=[], enabled=True):
        torch.manual_seed(expert_seed)
        return ResidualExpert(hidden_dim, adapter_dim)


def _load_contract(
    *,
    schedules_path: Path,
    definitions_path: Path,
    report_path: Path,
    manifest_path: Path,
    expected_schedule_sha256: str,
    expected_definitions_sha256: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    report = json.loads(report_path.read_text())
    if (
        report.get("status") != "complete"
        or report.get("development_only") is not True
        or report.get("expression_loaded") is not False
        or report.get("model_fit") is not False
        or report.get("best_seed_selection_allowed") is not False
    ):
        raise ValueError("schedule report does not satisfy the development firewall")
    actual_schedule_hash = sha256_file(schedules_path)
    actual_definitions_hash = sha256_file(definitions_path)
    if actual_schedule_hash != str(expected_schedule_sha256).lower():
        raise ValueError("training schedule differs from expected SHA256")
    if actual_definitions_hash != str(expected_definitions_sha256).lower():
        raise ValueError("arm definitions differ from expected SHA256")
    hashes = report.get("hashes", {})
    if actual_schedule_hash != hashes.get("training_schedules_sha256"):
        raise ValueError("schedule report does not pin the training schedule")
    if actual_definitions_hash != hashes.get("arm_definitions_sha256"):
        raise ValueError("schedule report does not pin the arm definitions")
    if sha256_file(manifest_path) != hashes.get("manifest_sha256"):
        raise ValueError("schedule report manifest hash differs from input manifest")

    definitions_payload = json.loads(definitions_path.read_text())
    definitions = definitions_payload.get("arms")
    if (
        definitions_payload.get("schema_version") != 1
        or not isinstance(definitions, list)
        or not definitions
    ):
        raise ValueError("arm definitions are invalid")
    if definitions_payload.get("initialization_key") != report.get(
        "initialization_key"
    ):
        raise ValueError("initialization key differs between schedule artifacts")
    schedules = pd.read_parquet(schedules_path)
    missing = sorted(REQUIRED_SCHEDULE_COLUMNS - set(schedules.columns))
    if missing:
        raise ValueError(f"training schedules lack required columns: {missing}")
    expected_arm_ids = [str(value["arm_id"]) for value in definitions]
    if len(expected_arm_ids) != len(set(expected_arm_ids)):
        raise ValueError("arm definitions contain duplicate arm IDs")
    if set(schedules["arm_id"].astype(str)) != set(expected_arm_ids):
        raise ValueError("schedule arm IDs differ from definitions")
    if int(report["counts"]["total_arms"]) != len(definitions):
        raise ValueError("schedule report arm count differs from definitions")
    if int(report["counts"]["total_schedule_draws"]) != len(schedules):
        raise ValueError("schedule report draw count differs from schedule")

    for definition in definitions:
        arm_id = str(definition["arm_id"])
        arm = schedules.loc[schedules["arm_id"].astype(str).eq(arm_id)].copy()
        arm = arm.sort_values("draw_number", kind="stable")
        total_draws = int(definition["total_draws"])
        batch_size = int(definition["batch_size"])
        number_batches = int(definition["number_batches"])
        if len(arm) != total_draws:
            raise ValueError(f"arm {arm_id!r} draw count differs from definition")
        if arm["draw_number"].astype(int).tolist() != list(range(total_draws)):
            raise ValueError(f"arm {arm_id!r} draw numbers are not contiguous")
        expected_batches = np.repeat(np.arange(number_batches), batch_size)
        expected_positions = np.tile(np.arange(batch_size), number_batches)
        if not np.array_equal(arm["batch_number"].to_numpy(), expected_batches):
            raise ValueError(f"arm {arm_id!r} batch numbers are invalid")
        if not np.array_equal(arm["batch_position"].to_numpy(), expected_positions):
            raise ValueError(f"arm {arm_id!r} batch positions are invalid")
        realized = arm["source_role"].value_counts().sort_index().to_dict()
        expected = {
            str(role): int(count)
            for role, count in definition["source_draws"].items()
        }
        if realized != dict(sorted(expected.items())):
            raise ValueError(f"arm {arm_id!r} source totals differ from definition")
        per_batch = (
            arm.groupby(["batch_number", "source_role"])
            .size()
            .unstack(fill_value=0)
        )
        expected_per_batch = {
            str(role): int(count)
            for role, count in definition["source_draws_per_batch"].items()
        }
        for role, count in expected_per_batch.items():
            if role not in per_batch or not per_batch[role].eq(count).all():
                raise ValueError(
                    f"arm {arm_id!r} source {role!r} is not balanced per batch"
                )
    return schedules, definitions, report


class _ExactScheduleBatchSampler(Sampler[list[tuple[int, int]]]):
    def __init__(
        self,
        arm_schedule: pd.DataFrame,
        sample_index: dict[str, int],
        *,
        batch_size: int,
        max_batches: int | None = None,
    ):
        ordered = arm_schedule.sort_values("draw_number", kind="stable")
        batches: list[list[tuple[int, int]]] = []
        for _, batch in ordered.groupby("batch_number", sort=True):
            batch = batch.sort_values("batch_position", kind="stable")
            if len(batch) != batch_size:
                raise ValueError("schedule batch differs from frozen batch size")
            rows = []
            for row in batch.itertuples(index=False):
                sample_id = str(row.sample_id)
                if sample_id not in sample_index:
                    raise ValueError(f"scheduled sample is absent from training: {sample_id}")
                rows.append(
                    (sample_index[sample_id], int(row.source_draw_number))
                )
            batches.append(rows)
        if max_batches is not None:
            batches = batches[: int(max_batches)]
        if not batches:
            raise ValueError("exact schedule contains no batches")
        self.batches = tuple(tuple(batch) for batch in batches)

    def __iter__(self) -> Iterator[list[tuple[int, int]]]:
        yield from self.batches

    def __len__(self) -> int:
        return len(self.batches)


def _evaluate_arm(
    *,
    trunk: torch.nn.Module,
    expert: ResidualExpert,
    loader: DataLoader,
    device: torch.device,
) -> tuple[np.ndarray, np.ndarray]:
    pooled_rows: list[np.ndarray] = []
    adapter_rows: list[np.ndarray] = []
    trunk.eval()
    expert.eval()
    with torch.no_grad():
        for masked, truth, mask in loader:
            masked = masked.to(device)
            truth = truth.to(device)
            mask = mask.to(device)
            hidden = trunk.encode(masked)
            pooled = trunk.decode(hidden)
            adapted = pooled + expert(hidden)
            pooled_rows.append(_masked_row_mse(pooled, truth, mask).cpu().numpy())
            adapter_rows.append(_masked_row_mse(adapted, truth, mask).cpu().numpy())
    return (
        np.concatenate(pooled_rows).astype(np.float64),
        np.concatenate(adapter_rows).astype(np.float64),
    )


def run_training(args: argparse.Namespace) -> dict[str, Any]:
    if int(args.seed) not in PRESPECIFIED_SEEDS:
        raise ValueError(f"seed must be one of {PRESPECIFIED_SEEDS}")
    trunk_seed = int(args.seed)
    optimization_seed_raw = getattr(args, "optimization_seed", None)
    optimization_seed = int(
        trunk_seed if optimization_seed_raw is None else optimization_seed_raw
    )
    mask_seed_raw = getattr(args, "mask_seed", None)
    mask_seed = int(
        optimization_seed if mask_seed_raw is None else mask_seed_raw
    )
    loader_seed_raw = getattr(args, "loader_seed", None)
    loader_seed = int(
        optimization_seed if loader_seed_raw is None else loader_seed_raw
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    seed_everything(optimization_seed, deterministic=True)
    device = _resolve_device(args.device)

    schedules_path = Path(args.training_schedules)
    definitions_path = Path(args.arm_definitions)
    report_path = Path(args.schedule_report)
    manifest_path = Path(args.manifest)
    schedules, definitions, schedule_report = _load_contract(
        schedules_path=schedules_path,
        definitions_path=definitions_path,
        report_path=report_path,
        manifest_path=manifest_path,
        expected_schedule_sha256=args.expected_schedule_sha256,
        expected_definitions_sha256=args.expected_definitions_sha256,
    )
    manifest = read_manifest(manifest_path)
    selection = select_manifest_rows(
        manifest,
        role="pooled",
        train_split=args.train_split,
        validation_split=args.validation_split,
        train_filter_column=args.train_filter_column,
    )
    train_ids = selection.train[args.sample_id_column].astype(str).tolist()
    validation_ids = selection.validation[args.sample_id_column].astype(str).tolist()
    expression, expression_info = load_expression_rows(
        args.expression_parquet,
        train_ids + validation_ids,
        sample_id_column=args.sample_id_column,
    )
    validate_expression_metadata(
        args.expression_parquet,
        expression_info.gene_columns,
        metadata_path=args.expression_metadata,
    )
    train_expression = expression[: len(train_ids)]
    validation_expression = expression[len(train_ids) :]
    trunk, checkpoint_config, checkpoint = load_frozen_trunk(
        args.pooled_checkpoint, device
    )
    if list(expression_info.gene_columns) != list(checkpoint_config["gene_list"]):
        raise ValueError("expression gene order differs from pooled checkpoint")
    if checkpoint_config["normalization"] != "log1p_tpm":
        raise ValueError("Stage 2 requires a log1p_tpm pooled checkpoint")
    if not np.isclose(float(checkpoint_config["mask_token"]), float(args.mask_token)):
        raise ValueError("mask token differs from pooled checkpoint")
    with np.load(args.axis_definitions, allow_pickle=False) as archive:
        score_indices = archive["score_gene_indices"].astype(np.int64)
        definition_gene_names = archive["gene_names"].astype(str).tolist()
    if definition_gene_names != list(expression_info.gene_columns):
        raise ValueError("axis definition gene order differs from expression")

    schedule_ids = set(schedules["sample_id"].astype(str))
    if not schedule_ids <= set(train_ids):
        raise ValueError("training schedule contains non-training sample IDs")
    train_index = {sample_id: index for index, sample_id in enumerate(train_ids)}
    training_dataset = DeterministicMaskedExpressionDataset(
        train_expression,
        train_ids,
        normalization="log1p_tpm",
        mask_ratio=float(args.mask_ratio),
        mask_token=float(args.mask_token),
        seed=mask_seed,
        phase="stage2_directed_transfer_source_paired",
        fixed_masks=False,
    )

    smoke_only = bool(args.smoke_only)
    selected_definitions = definitions
    if smoke_only:
        selected_definitions = definitions[: int(args.smoke_arms)]
    hidden_dim = int(trunk.gene_embedding.embedding_dim)
    initialization_key = str(schedule_report["initialization_key"])
    reference_expert = _initialize_expert(
        hidden_dim=hidden_dim,
        adapter_dim=int(args.adapter_dim),
        training_seed=optimization_seed,
        initialization_key=initialization_key,
    )
    initial_state_hash = _tensor_state_sha256(reference_expert.state_dict())
    del reference_expert
    arms_root = output_dir / "arms"
    arms_root.mkdir()
    run_metadata: dict[str, Any] = {
        "schema_version": 1,
        "status": "running",
        "research_stage": "stage2_directed_organ_transfer_development",
        "training_seed": trunk_seed,
        "trunk_seed": trunk_seed,
        "optimization_seed": optimization_seed,
        "mask_seed": mask_seed,
        "loader_seed": loader_seed,
        "code_commit": str(args.code_commit),
        "development_only": True,
        "external_data_accessed": False,
        "test_data_accessed": False,
        "best_seed_selection_allowed": False,
        "mechanical_only": smoke_only,
        "initialization_key": initialization_key,
        "initial_state_sha256": initial_state_hash,
        "counts": {
            "train": len(train_ids),
            "calibration": len(validation_ids),
            "genes": len(expression_info.gene_columns),
            "score_genes": len(score_indices),
            "scheduled_arms": len(definitions),
            "executed_arms": len(selected_definitions),
        },
        "hashes": {
            "manifest_sha256": sha256_file(manifest_path),
            "expression_sha256": sha256_file(args.expression_parquet),
            "expression_metadata_sha256": sha256_file(args.expression_metadata),
            "pooled_checkpoint_sha256": sha256_file(args.pooled_checkpoint),
            "axis_definitions_sha256": sha256_file(args.axis_definitions),
            "training_schedules_sha256": sha256_file(schedules_path),
            "arm_definitions_sha256": sha256_file(definitions_path),
            "schedule_report_sha256": sha256_file(report_path),
            "train_sample_ids_sha256": sha256_lines(train_ids),
            "calibration_sample_ids_sha256": sha256_lines(validation_ids),
            "gene_order_sha256": sha256_lines(expression_info.gene_columns),
        },
        "config": {
            "adapter_dim": int(args.adapter_dim),
            "mask_ratio": float(args.mask_ratio),
            "mask_token": float(args.mask_token),
            "learning_rate": float(args.learning_rate),
            "weight_decay": float(args.weight_decay),
            "batch_size": int(schedule_report["batch_size"]),
            "optimizer": "AdamW",
            "scheduler": "CosineAnnealingLR",
            "use_amp": bool(args.use_amp),
            "checkpoint_policy": "predetermined_final_update_per_arm",
            "mask_pairing": "sample_id plus source-local draw number",
            "seed_factorization": (
                "explicit trunk, optimization/initialization, mask, and loader seeds"
            ),
        },
        "arms": [],
    }
    run_metadata["hashes"]["resolved_config_sha256"] = sha256_json(
        run_metadata["config"]
    )
    _atomic_json(output_dir / "run_metadata.json", run_metadata)
    start_time = time.time()

    for arm_number, definition in enumerate(selected_definitions, start=1):
        arm_id = str(definition["arm_id"])
        arm_dir = arms_root / arm_id
        arm_dir.mkdir()
        arm_schedule = schedules.loc[schedules["arm_id"].astype(str).eq(arm_id)]
        batch_size = int(definition["batch_size"])
        sampler = _ExactScheduleBatchSampler(
            arm_schedule,
            train_index,
            batch_size=batch_size,
            max_batches=(int(args.smoke_batches) if smoke_only else None),
        )
        loader_generator = torch.Generator().manual_seed(
            stable_seed(loader_seed, "stage2_transfer_loader", arm_id) % (2**63 - 1)
        )
        train_loader = DataLoader(
            training_dataset,
            batch_sampler=sampler,
            num_workers=int(args.num_workers),
            worker_init_fn=seed_data_worker,
            generator=loader_generator,
        )
        expert = _initialize_expert(
            hidden_dim=hidden_dim,
            adapter_dim=int(args.adapter_dim),
            training_seed=optimization_seed,
            initialization_key=initialization_key,
        ).to(device)
        if _tensor_state_sha256(expert.state_dict()) != initial_state_hash:
            raise AssertionError(f"arm {arm_id!r} did not start from shared state")
        optimizer = AdamW(
            expert.parameters(),
            lr=float(args.learning_rate),
            weight_decay=float(args.weight_decay),
        )
        scheduler = CosineAnnealingLR(optimizer, T_max=max(1, len(sampler)))
        use_amp = bool(args.use_amp and device.type == "cuda")
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
        losses = []
        trunk.eval()
        expert.train()
        for update, batch in enumerate(train_loader, start=1):
            optimizer.zero_grad(set_to_none=True)
            masked, truth, mask = (value.to(device) for value in batch)
            autocast = torch.autocast(
                device_type="cuda", dtype=torch.float16, enabled=use_amp
            )
            with autocast:
                with torch.no_grad():
                    hidden = trunk.encode(masked)
                    pooled = trunk.decode(hidden)
                adapted = pooled + expert(hidden)
                loss = _masked_row_mse(adapted, truth, mask).mean()
            if not bool(torch.isfinite(loss).item()):
                raise FloatingPointError(
                    f"non-finite loss in arm {arm_id!r} update {update}"
                )
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            losses.append(float(loss.detach().cpu()))

        checkpoint_path = arm_dir / "final_adapter.pt"
        state = {name: value.detach().cpu() for name, value in expert.state_dict().items()}
        torch.save(
            {
                "schema_version": 1,
                "arm_id": arm_id,
                "training_seed": trunk_seed,
                "trunk_seed": trunk_seed,
                "optimization_seed": optimization_seed,
                "mask_seed": mask_seed,
                "loader_seed": loader_seed,
                "initialization_key": initialization_key,
                "initial_state_sha256": initial_state_hash,
                "final_state_sha256": _tensor_state_sha256(state),
                "adapter_state_dict": state,
                "completed_updates": len(sampler),
                "source_draws": definition["source_draws"],
            },
            checkpoint_path,
        )

        recipients = [str(value) for value in definition["evaluation_recipients"]]
        validation_mask = selection.validation[args.organ_column].astype(str).isin(
            recipients
        ).to_numpy()
        validation_frame = selection.validation.loc[validation_mask].reset_index(drop=True)
        validation_values = validation_expression[validation_mask]
        validation_dataset = FixedGeneMaskDataset(
            validation_values,
            validation_frame[args.sample_id_column].astype(str).tolist(),
            mask_indices=score_indices,
            mask_token=float(args.mask_token),
        )
        validation_loader = DataLoader(
            validation_dataset,
            batch_size=int(args.validation_batch_size),
            shuffle=False,
            num_workers=int(args.num_workers),
            worker_init_fn=seed_data_worker,
            generator=loader_generator,
        )
        pooled_mse, adapter_mse = _evaluate_arm(
            trunk=trunk,
            expert=expert,
            loader=validation_loader,
            device=device,
        )
        score_path = arm_dir / "calibration_scores.npz"
        np.savez_compressed(
            score_path,
            sample_ids=validation_frame[args.sample_id_column].astype(str).to_numpy(),
            donor_ids=validation_frame["donor_id"].astype(str).to_numpy(),
            groups=validation_frame[args.group_column].astype(str).to_numpy(),
            organs=validation_frame[args.organ_column].astype(str).to_numpy(),
            pooled_mse=pooled_mse,
            adapter_mse=adapter_mse,
        )
        relative = (pooled_mse - adapter_mse) / pooled_mse
        arm_metadata = {
            "schema_version": 1,
            "status": "complete",
            "arm_id": arm_id,
            "arm_number": arm_number,
            "training_seed": trunk_seed,
            "trunk_seed": trunk_seed,
            "optimization_seed": optimization_seed,
            "mask_seed": mask_seed,
            "loader_seed": loader_seed,
            "mechanical_only": smoke_only,
            "completed_updates": len(sampler),
            "completed_draws": len(sampler) * batch_size,
            "source_draws": definition["source_draws"],
            "source_draws_per_batch": definition["source_draws_per_batch"],
            "evaluation_recipients": recipients,
            "calibration_rows": len(validation_frame),
            "mean_sample_relative_mse_reduction": float(relative.mean()),
            "loss": {
                "first": losses[0],
                "last": losses[-1],
                "minimum": min(losses),
            },
            "hashes": {
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "score_cache_sha256": sha256_file(score_path),
                "initial_state_sha256": initial_state_hash,
                "final_state_sha256": _tensor_state_sha256(state),
            },
        }
        _atomic_json(arm_dir / "run_metadata.json", arm_metadata)
        run_metadata["arms"].append(arm_metadata)
        run_metadata["last_completed_arm"] = arm_id
        _atomic_json(output_dir / "run_metadata.json", run_metadata)
        del expert, optimizer, scheduler, scaler
        if device.type == "cuda":
            torch.cuda.empty_cache()

    run_metadata["status"] = "complete"
    run_metadata["elapsed_seconds"] = float(time.time() - start_time)
    run_metadata["completed_arms"] = len(run_metadata["arms"])
    _atomic_json(output_dir / "run_metadata.json", run_metadata)
    (output_dir / "COMPLETE").touch()
    return run_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expression-parquet", required=True)
    parser.add_argument("--expression-metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pooled-checkpoint", required=True)
    parser.add_argument("--axis-definitions", required=True)
    parser.add_argument("--training-schedules", required=True)
    parser.add_argument("--arm-definitions", required=True)
    parser.add_argument("--schedule-report", required=True)
    parser.add_argument("--expected-schedule-sha256", required=True)
    parser.add_argument("--expected-definitions-sha256", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--optimization-seed", type=int)
    parser.add_argument("--mask-seed", type=int)
    parser.add_argument("--loader-seed", type=int)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="calibration")
    parser.add_argument("--train-filter-column", default="balanced_train")
    parser.add_argument("--sample-id-column", default="sample_id")
    parser.add_argument("--organ-column", default="organ")
    parser.add_argument("--group-column", default="series_group_id")
    parser.add_argument("--adapter-dim", type=int, default=64)
    parser.add_argument("--mask-ratio", type=float, default=0.30)
    parser.add_argument("--mask-token", type=float, default=-10.0)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--validation-batch-size", type=int, default=8)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--use-amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--smoke-arms", type=int, default=2)
    parser.add_argument("--smoke-batches", type=int, default=2)
    return parser


def main() -> None:
    result = run_training(build_parser().parse_args())
    print(
        json.dumps(
            {
                "status": result["status"],
                "training_seed": result["training_seed"],
                "optimization_seed": result["optimization_seed"],
                "completed_arms": result["completed_arms"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
