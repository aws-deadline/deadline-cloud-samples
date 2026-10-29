"""Stand-in for ``omni.client`` that reports every remote path as absent.

``omniverseclient`` supplies the real module. It is NVIDIA-proprietary and publishes
``manylinux_2_35`` wheels only, while Amazon Linux 2023 ships glibc 2.34, so it is excluded
from ``requirements-isaaclab3.txt``.

Isaac Lab imports it lazily, but not only on the remote-asset path.
``isaaclab.utils.assets.retrieve_file_path`` runs ``UsdUtils.ModifyAssetPaths`` over every
USD layer and tests each reference for existence to decide whether to rewrite it. That test
consults a remote lookup for anything absent locally, and the lookup imports
``omni.client``. Isaac Lab's default ground plane references ``OmniPBR.mdl``, which ships
inside Omniverse Kit, so a fully prefetched scene still reaches it.

Reporting "not found" leaves such a reference anchored and unrewritten. That is correct for
a material binding in a headless run with no camera sensors, where nothing evaluates it.

A missing asset therefore fails instead of downloading on demand, so every asset a task
needs must be prefetched by ``prefetch_assets.py``.

Workflows that evaluate MDL materials or render with RTX need Isaac Lab's ``ov`` extra,
which reinstates both the proprietary dependency and the glibc 2.35 floor, and with it a
container.
"""

import logging

logger = logging.getLogger(__name__)


class Result:
    """Subset of ``omni.client.Result`` that ``isaaclab.utils.assets`` compares against."""

    OK = 0
    ERROR_NOT_FOUND = 1


class CopyBehavior:
    """Subset of ``omni.client.CopyBehavior`` referenced by the download path."""

    OVERWRITE = 0


def stat(url):
    """Report every remote path as absent.

    Returns:
        A ``(result, entry)`` tuple. ``result`` is never ``Result.OK``, so the caller
        treats the path as not present on a server and returns 0 from
        ``check_file_path``.
    """
    logger.info("omni.client shim: stat(%s) -> ERROR_NOT_FOUND", url)
    return (Result.ERROR_NOT_FOUND, None)


def copy(source, target, behavior=None):
    """Fail loudly. Reached only if something asks for a remote asset at runtime."""
    raise RuntimeError(
        "The omni.client shim cannot download %r. This environment has no Omniverse client, "
        "so remote assets are unavailable by design. Add the file to the prefetch manifest "
        "and re-run prefetch_assets.py instead." % (source,)
    )


def set_s3_configuration(**kwargs):
    """No-op. Only called when ISAACSIM_ASSET_REGION_PROFILE is set, which this sample avoids."""
    return Result.OK
