# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Detection of loadable outputs from a job's file list. No AWS."""

from __future__ import annotations

from deadline.physical_ai.job_outputs import OutputFile
from deadline.physical_ai.outputs import KINDS, detect


def f(path: str, size: int = 10) -> OutputFile:
    return OutputFile(path=path, hash="h" + path, size=size)


FILES = [
    f("evaluate/eval_summary.json"),
    f("evaluate/rollouts/ep_003.trajectory.npz"),
    f("evaluate/rollouts/ep_004.TRAJECTORY.npz"),
    f("evaluate/rollouts/ep_004_stats.npz"),  # any .npz is offered; checked when loaded
    f("evaluate/videos/ep_003.mp4"),
    f("generate/dataset/meta/info.json"),
    f("generate/dataset/data/chunk-000/file-000.parquet"),
    f("generate/dataset/videos/front.mp4"),  # part of the dataset, not its own item
    f("generate/dataset/plans/a.trajectory.npz"),  # beside the dataset folders: its own item
    f("label/dataset/meta/info.json"),  # no parquet: not a dataset
    f("scenes/table.usda"),
    f("scenes/table.USDZ"),
    f("train/checkpoint/checkpoint.json"),
    f("train/checkpoint/model.safetensors", 1000),
    f("train/checkpoint/eval_summary.json"),  # inside a checkpoint: loads with it
    f("record/episodes.hdf5"),
    f("logs/run.log"),
]


def by_path(items: list) -> dict:
    return {i["path"]: i for i in items}


def test_kinds_and_order() -> None:
    items = detect(FILES)
    assert [(i["kind"], i["path"]) for i in items] == [
        ("eval_summary", "evaluate/eval_summary.json"),
        ("trajectory", "evaluate/rollouts/ep_003.trajectory.npz"),
        ("trajectory", "evaluate/rollouts/ep_004.TRAJECTORY.npz"),
        ("trajectory", "evaluate/rollouts/ep_004_stats.npz"),
        ("trajectory", "generate/dataset/plans/a.trajectory.npz"),
        ("usd", "scenes/table.USDZ"),
        ("usd", "scenes/table.usda"),
        ("lerobot", "generate/dataset"),
        ("checkpoint", "train/checkpoint"),
        ("hdf5", "record/episodes.hdf5"),
        ("video", "evaluate/videos/ep_003.mp4"),
    ]
    p = by_path(items)
    assert p["generate/dataset"]["file_count"] == 3 and p["generate/dataset"]["loader"] == "input"
    assert p["train/checkpoint"]["file_count"] == 3 and p["train/checkpoint"]["size"] == 1020
    assert (
        p["scenes/table.usda"]["loader"] == "open" and p["scenes/table.usda"]["group"] == "scenes"
    )
    assert {i["loader"] for i in items} <= set(KINDS.values())


def test_root_lerobot_dataset_is_detected() -> None:
    """OutputDir itself is the dataset (meta/info.json at the root)."""
    files = [
        f("meta/info.json"),
        f("data/chunk-000/file-000.parquet"),
        f("videos/a.mp4"),
        f("x.log"),
    ]
    assert [(i["kind"], i["path"], i["file_count"]) for i in detect(files)] == [("lerobot", "", 3)]


def test_root_checkpoint_is_detected_with_empty_path() -> None:
    items = detect([f("checkpoint.json"), f("model.safetensors")])
    assert [(i["kind"], i["path"], i["file_count"]) for i in items] == [("checkpoint", "", 2)]


def test_root_checkpoint_hides_nothing_else() -> None:
    """A checkpoint at the OutputDir root has root path "", which is every path: the job's
    other outputs must still be listed."""
    items = detect(
        [f("checkpoint.json"), f("eval_summary.json"), f("rollout.mp4"), f("policy.usd")]
    )
    assert [(i["kind"], i["path"]) for i in items] == [
        ("eval_summary", "eval_summary.json"),
        ("usd", "policy.usd"),
        ("checkpoint", ""),
        ("video", "rollout.mp4"),
    ]


def test_nothing_loadable() -> None:
    assert detect([f("logs/a.txt"), f("x.txt")]) == []
