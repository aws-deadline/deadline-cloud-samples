# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Find job bundles on this machine and prefill the submit dialog from Isaac Sim.

A job bundle is a folder with ``template.yaml`` / ``template.json`` (Open Job
Description). The submit dialog itself is the stock ``deadline bundle gui-submit``;
this module only decides which bundles to list and which parameter values to start
the dialog with:

* PATH parameters that take a USD file get the open stage's file;
* dataset and checkpoint parameters get the datasets / checkpoint downloaded through
  "Load job output" (several datasets are gathered into one folder of hard links,
  which bundles that take "a dataset or a folder of datasets" accept);
* a parameter for a previous job's id gets the job loaded through "Load job output".

Everything else comes from the bundle's own ``parameter_values.json`` and defaults
(read by the dialog).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

TEMPLATE_NAMES = ("template.yaml", "template.yml", "template.json")
USD_EXT = (".usd", ".usda", ".usdc", ".usdz")
#: Parameter names treated as "the previous job's id" (case-insensitive).
FROM_JOB_NAMES = (
    "fromjob",
    "fromjobid",
    "previousjob",
    "previousjobid",
    "sourcejobid",
    "inputjobid",
)


@dataclass
class Bundle:
    path: str
    name: str
    description: str = ""
    parameters: list = field(default_factory=list)  # template parameterDefinitions


def _load_template(folder: str):
    for n in TEMPLATE_NAMES:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                if n.endswith(".json"):
                    return json.load(fh)
                import yaml

                return yaml.safe_load(fh)
    return None


def discover(folders: list, max_depth: int = 2) -> list:
    """Bundles under each folder (the folder itself, or up to ``max_depth`` levels
    below it), sorted by name. Unreadable templates are skipped."""
    import yaml

    found, seen = [], set()
    for root in folders:
        root = os.path.expanduser(root or "")
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dp, dirs, _ in os.walk(root):
            if dp.rstrip(os.sep).count(os.sep) - base_depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            real = os.path.realpath(dp)
            if real in seen:
                continue
            try:
                t = _load_template(dp)
            except (
                OSError,
                ValueError,
                yaml.YAMLError,
            ):  # unreadable or not a template: not a bundle
                continue
            if not isinstance(t, dict) or "specificationVersion" not in t:
                continue
            seen.add(real)
            dirs[:] = []  # a bundle's subfolders are its own, not more bundles
            found.append(
                Bundle(
                    dp,
                    str(t.get("name") or os.path.basename(dp)),
                    str(t.get("description") or ""),
                    list(t.get("parameterDefinitions") or []),
                )
            )
    return sorted(found, key=lambda b: b.name.lower())


def _takes_usd(p: dict) -> bool:
    if p.get("type") != "PATH" or p.get("objectType", "FILE") != "FILE":
        return False
    ui = p.get("userInterface") or {}
    filters = ui.get("fileFilters") or []
    pats = [str(x).lower() for f in filters for x in (f.get("patterns") or [])]
    if any(pat.endswith(USD_EXT) or pat in ("*.usd*",) for pat in pats):
        return True
    # Without USD file filters, only a name that says USD or stage counts. "Scene" alone does
    # not: a SceneFile parameter may take a scene description in another format.
    name = str(p.get("name", "")).lower()
    return not pats and any(k in name for k in ("usd", "stage"))


def _is_input_dir(p: dict) -> bool:
    return (
        p.get("type") == "PATH"
        and p.get("objectType") == "DIRECTORY"
        and p.get("dataFlow", "IN") == "IN"
    )


def _wants(p: dict, word: str) -> bool:
    """Parameter name says it takes ``word`` itself (``Datasets``, ``train_Datasets``,
    ``PolicyCheckpoint``, ``CheckpointDir``), and is not a different thing that merely
    mentions it (``DatasetCacheDir``, ``CheckpointOutputRoot``, ``SimSettings``).

    The name after the last ``_``, lowercased, must be or end with the word or its plural,
    optionally followed by ``dir``, ``path`` or ``folder``."""
    last = str(p.get("name", "")).lower().split("_")[-1]
    return last.endswith(
        tuple(stem + tail for stem in (word, word + "s") for tail in ("", "dir", "path", "folder"))
    )


def wants_input(p: dict, word: str) -> bool:
    """An input folder parameter named for ``word`` ("dataset", "checkpoint")."""
    return _is_input_dir(p) and _wants(p, word)


