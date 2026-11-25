# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""examples/quest3_hand_ingest: sample sessions through import and dataset, checked against the
sample generator's known geometry, plus OpenJD validation of the template."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

BUNDLE = Path(__file__).resolve().parents[3] / "examples" / "quest3_hand_ingest"
sys.path.insert(0, str(BUNDLE / "scripts"))

import build_dataset
import import_session
import make_sample_sessions
import quest_capture as qc

#: Where the sample sessions pinch the cube, in the task frame (make_sample_sessions.CUBE_C).
CUBE = np.array([0.05, 0.10, 0.023])


@pytest.fixture(scope="module")
def imported(tmp_path_factory: Any) -> tuple:
    root = tmp_path_factory.mktemp("quest3")
    sessions, out = root / "sessions", root / "out"
    assert make_sample_sessions.main(["--out", str(sessions)]) == 0
    reports = [
        import_session.import_session(str(sessions), i, str(out), 30.0, 0.1) for i in range(1, 5)
    ]
    return sessions, out, reports


def _pinch_mid(out: Path, name: str, t: float) -> np.ndarray:
    with np.load(out / "sessions" / name / "poses.npz") as z:
        k = int(np.argmin(np.abs(z["t"] - t)))
        j = z["right"][k]
        return (j[qc.THUMB_TIP, :3] + j[qc.INDEX_TIP, :3]) / 2


def test_import_puts_the_pinch_on_the_cube_in_both_calibrations(imported: tuple) -> None:
    _sessions, out, reports = imported
    by = {r["session"]: r for r in reports}
    assert by["anchored"]["world"]["method"] == "touch_points"
    assert by["webxr"]["world"]["method"] == "T_xr_world"
    for name in ("anchored", "webxr"):
        assert np.allclose(_pinch_mid(out, name, 2.3), CUBE, atol=2e-3), name
    assert by["unanchored"]["flags"] == ["world_frame_unanchored"]


def test_import_bridges_short_gaps_and_marks_long_ones(imported: tuple) -> None:
    _sessions, out, reports = imported
    by = {r["session"]: r for r in reports}
    assert by["anchored"]["hands"]["right"]["tracked_fraction"] == 1.0  # 50 ms dropout bridged
    lost = by["lost"]["hands"]["right"]
    assert 0.4 < lost["tracked_fraction"] < 0.5 and lost["longest_gap_s"] > 3
    with np.load(out / "sessions" / "lost" / "poses.npz") as z:
        gap = (z["t"] > 2) & (z["t"] < 4)
        assert not z["right_ok"][gap].any() and np.isnan(z["right"][gap]).all()


def test_dataset_follows_lerobot_v3(imported: tuple) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    pytest.importorskip("pandas")
    sessions, out, _reports = imported
    assert (
        build_dataset.main(
            ["--sessions-dir", str(sessions), "--num-sessions", "4", "--output-dir", str(out)]
        )
        == 0
    )
    root = out / "dataset"
    info = json.loads((root / "meta" / "info.json").read_text())
    assert info["codebase_version"] == "v3.0" and info["total_episodes"] == 4
    assert info["total_frames"] == 720 and info["splits"] == {"train": "0:4"}
    data = pq.read_table(root / "data" / "chunk-000" / "file-000.parquet")
    assert set(data.column_names) == set(info["features"])
    assert data.num_rows == info["total_frames"]
    assert data.schema.field("observation.hand.right.joints").type.list_size == 75
    eps = pq.read_table(root / "meta" / "episodes" / "chunk-000" / "file-000.parquet").to_pylist()
    assert [e["dataset_from_index"] for e in eps] == [0, 180, 360, 540]
    assert eps[1]["session"] == "lost" and eps[0]["tasks"] == ["place the cube on the target"]
    rows = data.to_pandas()
    lost = rows[rows.episode_index == 1]
    untracked = lost[~lost["observation.hand.right.valid"]]
    assert len(untracked) and not np.stack(untracked["observation.hand.right.joints"]).any()
    stats = json.loads((root / "meta" / "stats.json").read_text())
    assert len(stats["observation.hand.right.joints"]["mean"]) == 75
    qc_rows = json.loads((out / "qc_report" / "qc.json").read_text())
    warnings = {r["session"]: r["warnings"] for r in qc_rows}
    assert warnings["anchored"] == [] and warnings["webxr"] == []
    assert warnings["lost"] == ["right_hand_tracked_46%"]
    assert "lost" in (out / "qc_report" / "index.html").read_text()


def test_bad_sessions_are_refused_with_the_line(tmp_path: Path) -> None:
    d = tmp_path / "s1"
    d.mkdir()
    (d / "session.jsonl").write_text(
        '{"type": "header", "format": "quest-capture", "version": 1}\n'
        '{"type": "frame", "t": 0, "hands": {"right": [[0, 0, 0, 0, 0, 0, 1]]}}\n'
    )
    with pytest.raises(qc.InputError, match=r"session.jsonl:2: the right hand needs 26 joints"):
        qc.read_session(str(d / "session.jsonl"))
    (tmp_path / "sessions.txt").write_text("s1\nmissing\n")
    with pytest.raises(qc.InputError, match="missing"):
        qc.list_sessions(str(tmp_path))


def test_template_is_valid_openjd() -> None:
    model = pytest.importorskip("openjd.model")
    import yaml

    with open(BUNDLE / "template.yaml", encoding="utf-8") as fh:
        template = model.decode_job_template(template=yaml.safe_load(fh))
    assert [s.name for s in template.steps] == ["Import Sessions", "Build Dataset"]
    scripts = {p.name for p in (BUNDLE / "scripts").iterdir()}
    for step in template.steps:
        args = [str(a) for a in step.script.actions.onRun.args or []]
        assert args[2] in scripts and os.path.basename(args[0]) == "run.sh"
