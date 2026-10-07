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


def build_scene(rep, scene_source: str, object_count: int):
    """Build the scene and return the camera to attach a render product to."""
    if scene_source == "primitives":
        _primitives_scene(rep, object_count)
    elif scene_source == "workshop":
        _workshop_scene(rep, object_count)
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