def prefill(
    bundle: Bundle,
    *,
    stage_path: str = "",
    from_job_id: str = "",
    datasets: str = "",
    checkpoint: str = "",
    several_datasets: bool = False,
) -> dict:
    """Initial values for ``gui-submit -p``: ``{parameter name: value}``. ``datasets`` is
    one dataset or, with ``several_datasets``, a folder of datasets, which only goes to
    parameters named for several (``...Datasets``); ``checkpoint`` is a checkpoint folder."""
    out = {}
    for p in bundle.parameters:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        name = str(p["name"])
        if stage_path and _takes_usd(p) and p.get("dataFlow", "IN") in ("IN", "INOUT"):
            out[name] = stage_path
        elif (
            from_job_id
            and p.get("type") == "STRING"
            and name.lower().replace("_", "") in FROM_JOB_NAMES
        ):
            out[name] = from_job_id
        elif (
            datasets
            and _is_input_dir(p)
            and _wants(p, "dataset")
            and (not several_datasets or name.lower().endswith("datasets"))
        ):
            out[name] = datasets
        elif checkpoint and _is_input_dir(p) and _wants(p, "checkpoint"):
            out[name] = checkpoint
    return out


def _names(bundle: Bundle) -> set:
    return {str(p["name"]) for p in bundle.parameters if isinstance(p, dict) and p.get("name")}


def match_job(bundles: list, job_name: str, parameters: dict):
    """The bundle a finished job most likely came from, or ``None``: the service keeps no
    link from a job to its bundle. Ranked by: defines every parameter the job has, then
    template name equals the job's name, then most shared parameter names, then fewest
    extra ones. A bundle sharing no parameter name never matches."""
    want = set(parameters)
    best, best_key = None, None
    for b in bundles:
        have = _names(b)
        shared = len(want & have)
        if not shared:
            continue
        key = (want <= have, b.name == job_name, shared, -len(have - want))
        if best_key is None or key > best_key:
            best, best_key = b, key
    return best


def output_dirs(bundle: Bundle) -> list:
    """Output folder parameters (``dataFlow`` ``OUT`` or ``INOUT``) without a default: the
    user would otherwise pick a new, empty folder for every job."""
    return [
        str(p["name"])
        for p in bundle.parameters
        if isinstance(p, dict)
        and p.get("name")
        and p.get("type") == "PATH"
        and p.get("objectType") == "DIRECTORY"
        and p.get("dataFlow") in ("OUT", "INOUT")
        and not p.get("default")
    ]


def fresh_outputs(bundle: Bundle, root: str, stamp: str, create: bool) -> dict:
    """A new folder for each of :func:`output_dirs`: ``<root>/<bundle folder>/<stamp>``, or
    a subfolder per parameter when there are several. Never an existing folder: an
    ``INOUT`` folder's contents are uploaded with the job. ``create`` makes them (at
    submit); without it the paths are a preview."""
    names = output_dirs(bundle)
    if not names:
        return {}
    parent = os.path.join(root, os.path.basename(os.path.normpath(bundle.path)) or "job")
    base, n = os.path.join(parent, stamp), 1
    while os.path.exists(base):
        n += 1
        base = os.path.join(parent, f"{stamp}-{n}")
    out = {k: base if len(names) == 1 else os.path.join(base, k) for k in names}
    if create:
        for path in out.values():
            os.makedirs(path)
    return out


def resubmit_values(bundle: Bundle, parameters: dict) -> dict:
    """A finished job's parameter values that ``bundle`` defines (``gui-submit`` warns about
    the rest)."""
    have = _names(bundle)
    return {k: v for k, v in parameters.items() if k in have}


def gather_datasets(paths: list, folder: str) -> str:
    """One dataset: its own path. Several: ``folder`` holding each as a subfolder of hard
    links (a copy where hard links fail), so a "folder of datasets" input sees them all.
    Job attachments hash file contents, so the links upload nothing new. ``folder`` is
    never emptied first: pass a fresh one (an open submit dialog may still be uploading
    an earlier one)."""
    paths = [p for p in paths if p and os.path.isdir(p)]
    if len(paths) <= 1:
        return paths[0] if paths else ""
    import shutil

    used = set()
    for src in paths:
        parts = [x for x in os.path.normpath(src).split(os.sep) if x][-2:]
        name, n = "_".join(parts), 1
        while name in used:
            n += 1
            name = f"{'_'.join(parts)}_{n}"
        used.add(name)
        for dp, _, fs in os.walk(src):
            dst_dir = os.path.join(folder, name, os.path.relpath(dp, src))
            os.makedirs(dst_dir, exist_ok=True)
            for f in fs:
                s_, d_ = os.path.join(dp, f), os.path.join(dst_dir, f)
                try:
                    os.link(s_, d_)
                except OSError:
                    shutil.copy2(s_, d_)
    return folder
