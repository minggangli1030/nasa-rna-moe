from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]
for source_dir in (ROOT / "core", ROOT / "evaluation"):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from build_organ_k45_retraining_partitions import (  # noqa: E402
    K4_ORGANS,
    _assign_group_atomic_k4,
)
from evaluate_organ_k45_retraining import (  # noqa: E402
    SEEDS,
    _parse_seed_paths,
    _relative_penalty_interval,
    _routed_mse,
    decide,
)
from train_fixed_partition_banks import (  # noqa: E402
    PackedExpertBanks,
    _parse_axis_expert_keys,
    _parse_axis_int_overrides,
    _tensor_state_sha256,
    _validate_axes,
)
from train_fixed_partition_moe import evaluate_fixed_partition  # noqa: E402


class _TinyEvaluationModel(nn.Module):
    num_experts = 2

    def forward(self, masked: torch.Tensor):
        base = torch.ones_like(masked)
        experts = torch.stack(
            (torch.full_like(masked, 0.25), torch.full_like(masked, 2.0)), dim=1
        )
        logits = torch.zeros(
            len(masked), self.num_experts, dtype=masked.dtype, device=masked.device
        )
        return experts, logits, base


def _evaluation_loader() -> DataLoader:
    rows = 8
    genes = 3
    masked = torch.zeros((rows, genes), dtype=torch.float32)
    truth = torch.zeros((rows, genes), dtype=torch.float32)
    mask = torch.tensor([[0, 2]] * rows, dtype=torch.int64)
    return DataLoader(TensorDataset(masked, truth, mask), batch_size=4)


