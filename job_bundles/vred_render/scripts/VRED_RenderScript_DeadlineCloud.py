# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Defines the render script (referenced by a job bundle). It is invoked by a worker node
to initialize rendering settings and to perform rendering. It should always terminate VRED
after rendering (or when encountering errors) to allow a render job to continue to progress.
"""

import json
import logging
import os
import traceback

from dataclasses import dataclass
from enum import auto, Enum, IntEnum
from typing import Any, Dict, List

from builtins import vrCameraService, vrReferenceService  # type: ignore[attr-defined]
from vrController import crashVred, terminateVred
from vrOSGWidget import (
    enableRaytracing,
    isDLSSSupported,
    setDLSSQuality,
    setRenderQuality,
    setSuperSampling,
    setSuperSamplingQuality,
    VR_QUALITY_ANALYTIC_HIGH,
    VR_QUALITY_ANALYTIC_LOW,
    VR_QUALITY_NPR,
    VR_QUALITY_RAYTRACING,
    VR_QUALITY_REALISTIC_HIGH,
    VR_QUALITY_REALISTIC_LOW,
    VR_SS_QUALITY_HIGH,
    VR_SS_QUALITY_LOW,
    VR_SS_QUALITY_MEDIUM,
    VR_SS_QUALITY_OFF,
    VR_SS_QUALITY_ULTRA_HIGH,
    VR_DLSS_BALANCED,
    VR_DLSS_PERFORMANCE,
    VR_DLSS_OFF,
    VR_DLSS_QUALITY,
    VR_DLSS_ULTRA_PERFORMANCE,
)
from vrRenderSettings import (
    getRenderFilename,
    setRaytracingMode,
    setRaytracingRenderRegion,
    setRenderAlpha,
    setRenderAnimation,
    setRenderAnimationClip,
    setRenderAnimationFormat,
    setRenderAnimationType,
    setRenderFilename,
    setRenderFrameStep,
    setRenderPixelResolution,
    setRenderPremultiply,
    setRenderRegionEndX,
    setRenderRegionEndY,
    setRenderRegionStartX,
    setRenderRegionStartY,
    setRenderStartFrame,
    setRenderStopFrame,
    setRenderSupersampling,
    setRenderTonemapHDR,
    setRenderUseClipRange,
    setRenderView,
    setUseRenderPasses,
    setUseRenderRegion,
    startRenderToFile,
)
from vrSequencer import runAllSequences, runSequence


class StrEnum(str, Enum):
    """
    This is a backport of Python 3.11's StrEnum for compatibility with Python 3.10.
    """

    def __new__(cls, value):
        if not isinstance(value, str):
            raise TypeError(f"{cls.__name__} members must be strings")
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    def __str__(self):
        return str(self.value)

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> str:
        return name.lower()


class DynamicKeyValueObject:
    def __init__(self, data_dict: Dict[str, Any]) -> None:
        """
        Assigns attributes and values to this object; reflect the contents of data_dict for easy attribute-based access.
        :param: data_dict: attributes/properties and values
        """
        for k, v in data_dict.items():
            setattr(self, k, v)


class JobType(StrEnum):
    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list[str]) -> str:
        return name.capitalize()

    RENDER = auto()
    SEQUENCER = auto()


class AnimationFormat(IntEnum):
    IMAGE = 0
    VIDEO = 1


class CurrentState(IntEnum):
    Off = 0
    On = 1


@dataclass
class PathMappingRule:
    """
    Provides path mapping fields corresponding to those in the Deadline Cloud API
    path mapping JSON file.
    """

    source_path_format: str
    """The path format associated with the source path (WINDOWS vs POSIX)"""

    source_path: str
    """The path to match (convert from)"""

    destination_path: str
    """The path to transform to (from source_path)"""


class PathFormat(StrEnum):
    """
    Identifies source_path format per Deadline Cloud API path mapping JSON file.
    """

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name

    POSIX = auto()
    WINDOWS = auto()


class DeadlineCloudRenderer:
    # Note: keep enabled when not debugging
    #
    WANT_VRED_TERMINATION = True

    LOGGING_FORMAT = "%(levelname)s - %(message)s"
    LOGGING_LEVEL = logging.INFO

    DLSS_QUALITY_DICT = {
        "Off": VR_DLSS_OFF,
        "Performance": VR_DLSS_PERFORMANCE,
        "Balanced": VR_DLSS_BALANCED,
        "Quality": VR_DLSS_QUALITY,
        "Ultra Performance": VR_DLSS_ULTRA_PERFORMANCE,
    }
    RENDER_QUALITY_DICT = {
        "Analytic Low": VR_QUALITY_ANALYTIC_LOW,
        "Analytic High": VR_QUALITY_ANALYTIC_HIGH,
        "Realistic Low": VR_QUALITY_REALISTIC_LOW,
        "Realistic High": VR_QUALITY_REALISTIC_HIGH,
        "Raytracing": VR_QUALITY_RAYTRACING,
        "NPR": VR_QUALITY_NPR,
    }
    SS_QUALITY_DICT = {
        "Off": VR_SS_QUALITY_OFF,
        "Low": VR_SS_QUALITY_LOW,
        "Medium": VR_SS_QUALITY_MEDIUM,
        "High": VR_SS_QUALITY_HIGH,
        "Ultra High": VR_SS_QUALITY_ULTRA_HIGH,
    }
    ANIMATION_TYPE_DICT = {"Clip": 0, "Timeline": 1}
    CAMERA_FOUND = "Found camera in view list:"
    DLSS_SUPER_SAMPLING_ASSIGNED = "Deep Learning Supersampling quality level set to:"
    ERROR_DLSS_SUPERSAMPLING_CONFLICT = (
        "DLSS is already enabled. Non-DLSS Supersampling will be ignored."
    )
    ERROR_INVALID_ANIMATION_TYPE = "Invalid animation type"
    ERROR_INVALID_RENDER_QUALITY = "Invalid render quality"
    ERROR_INVALID_SS_QUALITY = "Invalid Supersampling quality"
    ERROR_INVALID_DLSS_QUALITY = "Invalid DLSS quality"
    ERROR_START_FRAME_EXCEEDS_END_FRAME = "StartFrame exceeds EndFrame"
    ERROR_VIEW_MISSING = "Could not find the specified camera or viewpoint name:"
    GPU_RAYTRACING_ASSIGNED = "GPU Raytracing value set to:"
    PATH_MAPPING_RULES_FIELD = "path_mapping_rules"
    READ_FLAG = "r"
    REMAPPING_FILE_REFERENCE = "Remapping file reference:"
    RENDERING_TO_FILE = "Render output filename is:"
    RUNNING_ALL_SEQUENCES_STARTING = "Starting to run all sequences"
    RUNNING_SEQUENCE_STARTING = "Starting to run the following sequence:"
    STARTING_RENDER_PROCESS = "Starting render process."
    SUPER_SAMPLING_ASSIGNED = "Supersampling quality level set to:"
    VALIDATING_RENDER_SETTINGS = "Validating render settings"
    VIEWPOINT_FOUND = "Found viewpoint in view list:"

    def __init__(self, render_parameters_dict: Dict[str, Any]) -> None:
        """
        Initializes Deadline Cloud for VRED logging and render parameters (prior to applying them later)
        :param: render_parameters_dict: a dictionary of render parameters
        """
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(format=self.LOGGING_FORMAT, level=self.LOGGING_LEVEL)
        self.path_mapping_rules: List[PathMappingRule] = []
        self.render_parameters: Any = DynamicKeyValueObject(render_parameters_dict)
        self.output_filename = self._get_conventional_output_filename()

    def _get_conventional_output_filename(self) -> str:
        """
        Initializes the convention-based output filename depending on whether there are render regions enabled
        return: output filename as a path that includes its filename as: prefix.suffix or prefix_YxX_BxA.suffix
        (filename convention for tile-based rendering).
        Note: tile assembly filename convention is specified in the job template and represents X, Y for tiling
        on row (Y) and column (X), while total tiles are denoted as [# of X tiles]x[# of Y tiles] - not the reverse!
        Tiles are initially processed left to right from top to bottom.
        """
        output_directory = self.render_parameters.OutputDir.strip().replace("\\", "/")
        output_file_prefix = self.render_parameters.OutputFileNamePrefix.strip()
        output_file_suffix = self.render_parameters.OutputFormat.strip().lower()
        output_file_render_region_prefix = ""
        if self.render_parameters.RegionRendering:
            output_file_render_region_prefix = (
                f"{self.render_parameters.TileNumberY}x"
                f"{self.render_parameters.TileNumberX}_{self.render_parameters.NumXTiles}"
                f"x{self.render_parameters.NumYTiles}"
            )
        return os.path.join(
            output_directory,
            f"{output_file_prefix}{output_file_render_region_prefix}.{output_file_suffix}",
        )

    def validate_parameter_in_dict(
        self, parameter_name: str, dictionary: Dict, error_message: str
    ) -> None:
        """
        Validates the existence of a parameter in a dictionary.
        If the parameter is not found, then an error is logged and a ValueError is raised.
        :param: parameter_name: name of parameter
        :param: dictionary: dictionary to check for parameter_name as a key name
        :param: error_message: message to print when parameter_name is absent in dictionary's keys
        :raises: ValueError: if parameter_name absent in dictionary's keys
        """
        if parameter_name not in dictionary:
            self.logger.error(f"{error_message}: {parameter_name}")
            raise ValueError(f"{error_message}: {parameter_name}")

    def validate_render_settings(self) -> None:
        """
        Validates against accepted values for specific rendering-related settings
        :raises: ValueError: if a render setting violates its accepted values/constraints
        """
        self.logger.info(self.VALIDATING_RENDER_SETTINGS)

        self.validate_parameter_in_dict(
            self.render_parameters.RenderQuality,
            self.RENDER_QUALITY_DICT,
            self.ERROR_INVALID_RENDER_QUALITY,
        )
        self.validate_parameter_in_dict(
            self.render_parameters.SSQuality,
            self.SS_QUALITY_DICT,
            self.ERROR_INVALID_SS_QUALITY,
        )
        self.validate_parameter_in_dict(
            self.render_parameters.DLSSQuality,
            self.DLSS_QUALITY_DICT,
            self.ERROR_INVALID_DLSS_QUALITY,
        )
        self.validate_parameter_in_dict(
            self.render_parameters.AnimationType,
            self.ANIMATION_TYPE_DICT,
            self.ERROR_INVALID_ANIMATION_TYPE,
        )
        if self.render_parameters.StartFrame > self.render_parameters.EndFrame:
            raise ValueError(self.ERROR_START_FRAME_EXCEEDS_END_FRAME)

    def perform_sequencer_job(self) -> None:
        """
        Performs sequencer tasks related to Sequencer-typed jobs
        """
        sequence_name = self.render_parameters.SequenceName
        if not sequence_name:
            self.logger.info(self.RUNNING_ALL_SEQUENCES_STARTING)
            runAllSequences()
        else:
            self.logger.info(f"{self.RUNNING_SEQUENCE_STARTING} {sequence_name}")
            runSequence(sequence_name)

    def init_render_quality_modes(self):
        """
        Initializes (in VRED API) settings related to render quality modes
        """
        setRenderQuality(self.RENDER_QUALITY_DICT[self.render_parameters.RenderQuality])
        supersampling_quality = self.SS_QUALITY_DICT[self.render_parameters.SSQuality]
        dlss_quality = self.DLSS_QUALITY_DICT[self.render_parameters.DLSSQuality]
        dlss_quality_applied = False
        if (dlss_quality is not VR_DLSS_OFF) and isDLSSSupported():
            self.logger.info(f"{self.DLSS_SUPER_SAMPLING_ASSIGNED} {dlss_quality}")
            setDLSSQuality(self.DLSS_QUALITY_DICT[self.render_parameters.DLSSQuality])
            dlss_quality_applied = True
        if supersampling_quality is not VR_SS_QUALITY_OFF:
            if dlss_quality_applied:
                self.process_warning(self.ERROR_DLSS_SUPERSAMPLING_CONFLICT)
            else:
                setSuperSamplingQuality(self.SS_QUALITY_DICT[self.render_parameters.SSQuality])
                self.logger.info(f"{self.SUPER_SAMPLING_ASSIGNED} {supersampling_quality}")
                setSuperSampling(CurrentState.On)
        self.logger.info(f"{self.GPU_RAYTRACING_ASSIGNED} {self.render_parameters.GPURaytracing}")
        enableRaytracing(bool(self.render_parameters.GPURaytracing))
        setRaytracingMode(self.render_parameters.GPURaytracing)

    def init_render_job(self) -> None:
        """
        Initializes (in VRED API) settings related to Render-typed jobs
        """
        self.init_camera_view(self.render_parameters.View)
        self.init_render_quality_modes()
        setRenderPixelResolution(
            self.render_parameters.ImageWidth,
            self.render_parameters.ImageHeight,
            self.render_parameters.DPI,
        )
        setRenderAnimation(self.render_parameters.RenderAnimation)
        if self.render_parameters.RenderAnimation:
            self.init_render_animation()
        setRenderAlpha(self.render_parameters.IncludeAlphaChannel)

    def init_camera_view(self, view_name: str) -> None:
        """
        Initializes (in VRED API) view (a viewpoint or camera). If view_name is empty, then the scene
        file's current active view (i.e. getRenderView()=="Current") will remain - typically the default (Perspective) camera.
        :param: view_name: the name of the viewpoint or camera.
        """
        if view_name:
            # Consider the camera or view name and use it for rendering. In case of an identically-named camera
            # and viewpoint, have that viewpoint take precedence over the camera.
            view_list = [vp.getName() for vp in vrCameraService.getAllViewpoints()]
            cam_list = vrCameraService.getCameraNames()
            if view_name in view_list:
                self.logger.info(f"{self.VIEWPOINT_FOUND} {view_name}")
                setRenderView(view_name)
                vrCameraService.getViewpoint(view_name).activate()
            elif view_name in cam_list:
                self.logger.info(f"{self.CAMERA_FOUND} {view_name}")
                setRenderView(view_name)
                vrCameraService.getCamera(view_name).activate()
            else:
                self.process_warning(f"{self.ERROR_VIEW_MISSING} {view_name}")

    def init_render_animation(self) -> None:
        """
        Initializes (in VRED API) render settings related to animations
        """
        setRenderStartFrame(self.render_parameters.StartFrame)
        setRenderStopFrame(self.render_parameters.EndFrame)
        setRenderFrameStep(self.render_parameters.FrameStep)
        setRenderAnimationFormat(AnimationFormat.IMAGE)
        setRenderAnimationType(self.ANIMATION_TYPE_DICT[self.render_parameters.AnimationType])
        setRenderAnimationClip(self.render_parameters.AnimationClip)
        # Tech note: when Supersampling is disabled, it can potentially render a black noisy frame when the GUI isn't
        # available (i.e. on Linux) for some scene files and not others. Enables basic antialiasing.
        setRenderSupersampling(CurrentState.On)
        # Frame range to be rendered is provided if the clip range is used.
        setRenderUseClipRange(False)

    def init_override_render_passes(self) -> None:
        """
        Initializes (in VRED API) render settings related to overriding render passes
        Note: additional render pass configuration options could be exposed in the future
        """
        setUseRenderPasses(self.render_parameters.ExportRenderPasses)

    def init_common_features(self) -> None:
        """
        Initializes (in VRED API) render settings common to all render jobs
        """
        setRenderPremultiply(self.render_parameters.PremultiplyAlpha)
        setRenderTonemapHDR(self.render_parameters.TonemapHDR)

    def load_path_mapping_rules(self) -> bool:
        """
        Loads path mapping rules from the Deadline Cloud API-generated path mapping JSON file.
        :return: True if rules enumerated successful; False otherwise
        """
        try:
            with open(self.render_parameters.PathMappingRulesFile, self.READ_FLAG) as file_handle:
                data = json.load(file_handle)
                self.path_mapping_rules = [
                    PathMappingRule(**mapping)
                    for mapping in data.get(self.PATH_MAPPING_RULES_FIELD)
                ]
        except Exception as exc:
            self.logger.error(exc)
            return False
        return True

    def map_path(self, path) -> str:
        """
        Maps the provided path to the appropriate destination path based on established path mapping rules per
        Deadline Cloud API convention. Loads path mapping rules if absent.
        :param: path: the path to be mapped.
        :return: the mapped destination path; note: this may be the same path if there is no appropriate mapping.
        """
        if not self.path_mapping_rules and not self.load_path_mapping_rules():
            return path
        for rule in self.path_mapping_rules:
            in_path = os.path.normpath(path)
            source_path = os.path.normpath(rule.source_path)
            in_path_norm = in_path.replace("\\", "/")
            source_path_norm = source_path.replace("\\", "/")
            # Check if path starts with source path (case-insensitive for Windows)
            if (
                rule.source_path_format == PathFormat.WINDOWS
                and in_path_norm.lower().startswith(source_path_norm.lower())
            ) or (
                rule.source_path_format == PathFormat.POSIX
                and in_path_norm.startswith(source_path_norm)
            ):
                dest_path = os.path.normpath(rule.destination_path)
                return os.path.normpath(f"{dest_path}{os.sep}{in_path[len(source_path):]}").replace(
                    "\\", os.sep
                )
        return path

    def init_file_references(self) -> None:
        """
        Initializes (in VRED API) remapped file references.
        Supports Source References and Smart References
        """
        for node in vrReferenceService.getSceneReferences():
            if node.hasSmartReference():
                orig_path = node.getSmartPath()
                self.logger.info(
                    f"{self.REMAPPING_FILE_REFERENCE}: {orig_path} -> {self.map_path(orig_path)}"
                )
                node.setSmartPath(self.map_path(orig_path))
            else:
                orig_path = node.getSourcePath()
                self.logger.info(
                    f"{self.REMAPPING_FILE_REFERENCE}: {orig_path} -> {self.map_path(orig_path)}"
                )
                node.setSourcePath(self.map_path(orig_path))

    def init_render_region(self) -> None:
        """
        Initializes (in VRED API) computed render region (tile-based) settings
        Note: regions (sizes) are automatically computed below and are 1-indexed
        Note: separate tasks are (currently) generated per individual tile
        """
        setUseRenderRegion(self.render_parameters.RegionRendering)
        if self.render_parameters.RegionRendering:
            # Tile number uses 1-based indexing. Treat first tile (top left) as x=0, y=0.
            tile_num_x = self.render_parameters.TileNumberX
            tile_num_y = self.render_parameters.TileNumberY
            total_x_tiles = self.render_parameters.NumXTiles
            total_y_tiles = self.render_parameters.NumYTiles
            width = self.render_parameters.ImageWidth
            height = self.render_parameters.ImageHeight
            # Calculate the bounds for the tile with rounding applied.
            # Include a small overlap between tiles for addressing tile gap concerns
            left = int((float(width) / total_x_tiles * (tile_num_x - 1)) + 0.5)
            right = int((float(width) / total_x_tiles * tile_num_x) + 0.5)
            bottom = int((float(height) / total_y_tiles * (tile_num_y - 1)) + 0.5)
            top = int((float(height) / total_y_tiles * tile_num_y) + 0.5)
            # Set the border ranges for the tile
            setRenderRegionStartX(left)
            setRenderRegionEndX(right)
            setRenderRegionStartY(bottom)
            setRenderRegionEndY(top)
            # Set the active render region per convention: setRaytracingRenderRegion(xBegin, yBegin, xEnd, yEnd)
            # Each parameter becomes a relative normalized coordinate (in [0.0,1.0]).
            left = float(left) / self.render_parameters.ImageWidth
            right = float(right) / self.render_parameters.ImageWidth
            bottom = float(bottom) / self.render_parameters.ImageHeight
            top = float(top) / self.render_parameters.ImageHeight
            setRaytracingRenderRegion(left, 1 - top, right, 1 - bottom)
            # Ensures that the render region will be respected
            enableRaytracing(True)

    def init_by_job_type(self) -> None:
        """
        Initializes render settings by render job type
        """
        job_type = self.render_parameters.JobType
        if job_type == JobType.SEQUENCER:
            self.perform_sequencer_job()
        elif job_type == JobType.RENDER:
            self.init_render_job()

    def init_render_settings(self) -> None:
        """
        High-level render settings initialization method
        """
        self.init_by_job_type()
        if self.render_parameters.OverrideRenderPass:
            self.init_override_render_passes()
        self.init_common_features()
        self.init_render_region()
        setRenderFilename(self.output_filename)

    def process_warning(self, message) -> None:
        """
        Logs a warning
        :param: message: warning message to log
        """
        self.logger.warning(message)

    def render(self) -> None:
        """
        High-level render initiation routine with error handling
        """
        try:
            self.validate_render_settings()
            self.init_file_references()
            self.init_render_settings()
            self.logger.info(self.STARTING_RENDER_PROCESS)
            self.logger.info(f"{self.RENDERING_TO_FILE} {getRenderFilename()}")
            startRenderToFile(True)
            # Important to close VRED for further frame rendering to proceed and to release license
            if self.WANT_VRED_TERMINATION:
                terminateVred()
        except Exception as exc:
            self.logger.error(exc)
            self.logger.error(traceback.format_exc())
            if self.WANT_VRED_TERMINATION:
                crashVred(1)
        finally:
            if self.WANT_VRED_TERMINATION:
                terminateVred()


def deadline_cloud_render(render_parameters_dict: Dict[str, Any]) -> None:
    """
    Main entry point (to be triggered externally and indirectly via VRED "postpython" argument):
    - reads render parameters and values from a dictionary (render_parameters_dict)
    - applies render parameter values to VRED API
    - initiates rendering process with error handling
    :param: render_parameters_dict: a dictionary containing the render parameters and values
    """
    if render_parameters_dict:
        renderer = DeadlineCloudRenderer(render_parameters_dict)
        renderer.render()
