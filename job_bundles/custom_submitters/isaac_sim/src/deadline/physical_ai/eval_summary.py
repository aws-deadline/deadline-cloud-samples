# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Eval result files: ``eval_summary.json`` and LeRobot's ``eval_info.json``, checked and
completed into one shape. No AWS calls and no imports from the rest of the package, so
both :mod:`.outputs` (one job) and :mod:`.evals` (a whole queue) can use it.

``eval_summary.json`` schema (every field optional except as noted):

=================  ==========================================================================
Field              Meaning
=================  ==========================================================================
``episodes``       Number of evaluated episodes (int). Needed with ``successes`` for a rate.
``successes``      Number of successful episodes (int).
``success_rate``   ``successes / episodes`` (0 to 1). Computed when missing.
``ci95``           ``[low, high]``: a 95% confidence interval for the rate (0 to 1). When
                   missing, the Wilson score interval from ``successes`` and ``episodes``.
``checkpoint``     Which checkpoint was evaluated (text, e.g. ``checkpoint-20000``).
``by_condition``   ``{condition: {"episodes": n, "successes": k}}``: results per test
                   condition (start pose set, lighting, object), each like the top level.
``metrics``        ``{name: number}``: any other numbers worth comparing (mean episode
                   length, final distance to goal).
=================  ==========================================================================

``eval_info.json`` written by ``lerobot eval`` is read too (see :func:`from_lerobot`), so
LeRobot evaluations need no extra file. When a job has both, ``eval_summary.json`` wins.

"""

from __future__ import annotations

import json
import math
import posixpath
from collections.abc import Callable
from typing import Any

EVAL_SUMMARY = "eval_summary.json"
#: What ``lerobot eval`` writes; read as an eval summary too (see :func:`from_lerobot`).
LEROBOT_EVAL_INFO = "eval_info.json"
EVAL_FILES = (EVAL_SUMMARY, LEROBOT_EVAL_INFO)
#: An eval file larger than this is skipped with a warning.
EVAL_SUMMARY_CAP = 10_000_000
#: z for a two-sided 95% interval.
_Z95 = 1.959963984540054


def wilson(successes: int, episodes: int) -> list | None:
    """The Wilson score 95% interval ``[low, high]`` for ``successes`` of ``episodes``."""
    if episodes <= 0 or not 0 <= successes <= episodes:
        return None
    p, n, z2 = successes / episodes, episodes, _Z95 * _Z95
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = _Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if float(value).is_integer() and value >= 0 else None


def _rate(data: dict) -> dict:
    episodes, successes = _int(data.get("episodes")), _int(data.get("successes"))
    out: dict = {}
    if episodes is not None:
        out["episodes"] = episodes
    if successes is not None:
        out["successes"] = successes
    rate = data.get("success_rate")
    if isinstance(rate, (int, float)) and not isinstance(rate, bool) and 0 <= rate <= 1:
        out["success_rate"] = float(rate)
    elif episodes and successes is not None and successes <= episodes:
        out["success_rate"] = successes / episodes
    ci = data.get("ci95")
    if (
        isinstance(ci, (list, tuple))
        and len(ci) == 2
        and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in ci)
        and 0 <= ci[0] <= ci[1] <= 1
    ):
        out["ci95"] = [float(ci[0]), float(ci[1])]
    elif episodes and successes is not None:
        interval = wilson(successes, episodes)
        if interval:
            out["ci95"] = interval
    return out


def summarize(data: Any) -> dict | None:
    """The fields of a parsed ``eval_summary.json`` this module understands, checked and
    completed (rate and interval computed when missing). ``None`` when it isn't an object."""
    if not isinstance(data, dict):
        return None
    out = _rate(data)
    if isinstance(data.get("checkpoint"), (str, int)):
        out["checkpoint"] = str(data["checkpoint"])
    conds = data.get("by_condition")
    if isinstance(conds, dict):
        out["by_condition"] = {
            str(k): _rate(v) for k, v in conds.items() if isinstance(v, dict) and _rate(v)
        }
    metrics = data.get("metrics")
    if isinstance(metrics, dict):
        out["metrics"] = {
            str(k): float(v)
            for k, v in metrics.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        }
    return out


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _lerobot_block(block: Any) -> dict:
    """One LeRobot results block (``aggregated``, ``overall`` or a ``per_group`` entry):
    ``n_episodes``, ``n_success``, ``pc_success`` and ``pc_success_ci95`` are percentages."""
    if not isinstance(block, dict):
        return {}
    out: dict = {}
    n, k = _int(block.get("n_episodes")), _int(block.get("n_success"))
    if n is not None:
        out["episodes"] = n
    if k is not None:
        out["successes"] = k
    pc = _number(block.get("pc_success"))
    if pc is not None and 0 <= pc <= 100:
        out["success_rate"] = pc / 100
        if k is None and n:
            out["successes"] = round(pc * n / 100)
    ci = block.get("pc_success_ci95")
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        lo, hi = _number(ci[0]), _number(ci[1])
        if lo is not None and hi is not None:
            out["ci95"] = [lo / 100, hi / 100]
    return out


