#!/usr/bin/env python3
"""Scene construction for the Replicator SDG sample.

Two sources:

``primitives`` (default)
    Built entirely from ``rep.create.*`` primitives and lights. It references no
    NVIDIA-authored asset of any kind, which matters because this is a public
    sample: the Omniverse Kit SDK and NVIDIA's Omniverse content are governed by
    the Isaac Sim Additional Software and Materials License, and NVIDIA's own
    ``scene_based_sdg.py`` example cannot be copied here because it is built on
    ``get_assets_root_path()`` warehouse assets.

``workshop``
    Opt-in. Loads the Apache-2.0 local USD files that ship inside the
    Sim-to-Real-SO-101-Workshop image. NOTE it deliberately skips
    ``lightbox-simple.usd``, which carries a ``payload`` to NVIDIA's
    ``rsd455.usd`` RealSense camera geometry on S3. Even so, the remaining files
    bind materials fetched from NVIDIA's ``omniverse-content-production``
    bucket (the vial's ``Plastic_Thick_Translucent.mdl`` and the robot's
    ``Aluminum_Anodized_Black.mdl``), so this path rebinds materials to
    randomized OmniPBR -- which doubles as the domain-randomization demo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

WORKSHOP_USD_DIR = Path(
    "/workspace/Sim-to-Real-SO-101-Workshop/source/sim_to_real_so101/assets/usd"
)
# Explicitly NOT lightbox-simple.usd: it payloads NVIDIA's rsd455.usd.
WORKSHOP_SAFE_USD = ("SO-ARM101-USD-NO-CAMERA.usd", "Vial_rack_simple.usda")

SEMANTIC_CLASSES = ("cube", "sphere", "cylinder", "cone", "torus")


def _randomized_lighting(rep):
    """A dome plus a jittered distant light, re-rolled on each `randomize` event."""
    # DO NOT randomize a Dome light's `intensity`. That attribute is typed `int`
    # in this USD schema and Replicator hands the OmniGraph writer node a
    # TfPyObjWrapper regardless of whether the distribution is built from ints or
    # floats, so every frame throws:
    #   Type mismatch for </Replicator/DomeLight_Xform/DomeLight.intensity>:
    #   expected 'int', got 'TfPyObjWrapper'
    # Capture keeps going and it only surfaces as repeated [Error] lines in the
    # Kit log. Intensity is therefore fixed on the dome; brightness variation
    # comes from the Distant light, whose intensity is a float attribute.
    with rep.trigger.on_custom_event(event_name="randomize"):
        dome = rep.create.light(
            light_type="Dome",
            intensity=750,
            color=rep.distribution.uniform((0.6, 0.6, 0.6), (1.0, 1.0, 1.0)),
        )
        with dome:
            rep.modify.pose(rotation=rep.distribution.uniform((0, -180, 0), (0, 180, 0)))

        distant = rep.create.light(
            light_type="Distant",
            intensity=rep.distribution.uniform(500.0, 3000.0),
            color=rep.distribution.uniform((0.8, 0.8, 0.8), (1.0, 1.0, 1.0)),
        )
        with distant:
            rep.modify.pose(rotation=rep.distribution.uniform((-70, -180, 0), (-20, 180, 0)))


def _primitives_scene(rep, object_count: int):
    # A matte backdrop so segmentation has an unambiguous background class.
    rep.create.plane(scale=(12, 12, 1), position=(0, 0, 0), semantics=[("class", "floor")])

    shapes = []
    for i in range(object_count):
        kind = SEMANTIC_CLASSES[i % len(SEMANTIC_CLASSES)]
        factory = {
            "cube": rep.create.cube,
            "sphere": rep.create.sphere,
            "cylinder": rep.create.cylinder,
            "cone": rep.create.cone,
            "torus": rep.create.torus,
        }[kind]
        shapes.append(factory(semantics=[("class", kind)], scale=0.5))

    # Pose and colour are re-rolled per frame; this is the actual domain
    # randomization the sample is teaching.
    with rep.trigger.on_custom_event(event_name="randomize"):
        for shape in shapes:
            with shape:
                rep.modify.pose(
                    position=rep.distribution.uniform((-2.5, -2.5, 0.2), (2.5, 2.5, 2.0)),
                    rotation=rep.distribution.uniform((0, 0, 0), (360, 360, 360)),
                    scale=rep.distribution.uniform(0.3, 0.9),
                )
                rep.randomizer.color(
                    colors=rep.distribution.uniform((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
                )
    return shapes


def _workshop_scene(rep, object_count: int):
    missing = [n for n in WORKSHOP_SAFE_USD if not (WORKSHOP_USD_DIR / n).is_file()]
    if missing:
        raise SystemExit(
            "scene-source=workshop needs the workshop USD files in the image, "
            f"missing: {missing} under {WORKSHOP_USD_DIR}. "
            "Use --scene-source primitives, or build the image from "
            "containers/isaacsim-so101-workshop/."
        )

    props = []
    for name in WORKSHOP_SAFE_USD:
        cls = "robot" if name.startswith("SO-ARM") else "rack"
        props.append(rep.create.from_usd(
            str(WORKSHOP_USD_DIR / name), semantics=[("class", cls)]
        ))

    with rep.trigger.on_custom_event(event_name="randomize"):
        for prop in props:
            with prop:
                rep.modify.pose(
                    position=rep.distribution.uniform((-0.3, -0.3, 0.0), (0.3, 0.3, 0.1)),
                    rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
                )
                # Rebind to a randomized OmniPBR so the published pixels are not
                # shaded by NVIDIA's vMaterials MDLs. See the module docstring.
                rep.randomizer.color(
                    colors=rep.distribution.uniform((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
                )
    return props


def _assert_references_resolve(scene_usd: Path) -> None:
    """Refuse to render a stage whose references do not resolve.

    This guard is the whole reason the ``usd`` source is safe to automate. USD
    opens a stage with dangling references without error: the referencing prims
    exist locally, so a prim count still passes, the renderer still runs, and
    the job writes a dataset of empty frames and reports SUCCEEDED. Job
    attachments makes that easy to hit, because it only uploads what the
    submitter declared and relocates everything it does upload -- so a layer the
    closure missed, or a reference authored relative to the wrong directory,
    dangles on the worker while resolving fine on the workstation.

    ``ComputeAllDependencies`` returns the unresolved paths separately, which is
    exactly the signal needed. Fail here, where the message names the missing
    file, rather than after N shards of rendering nothing.
    """
    try:
        from pxr import UsdUtils
    except ImportError:  # pragma: no cover - pxr is always present inside Kit
        print("[sdg] WARNING: pxr unavailable, skipping reference check")
        return

    _layers, _assets, unresolved = UsdUtils.ComputeAllDependencies(str(scene_usd))
    if unresolved:
        raise SystemExit(
            f"scene-usd={scene_usd} has {len(unresolved)} unresolved "
            f"reference(s):\n  " + "\n  ".join(str(u) for u in unresolved) + "\n"
            "The stage would open and render empty frames. Include every "
            "dependency in asset_references.yaml, or point the missing layers at "
            "the image's ISAACSIM_ASSET_ROOT. Note that omniverse:// paths never "
            "resolve on a worker -- there is no Nucleus."
        )


def stage_sha256(scene_usd: Path) -> str:
    """SHA-256 of the stage file's bytes.

    Shared with the submitter: whatever produces ``SceneUsdSha256`` must use this
    same definition, which is why it is a module-level public function rather
    than inlined into the check below.
    """
    digest = hashlib.sha256()
    with open(scene_usd, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_stage_hash(scene_usd: Path, expected: str) -> None:
    """Prove the worker is rendering the stage the submitter meant to send.

    Job attachments already guarantees the bytes survive the round trip -- its
    content-addressed store would not resolve a corrupted file. What this adds is
    *provenance*, and it exists because of how a submitter has to capture an open
    stage.

    The file on disk is not what the user is looking at. Unsaved edits sit in a
    dirty root layer, and Kit routes a great deal of interaction into the session
    layer, which is never saved with the stage at all. So a submitter must export
    a flattened snapshot of the composed stage rather than sending the path of the
    file the user opened. ``Usd.Stage.Flatten`` captures both (verified: an
    unsaved size edit and a session-layer-only transform both survive the
    flatten). This check is what makes that export verifiable instead of merely
    intended -- the submitter records the hash of what it exported, and the worker
    refuses anything else.

    SCOPE, stated precisely: this covers the stage description only. It does not
    hash the external closure -- textures, MDL, referenced layers -- because those
    legitimately resolve to different paths on a worker than on a workstation, and
    assets under ISAACSIM_ASSET_ROOT are *meant* to resolve locally rather than
    travel with the job. Absent dependencies are caught by
    :func:`_assert_references_resolve` instead.

    Optional by design: an empty expected value skips the check, so hand-built
    submissions and the primitives and workshop sources are unaffected.
    """
    if not expected:
        return

    expected = expected.strip().lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise SystemExit(
            f"scene-usd-sha256 is not a SHA-256 hex digest: {expected!r}. "
            "Expected 64 hex characters, or an empty value to skip the check."
        )

    actual = stage_sha256(scene_usd)
    if actual != expected:
        raise SystemExit(
            f"scene-usd hash mismatch for {scene_usd.name}.\n"
            f"  expected {expected}\n"
            f"  actual   {actual}\n"
            "The worker is not rendering the stage the submitter exported. Most "
            "likely the stage was edited or re-exported after the hash was taken, "
            "so resubmit from the current scene. Refusing rather than rendering a "
            "dataset that misrepresents its own provenance."
        )
    print(f"[sdg] stage hash verified: {actual[:16]}...")


def _has_semantics(scene_usd: Path) -> bool:
    """True when the stage already labels geometry for Replicator's annotators."""
    try:
        from pxr import Usd
    except ImportError:  # pragma: no cover
        return False

    stage = Usd.Stage.Open(str(scene_usd))
    if stage is None:
        raise SystemExit(f"scene-usd={scene_usd} will not open as a USD stage")
    for prim in stage.Traverse():
        # Both the modern UsdSemantics labels and the older Semantics schema
        # satisfy the annotators; checking applied schema names covers both
        # without importing a schema module that may not exist in every build.
        if any("semantic" in s.lower() for s in prim.GetAppliedSchemas()):
            return True
    return False