def _evaluation_kwargs(labels: np.ndarray) -> dict:
    return {
        "labels": labels,
        "groups": np.asarray([f"study-{index}" for index in range(len(labels))]),
        "organs": np.asarray(["brain", "liver"] * (len(labels) // 2)),
        "sample_weights": np.full(len(labels), 1.0 / len(labels)),
        "device": torch.device("cpu"),
        "crossfit_seed": 91,
        "crossfit_folds": 2,
    }


def test_fixed_partition_evaluation_uses_pooled_prediction_for_fallback_minus_one():
    labels = np.asarray([-1, 0, 1, -1, 0, 1, 0, 1], dtype=np.int64)
    metrics, arrays = evaluate_fixed_partition(
        _TinyEvaluationModel(),
        _evaluation_loader(),
        fallback_label=-1,
        **_evaluation_kwargs(labels),
    )

    np.testing.assert_allclose(arrays["pooled_mse"], 1.0)
    np.testing.assert_allclose(arrays["expert_mse"][:, 0], 0.0625)
    np.testing.assert_allclose(arrays["expert_mse"][:, 1], 4.0)
    np.testing.assert_allclose(
        arrays["true_partition_mse"],
        np.asarray([1.0, 0.0625, 4.0, 1.0, 0.0625, 4.0, 0.0625, 4.0]),
    )
    assert arrays["true_labels"].tolist() == labels.tolist()
    assert metrics["partition_utilization"] == pytest.approx([0.5, 0.5])


@pytest.mark.parametrize(
    ("labels", "fallback_label", "message"),
    [
        (np.asarray([-1, 0, 1, 0, 0, 1, 0, 1]), None, "unconfigured fallback"),
        (np.asarray([-2, 0, 1, 0, 0, 1, 0, 1]), -1, "below fallback"),
        (np.asarray([-1, 0, 1, 0, 0, 1, 0, 1]), -2, "only fallback label -1"),
    ],
)
def test_fixed_partition_evaluation_rejects_invalid_fallback_contract(
    labels, fallback_label, message
):
    with pytest.raises(ValueError, match=message):
        evaluate_fixed_partition(
            _TinyEvaluationModel(),
            _evaluation_loader(),
            fallback_label=fallback_label,
            **_evaluation_kwargs(labels),
        )


def test_blind_routing_maps_only_active_k4_organs_and_leaves_adipose_pooled():
    label_names = ["brain", "liver", "skeletal_muscle", "skin"]
    pooled = np.asarray([9.0, 8.0, 7.0, 6.0, 5.0])
    experts = np.arange(20, dtype=np.float64).reshape(5, 4)
    predicted = np.asarray(
        ["brain", "adipose", "skin", "liver", "skeletal_muscle"]
    )

    actual = _routed_mse(pooled, experts, predicted, label_names)

    np.testing.assert_array_equal(
        actual,
        np.asarray([experts[0, 0], pooled[1], experts[2, 3], experts[3, 1], experts[4, 2]]),
    )
    np.testing.assert_array_equal(pooled, [9.0, 8.0, 7.0, 6.0, 5.0])


def test_blind_routing_rejects_unknown_router_class_or_misaligned_experts():
    pooled = np.ones(3)
    experts = np.ones((3, 4))
    names = ["brain", "liver", "skeletal_muscle", "skin"]
    with pytest.raises(ValueError, match="unknown classes"):
        _routed_mse(pooled, experts, np.asarray(["brain", "heart", "skin"]), names)
    with pytest.raises(ValueError, match="same shape|do not align"):
        _routed_mse(pooled, experts[:, :3], np.asarray(["brain", "liver", "skin"]), names)


def test_axis_validation_accepts_only_minus_one_plus_contiguous_active_labels():
    frame = pd.DataFrame(
        {
            "k4": [-1, 0, 1, 2, 3, -1],
            "k5": [0, 1, 2, 3, 4, 0],
        }
    )
    result = _validate_axes(frame, ["k4", "k5"], allow_fallback_label=True)
    np.testing.assert_array_equal(result["k4"], frame["k4"].to_numpy())
    np.testing.assert_array_equal(result["k5"], frame["k5"].to_numpy())

    with pytest.raises(ValueError, match="not contiguous"):
        _validate_axes(frame, ["k4"], allow_fallback_label=False)
    with pytest.raises(ValueError, match="below fallback"):
        _validate_axes(pd.DataFrame({"bad": [-2, 0, 1]}), ["bad"], allow_fallback_label=True)
    with pytest.raises(ValueError, match="active labels are not contiguous"):
        _validate_axes(pd.DataFrame({"bad": [-1, 0, 2]}), ["bad"], allow_fallback_label=True)
    with pytest.raises(ValueError, match="lacks requested axis"):
        _validate_axes(frame, ["missing"], allow_fallback_label=True)


def test_axis_override_parsers_accept_frozen_budgets_and_semantic_keys():
    axes = ["organ_k5", "organ_k4_epe", "organ_k4_total_active"]
    budgets = _parse_axis_int_overrides(
        ["organ_k5=1500", "organ_k4_epe=1500", "organ_k4_total_active=1875"],
        axes,
        option_name="axis-update-budget",
    )
    assert budgets == {
        "organ_k5": 1500,
        "organ_k4_epe": 1500,
        "organ_k4_total_active": 1875,
    }

    keys = _parse_axis_expert_keys(
        [
            "organ_k5=adipose,brain,liver,skeletal_muscle,skin",
            "organ_k4_epe=brain,liver,skeletal_muscle,skin",
        ],
        {"organ_k5": 5, "organ_k4_epe": 4},
    )
    assert keys["organ_k4_epe"] == list(K4_ORGANS)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (["organ_k4=1500", "organ_k4=1875"], "repeats axis"),
        (["unknown=1500"], "unknown axis"),
        (["organ_k4=0"], "positive"),
        (["organ_k4=1.5"], "noninteger"),
        (["organ_k4"], "AXIS=INTEGER"),
    ],
)
def test_axis_integer_override_parser_fails_closed(raw, message):
    with pytest.raises(ValueError, match=message):
        _parse_axis_int_overrides(
            raw, ["organ_k4"], option_name="axis-update-budget"
        )


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (["organ_k4=brain,liver,skin"], "count/values"),
        (["organ_k4=brain,liver,skin,skin"], "count/values"),
        (["organ_k4=brain,liver,,skin"], "count/values"),
        (["unknown=brain,liver,skeletal_muscle,skin"], "unknown axis"),
        (
            [
                "organ_k4=brain,liver,skeletal_muscle,skin",
                "organ_k4=brain,liver,skeletal_muscle,skin",
            ],
            "repeats axis",
        ),
    ],
)
def test_semantic_expert_key_parser_fails_closed(raw, message):
    with pytest.raises(ValueError, match=message):
        _parse_axis_expert_keys(raw, {"organ_k4": 4})


class _TinyTrunk(nn.Module):
    def __init__(self):
        super().__init__()
        self.gene_embedding = nn.Embedding(5, 6)