def from_lerobot(data: Any) -> dict | None:
    """An ``eval_summary.json``-shaped dict from ``lerobot eval``'s ``eval_info.json``.
    Single-task runs write an ``aggregated`` block; multi-task runs write ``overall`` plus
    ``per_group`` (read as ``by_condition``). Older versions lack ``n_success``, so
    successes then come from ``per_episode`` (each with a boolean ``success``).
    ``avg_sum_reward`` and ``avg_max_reward`` become metrics."""
    if not isinstance(data, dict):
        return None
    agg = data.get("overall") if isinstance(data.get("overall"), dict) else data.get("aggregated")
    agg = agg if isinstance(agg, dict) else {}
    out = _lerobot_block(agg)
    eps = data.get("per_episode")
    if "successes" not in out and isinstance(eps, list) and eps:
        flags = [e.get("success") for e in eps if isinstance(e, dict)]
        if flags and all(isinstance(f, bool) for f in flags):
            out["episodes"], out["successes"] = len(flags), sum(flags)
    groups = data.get("per_group")
    if isinstance(groups, dict):
        by = {str(g): _lerobot_block(v) for g, v in groups.items()}
        by = {g: v for g, v in by.items() if v}
        if by:
            out["by_condition"] = by
    metrics = {k: _number(agg.get(k)) for k in ("avg_sum_reward", "avg_max_reward")}
    metrics = {k: v for k, v in metrics.items() if v is not None}
    if metrics:
        out["metrics"] = metrics
    return out or None


def read_summary(files: list, read_text: Callable[[Any], str]) -> tuple:
    """``(summary, path, warnings)`` for the first ``eval_summary.json`` among ``files``
    (job output files with ``path`` and ``size``), else the first LeRobot
    ``eval_info.json``; ``(None, "", warnings)`` when none is readable. ``read_text(f)``
    fetches one file's text."""
    warnings: list = []
    named = [f for f in files if posixpath.basename(f.path) == EVAL_SUMMARY]
    named += [f for f in files if posixpath.basename(f.path) == LEROBOT_EVAL_INFO]
    for f in named:
        if f.size > EVAL_SUMMARY_CAP:
            warnings.append(f"skipped {f.path}: {f.size} bytes is over {EVAL_SUMMARY_CAP}")
            continue
        try:
            data = json.loads(read_text(f))
            if posixpath.basename(f.path) == LEROBOT_EVAL_INFO:
                data = from_lerobot(data)
            summary = summarize(data)
        except ValueError:
            warnings.append(f"skipped {f.path}: not JSON")
            continue
        if summary:
            return summary, f.path, warnings
    return None, "", warnings
