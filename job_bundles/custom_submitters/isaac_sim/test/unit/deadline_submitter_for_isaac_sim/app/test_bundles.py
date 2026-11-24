# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import os

import pytest
import yaml

from deadline.isaac_sim_submitter.app import bundles as bd


def make(root, name, params):
    d = os.path.join(root, name)
    os.makedirs(os.path.join(d, "scripts"))
    with open(os.path.join(d, "template.yaml"), "w") as fh:
        yaml.safe_dump(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": name,
                "parameterDefinitions": params,
                "steps": [],
            },
            fh,
        )
    with open(
        os.path.join(d, "scripts", "template.yaml"), "w"
    ) as fh:  # inside a bundle: not another bundle
        fh.write("specificationVersion: jobtemplate-2023-09\nname: nested\n")
    return d


PARAMS = [
    {
        "name": "SceneFile",
        "type": "PATH",
        "objectType": "FILE",
        "dataFlow": "IN",
        "userInterface": {"fileFilters": [{"label": "USD", "patterns": ["*.usd", "*.usda"]}]},
    },
    {"name": "OutputDir", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "OUT"},
    {"name": "FromJobId", "type": "STRING"},
    {"name": "Steps", "type": "INT", "default": 3},
]


def test_discover_and_prefill(tmp_path):
    make(str(tmp_path), "robot_pipeline", PARAMS)
    make(str(tmp_path / "group"), "eval_only", [])
    found = bd.discover([str(tmp_path), str(tmp_path / "missing")])
    assert [b.name for b in found] == ["eval_only", "robot_pipeline"]
    b = found[1]
    assert bd.prefill(b, stage_path="/s/scene.usda", from_job_id="job-1") == {
        "SceneFile": "/s/scene.usda",
        "FromJobId": "job-1",
    }
    assert bd.prefill(b) == {}
    assert not hasattr(found[0], "source")


def test_name_heuristic_only_without_filters(tmp_path):
    b = bd.Bundle(
        "x",
        "x",
        parameters=[
            {"name": "StageFile", "type": "PATH"},
            {
                "name": "Images",
                "type": "PATH",
                "userInterface": {"fileFilters": [{"patterns": ["*.png"]}]},
            },
        ],
    )
    assert bd.prefill(b, stage_path="/a.usd") == {"StageFile": "/a.usd"}