def test_semantic_initialization_is_identical_for_shared_k4_k5_experts():
    keys = {
        "organ_k5": ["adipose", "brain", "liver", "skeletal_muscle", "skin"],
        "organ_k4": ["brain", "liver", "skeletal_muscle", "skin"],
    }
    model = PackedExpertBanks(
        _TinyTrunk(),
        {"organ_k5": 5, "organ_k4": 4},
        adapter_dim=3,
        seed=17,
        axis_expert_keys=keys,
    )
    repeated = PackedExpertBanks(
        _TinyTrunk(),
        {"organ_k5": 5, "organ_k4": 4},
        adapter_dim=3,
        seed=17,
        axis_expert_keys=keys,
    )

    for key in keys["organ_k4"]:
        k4_index = keys["organ_k4"].index(key)
        k5_index = keys["organ_k5"].index(key)
        k4_hash = _tensor_state_sha256(dict(model.banks["organ_k4"][k4_index].state_dict()))
        k5_hash = _tensor_state_sha256(dict(model.banks["organ_k5"][k5_index].state_dict()))
        repeated_hash = _tensor_state_sha256(
            dict(repeated.banks["organ_k4"][k4_index].state_dict())
        )
        assert k4_hash == k5_hash == repeated_hash

    adipose_hash = _tensor_state_sha256(dict(model.banks["organ_k5"][0].state_dict()))
    brain_hash = _tensor_state_sha256(dict(model.banks["organ_k5"][1].state_dict()))
    assert adipose_hash != brain_hash


def _partition_fixture() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    sample = 0
    for organ_index, organ in enumerate(("adipose", *K4_ORGANS)):
        group_count = 2 if organ == "adipose" else 3
        for group_index in range(group_count):
            group = f"{organ}-study-{group_index}"
            group_size = 1 + ((organ_index + group_index) % 3)
            for _ in range(group_size):
                rows.append(
                    {
                        "sample_id": f"sample-{sample}",
                        "organ": organ,
                        "series_group_id": group,
                    }
                )
                sample += 1
    return pd.DataFrame(rows)


def test_k4_random_assignment_is_deterministic_row_order_invariant_and_study_atomic():
    frame = _partition_fixture()
    labels, report = _assign_group_atomic_k4(frame, seed=17, split_name="train")
    repeated, repeated_report = _assign_group_atomic_k4(
        frame, seed=17, split_name="train"
    )
    shuffled = frame.sample(frac=1.0, random_state=123)
    shuffled_labels, _ = _assign_group_atomic_k4(
        shuffled, seed=17, split_name="train"
    )

    np.testing.assert_array_equal(labels, repeated)
    assert report == repeated_report
    by_sample = dict(zip(frame["sample_id"], labels))
    shuffled_by_sample = dict(zip(shuffled["sample_id"], shuffled_labels))
    assert shuffled_by_sample == by_sample

    labeled = frame.assign(label=labels)
    assert set(labeled.loc[labeled["organ"].eq("adipose"), "label"]) == {-1}
    assert set(labeled.loc[~labeled["organ"].eq("adipose"), "label"]) == set(range(4))
    assert labeled.groupby("series_group_id")["label"].nunique().max() == 1
    assert sum(report["active_counts"]) == int((labels >= 0).sum())
    assert report["fallback_count"] == int((labels < 0).sum())
    assert report["active_connected_studies"] == 12


def test_k4_random_assignment_rejects_missing_organs_and_mixed_role_studies():
    frame = _partition_fixture()
    without_skin = frame.loc[~frame["organ"].eq("skin")].copy()
    with pytest.raises(ValueError, match="lacks one or more active K4 organs"):
        _assign_group_atomic_k4(without_skin, seed=17, split_name="train")

    mixed = frame.copy()
    adipose_row = mixed.index[mixed["organ"].eq("adipose")][0]
    brain_group = mixed.loc[mixed["organ"].eq("brain"), "series_group_id"].iloc[0]
    mixed.loc[adipose_row, "series_group_id"] = brain_group
    with pytest.raises(ValueError, match="mix organ/fallback roles"):
        _assign_group_atomic_k4(mixed, seed=17, split_name="train")


def _noninferiority_inputs(penalty: float = 0.005):
    organs = np.repeat(
        np.asarray(["adipose", "brain", "liver", "skeletal_muscle", "skin"]), 2
    )
    groups = np.asarray([f"{organ}-study-{index % 2}" for index, organ in enumerate(organs)])
    k5 = {seed: np.ones(len(groups), dtype=np.float64) for seed in SEEDS}
    k4 = {
        seed: np.full(len(groups), 1.0 + penalty, dtype=np.float64) for seed in SEEDS
    }
    return k4, k5, groups, organs