def _usd_scene(rep, scene_usd: str, semantic_class: str, expected_sha256: str = ""):
    """Reference a submitted stage into the Replicator scene.

    Referenced rather than opened. Opening it as *the* stage would mean
    authoring this sample's camera, lights and randomization graph into someone
    else's stage and inheriting whatever it already defines; referencing keeps
    the two separate and keeps the camera orbit and lighting randomization in
    ``build_scene`` applying unchanged.
    """
    if not scene_usd:
        raise SystemExit(
            "scene-source=usd requires --scene-usd. Set the SceneUsd job "
            "parameter to the stage you want rendered."
        )

    path = Path(scene_usd)
    if not path.is_file():
        raise SystemExit(
            f"scene-usd={path} not found on the worker. It is a dataFlow: IN "
            "PATH parameter, so job attachments should have delivered it -- "
            "check that it was declared in asset_references.yaml."
        )

    _assert_stage_hash(path, expected_sha256)
    _assert_references_resolve(path)

    if _has_semantics(path):
        print(f"[sdg] {path.name} carries its own semantics, leaving them alone")
        prop = rep.create.from_usd(str(path))
    else:
        print(
            f"[sdg] {path.name} declares no semantics, labelling it "
            f"class={semantic_class!r} so the annotators emit labels"
        )
        prop = rep.create.from_usd(str(path), semantics=[("class", semantic_class)])

    # Pose only. Materials are left untouched: unlike the workshop source, this
    # is the submitter's own asset and recolouring it would corrupt the thing
    # they asked to render. Viewpoint and lighting randomization still come from
    # build_scene and apply to every source.
    with rep.trigger.on_custom_event(event_name="randomize"):
        with prop:
            rep.modify.pose(
                position=rep.distribution.uniform((-0.3, -0.3, 0.0), (0.3, 0.3, 0.1)),
                rotation=rep.distribution.uniform((0, 0, -180), (0, 0, 180)),
            )
    return prop


def build_scene(
    rep,
    scene_source: str,
    object_count: int,
    scene_usd: str = "",
    scene_usd_class: str = "asset",
    scene_usd_sha256: str = "",
):
    """Build the scene and return the camera to attach a render product to."""
    if scene_source == "primitives":
        _primitives_scene(rep, object_count)
    elif scene_source == "workshop":
        _workshop_scene(rep, object_count)
    elif scene_source == "usd":
        _usd_scene(rep, scene_usd, scene_usd_class, scene_usd_sha256)
    else:
        raise SystemExit(f"Unknown scene source: {scene_source}")

    _randomized_lighting(rep)

    camera = rep.create.camera(focal_length=24.0, name="SdgCam")
    # Orbit the camera each frame: viewpoint variation is the cheapest and most
    # effective axis of randomization for a perception dataset.
    with rep.trigger.on_custom_event(event_name="randomize"):
        with camera:
            rep.modify.pose(
                position=rep.distribution.uniform((-5.0, -5.0, 1.5), (5.0, 5.0, 5.0)),
                look_at=(0.0, 0.0, 0.6),
            )
    return camera