TRAIN_EVAL = [
    {"name": "train_Datasets", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"},
    {"name": "evaluate_CheckpointDir", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"},
    {"name": "evaluate_SimSettingsFile", "type": "PATH", "objectType": "FILE", "dataFlow": "IN"},
    {"name": "report_Dataset", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"},
    {"name": "OutputDir", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "INOUT"},
]


def test_prefill_inputs_from_loaded_items():
    b = bd.Bundle("x", "x", parameters=TRAIN_EVAL)
    got = bd.prefill(b, datasets="/c/ds", checkpoint="/c/ckpt")
    assert got == {
        "train_Datasets": "/c/ds",
        "evaluate_CheckpointDir": "/c/ckpt",
        "report_Dataset": "/c/ds",
    }
    several = bd.prefill(b, datasets="/c/gathered", several_datasets=True)
    assert several == {"train_Datasets": "/c/gathered"}


def test_gather_datasets(tmp_path):
    a = tmp_path / "job" / "generate" / "dataset"
    r = tmp_path / "job" / "collect" / "datasets" / "reach"
    for d in (a, r):
        (d / "meta").mkdir(parents=True)
        (d / "meta" / "info.json").write_text("{}")
    assert bd.gather_datasets([str(a)], str(tmp_path / "g")) == str(a)
    out = bd.gather_datasets([str(a), str(r)], str(tmp_path / "g"))
    subs = sorted(os.listdir(out))
    assert subs == ["datasets_reach", "generate_dataset"]
    assert os.path.samefile(
        os.path.join(out, "generate_dataset", "meta", "info.json"), a / "meta" / "info.json"
    )


def test_gather_datasets_never_deletes_the_folder(tmp_path):
    """Each submit gathers into its own folder; gathering must not wipe one an open
    dialog is still uploading (or anything else already there)."""
    a, r = tmp_path / "a" / "dataset", tmp_path / "b" / "dataset"
    for d in (a, r):
        d.mkdir(parents=True)
        (d / "x.parquet").write_text("x")
    g = tmp_path / "g"
    g.mkdir()
    (g / "keep.txt").write_text("k")
    assert bd.gather_datasets([str(a), str(r)], str(g)) == str(g)
    assert (g / "keep.txt").exists() and len(os.listdir(g)) == 3


def test_scene_json_param_is_not_a_stage():
    b = bd.Bundle(
        "x",
        "x",
        parameters=[
            {
                "name": "label_SceneFile",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {"control": "CHOOSE_INPUT_FILE"},
            },
            {"name": "StageUsd", "type": "PATH", "objectType": "FILE", "dataFlow": "IN"},
        ],
    )
    assert bd.prefill(b, stage_path="/a.usda") == {"StageUsd": "/a.usda"}


WANTS = [
    ("Datasets", "dataset", True),
    ("Dataset", "dataset", True),
    ("TrainDatasets", "dataset", True),
    ("train_Datasets", "dataset", True),
    ("DatasetDir", "dataset", True),
    ("DatasetsDir", "dataset", True),
    ("evaluate_DatasetPath", "dataset", True),
    ("DatasetFolder", "dataset", True),
    ("PolicyCheckpoint", "checkpoint", True),
    ("CheckpointDir", "checkpoint", True),
    ("Checkpoint", "checkpoint", True),
    ("DatasetCacheDir", "dataset", False),
    ("dataset_cache", "dataset", False),
    ("DatasetCount", "dataset", False),
    ("CheckpointOutputRoot", "checkpoint", False),
    ("CheckpointSteps", "checkpoint", False),
    ("SimSettings", "dataset", False),
    ("ImagesDir", "dataset", False),
]


@pytest.mark.parametrize("name,word,wanted", WANTS, ids=[f"{n}-{w[0]}" for n, w, _ in WANTS])
def test_wants_matches_the_word_itself(name, word, wanted):
    """A name that merely contains the word is a different thing: a dataset cache folder
    must not be filled with a dataset."""
    assert bd._wants({"name": name}, word) is wanted


def _b(name, *params):
    return bd.Bundle(path=f"/b/{name}", name=name, parameters=[{"name": p} for p in params])


def test_match_job_prefers_a_bundle_defining_every_parameter():
    train = _b("train", "Steps", "Lr", "OutputDir")
    train_v2 = _b("train_v2", "Steps", "Lr", "OutputDir", "Augment")
    evalb = _b("eval", "Checkpoint", "OutputDir")
    job = {"Steps": "5", "Lr": "1", "OutputDir": "/o"}
    assert bd.match_job([train_v2, evalb, train], "my run", job) is train  # fewest extras
    job2 = dict(job, Augment="on")
    assert bd.match_job([train, train_v2], "my run", job2) is train_v2  # covers all
    named = _b("my run", "Steps", "Lr", "OutputDir", "Extra")
    assert bd.match_job([train, named], "my run", job) is named  # name beats extras
    assert bd.match_job([_b("other", "X")], "my run", job) is None


def test_resubmit_values_keep_only_defined_parameters():
    b = _b("train", "Steps", "OutputDir")
    assert bd.resubmit_values(b, {"Steps": "5", "Gone": "x", "OutputDir": "/o"}) == {
        "Steps": "5",
        "OutputDir": "/o",
    }


def _out(name, flow="OUT", **extra):
    return {"name": name, "type": "PATH", "objectType": "DIRECTORY", "dataFlow": flow, **extra}


def test_output_dirs_are_output_folders_without_a_default():
    b = bd.Bundle(
        "/b/train",
        "train",
        parameters=[
            _out("OutputDir", "INOUT"),
            _out("Logs"),
            _out("Kept", default="./output"),
            _out("Data", "IN"),
            {"name": "File", "type": "PATH", "objectType": "FILE", "dataFlow": "OUT"},
        ],
    )
    assert bd.output_dirs(b) == ["OutputDir", "Logs"]


def test_fresh_outputs_are_new_folders_under_the_bundle(tmp_path):
    one = bd.Bundle(str(tmp_path / "bundles" / "3-sdg"), "SDG", parameters=[_out("OutputDir")])
    preview = bd.fresh_outputs(one, str(tmp_path / "out"), "20261124-1500", create=False)
    assert preview == {"OutputDir": str(tmp_path / "out" / "3-sdg" / "20261124-1500")}
    assert not (tmp_path / "out").exists()  # a preview creates nothing
    made = bd.fresh_outputs(one, str(tmp_path / "out"), "20261124-1500", create=True)
    assert made == preview and os.path.isdir(made["OutputDir"])
    # The same second again: never an existing folder (an INOUT folder's files upload).
    again = bd.fresh_outputs(one, str(tmp_path / "out"), "20261124-1500", create=True)
    assert again["OutputDir"].endswith("20261124-1500-2") and os.listdir(again["OutputDir"]) == []
    two = bd.Bundle(str(tmp_path / "b2"), "two", parameters=[_out("A"), _out("B")])
    both = bd.fresh_outputs(two, str(tmp_path / "out"), "s", create=True)
    assert both == {k: str(tmp_path / "out" / "b2" / "s" / k) for k in ("A", "B")}
    assert bd.fresh_outputs(bd.Bundle("/b/x", "x"), str(tmp_path), "s", create=True) == {}