@pytest.mark.parametrize("penalty", [-0.005, 0.005, 0.02])
def test_noninferiority_interval_is_paired_deterministic_and_on_relative_mse_scale(
    penalty
):
    k4, k5, groups, organs = _noninferiority_inputs(penalty)
    result = _relative_penalty_interval(
        k4, k5, groups, organs, seed=31337, reps=100
    )
    repeated = _relative_penalty_interval(
        k4, k5, groups, organs, seed=31337, reps=100
    )
    assert result == repeated
    assert result["relative_mse_penalty"] == pytest.approx(penalty)
    assert result["relative_mse_penalty_per_seed"] == pytest.approx([penalty] * 3)
    assert result["paired_clustered_interval_95"] == pytest.approx([penalty, penalty])
    assert result["simultaneous_one_sided_upper_97_5"] == pytest.approx(penalty)


def test_noninferiority_interval_rejects_misalignment_and_groups_spanning_organs():
    k4, k5, groups, organs = _noninferiority_inputs()
    bad_shape = dict(k4)
    bad_shape[101] = bad_shape[101][:-1]
    with pytest.raises(ValueError, match="same shape|do not align"):
        _relative_penalty_interval(
            bad_shape, k5, groups, organs, seed=4, reps=10
        )

    mixed_groups = groups.copy()
    mixed_groups[2] = mixed_groups[0]
    with pytest.raises(ValueError, match="spans organs"):
        _relative_penalty_interval(
            k4, k5, mixed_groups, organs, seed=4, reps=10
        )


@pytest.mark.parametrize(
    ("support", "noninferiority", "branch", "selected"),
    [
        (
            {"k5": True, "k4_epe": True, "k4_total_active": True},
            {"k4_epe": True, "k4_total_active": True},
            "k4_robust",
            "k4_epe",
        ),
        (
            {"k5": True, "k4_epe": False, "k4_total_active": True},
            {"k4_epe": False, "k4_total_active": True},
            "k4_budget_dependent",
            "k4_total_active",
        ),
        (
            {"k5": True, "k4_epe": True, "k4_total_active": False},
            {"k4_epe": True, "k4_total_active": False},
            "k5_retained",
            "k5",
        ),
        (
            {"k5": False, "k4_epe": True, "k4_total_active": False},
            {"k4_epe": True, "k4_total_active": False},
            "k4_efficient",
            "k4_epe",
        ),
        (
            {"k5": False, "k4_epe": False, "k4_total_active": True},
            {"k4_epe": False, "k4_total_active": False},
            "inconclusive",
            None,
        ),
        (
            {"k5": False, "k4_epe": False, "k4_total_active": False},
            {"k4_epe": False, "k4_total_active": False},
            "no_supported_split",
            None,
        ),
    ],
)
def test_frozen_decision_tree_covers_k4_k5_outcomes(
    support, noninferiority, branch, selected
):
    result = decide(support, noninferiority)
    assert result["decision_branch"] == branch
    assert result["selected_candidate_for_future_freeze"] == selected
    assert result["development_only"] is True
    assert result["test_accessed"] is False
    assert result["automatic_external_test_authorization"] is False


def test_decision_and_seed_path_parsers_require_the_exact_frozen_families(tmp_path):
    with pytest.raises(ValueError, match="cover frozen arms"):
        decide(
            {"k5": True, "k4_epe": True},
            {"k4_epe": True, "k4_total_active": True},
        )

    parsed = _parse_seed_paths(
        [f"17={tmp_path / 's17'}", f"42={tmp_path / 's42'}", f"101={tmp_path / 's101'}"]
    )
    assert tuple(sorted(parsed)) == SEEDS
    with pytest.raises(ValueError, match="exactly"):
        _parse_seed_paths([f"17={tmp_path / 's17'}", f"42={tmp_path / 's42'}"])
    with pytest.raises(ValueError, match="duplicate"):
        _parse_seed_paths(
            [
                f"17={tmp_path / 'first'}",
                f"17={tmp_path / 'second'}",
                f"42={tmp_path / 's42'}",
                f"101={tmp_path / 's101'}",
            ]
        )
    with pytest.raises(ValueError, match="SEED=PATH"):
        _parse_seed_paths(["17", f"42={tmp_path / 's42'}", f"101={tmp_path / 's101'}"])
