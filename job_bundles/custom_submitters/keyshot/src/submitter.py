# AUTHOR AWS
# VERSION 0.5.0
# Submit to AWS Deadline Cloud

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import glob
import json
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import lux

RENDER_SUBMITTER_SETTINGS_FILE_EXT = ".deadline_render_settings.json"
SUBMISSION_MODE_KEY = "submission_mode"
# Unique ID required to allow KeyShot to save selections for a dialog
DEADLINE_CLOUD_DIALOG_ID = "e309ce79-3ee8-446a-8308-10d16dfcbb42"

_SERVER_START_TIMEOUT_SECONDS = 30
_SERVER_END_TIMEOUT_SECONDS = 30
_KEYSHOT_START_TIMEOUT_SECONDS = 300
_KEYSHOT_END_TIMEOUT_SECONDS = 30

KEYSHOT_ENVIRON_ENTER_TIMEOUT = _SERVER_START_TIMEOUT_SECONDS + _KEYSHOT_START_TIMEOUT_SECONDS + 60
KEYSHOT_ENVIRON_EXIT_TIMEOUT = _SERVER_END_TIMEOUT_SECONDS + _KEYSHOT_END_TIMEOUT_SECONDS + 60


@dataclass
class Settings:
    parameter_values: list[dict[str, Any]]  # [{"name": "my_param_name", "value": X}]
    input_filenames: list[str]
    input_directories: list[str]
    output_directories: list[str]
    referenced_paths: list[str]
    auto_detected_input_filenames: list[str]

    def output_sticky_settings(self) -> dict:
        return {
            # we always use the current the KeyShotFile
            "parameterValues": [
                param for param in self.parameter_values if param["name"] != "KeyShotFile"
            ],
            "inputFilenames": self.input_filenames,
            "inputDirectories": self.input_directories,
            "outputDirectories": self.output_directories,
            "referencedPaths": self.referenced_paths,
            # Do not include auto-detected inputs and outputs since they should not be sticky
        }

    def apply_sticky_settings(self, sticky_settings: dict) -> None:
        input_parameter_values = sticky_settings.get("parameterValues", [])

        updated_parameter_values = {}

        for param in self.parameter_values:
            updated_parameter_values[param["name"]] = param["value"]

        for param in input_parameter_values:
            if param.get("name") and param.get("value"):
                # Don't re-use KeyShotFile or AdaptorScriptsDir, they are in a new temp dir for every submission
                # Don't preserve CondaPackages so the Keyshot version can be updated by updating the submitter
                if param["name"] in [
                    "KeyShotFile",
                    "AdaptorScriptsDir",
                    "CondaPackages",
                ]:
                    continue
                updated_parameter_values[param["name"]] = param["value"]

        self.parameter_values = [
            {"name": parameter_name, "value": updated_parameter_values[parameter_name]}
            for parameter_name in updated_parameter_values
        ]

        self.input_filenames = sticky_settings.get("inputFilenames", self.input_filenames)
        self.input_directories = sticky_settings.get("inputDirectories", self.input_directories)
        self.output_directories = sticky_settings.get("outputDirectories", self.output_directories)
        self.referenced_paths = sticky_settings.get("referencedPaths", self.referenced_paths)

    def apply_submitter_settings(self, output: dict) -> None:
        job_bundle_history_dir = output.get("jobHistoryBundleDirectory")
        if not job_bundle_history_dir:
            return
        with open(
            os.path.join(job_bundle_history_dir, "parameter_values.json"), encoding="utf-8"
        ) as parameter_values_file:
            self.parameter_values = json.load(parameter_values_file).get("parameterValues", [])
        with open(
            os.path.join(job_bundle_history_dir, "asset_references.json"), encoding="utf-8"
        ) as asset_references_file:
            asset_references_contents = json.load(asset_references_file)
        asset_references = asset_references_contents.get("assetReferences", {})

        if asset_references.get("inputs", {}).get("filenames"):
            # Persist input files that were not autodetected (i.e. were manually added)
            self.input_filenames = list(
                set(asset_references["inputs"]["filenames"])
                - set(self.auto_detected_input_filenames)
            )
        if asset_references.get("inputs", {}).get("directories"):
            self.input_directories = asset_references["inputs"]["directories"]
        if asset_references.get("outputs", {}).get("directories"):
            self.output_directories = asset_references["outputs"]["directories"]
        if asset_references.get("referencedPaths"):
            self.referenced_paths = asset_references["referencedPaths"]


def construct_job_template(filename: str) -> dict:
    """
    Constructs and returns a dict containing a valid job template for the KeyShot job.
    The return value is safe to convert/dump to JSON or YAML.
    """

    return {
        "specificationVersion": "jobtemplate-2023-09",
        "name": filename,
        "parameterDefinitions": [
            {
                "name": "AdaptorScriptsDir",
                "description": "Directory containing adaptor scripts.",
                "userInterface": {"control": "HIDDEN"},
                "type": "PATH",
                "objectType": "DIRECTORY",
                "dataFlow": "IN",
                "default": "adaptor",
                "maxLength": 10000,
            },
            {
                "name": "KeyShotFile",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {
                    "control": "HIDDEN",
                    "label": "KeyShot Package File",
                    "groupLabel": "KeyShot Settings",
                },
                "description": "The KeyShot package file to render.",
                "default": "",  # Workaround for https://github.com/aws-deadline/deadline-cloud/issues/343
                "maxLength": 10000,
            },
            {
                "name": "Frames",
                "type": "STRING",
                "userInterface": {
                    "control": "LINE_EDIT",
                    "label": "Frames",
                    "groupLabel": "KeyShot Settings",
                },
                "description": "The frames to render e.g. 1-3,8,11-15",
                "minLength": 1,
                "maxLength": 10000,
            },
            {
                "name": "OutputFilePath",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "OUT",
                "userInterface": {
                    "control": "CHOOSE_OUTPUT_FILE",
                    "label": "Output File Path",
                    "groupLabel": "KeyShot Settings",
                },
                "description": "The render output path.",
                "maxLength": 10000,
            },
            {
                "name": "OutputFormat",
                "type": "STRING",
                "description": "The render output format.",
                "allowedValues": [
                    "PNG",
                    "JPEG",
                    "EXR",
                    "TIFF8",
                    "TIFF32",
                    "PSD8",
                    "PSD16",
                    "PSD32",
                ],
                "default": "PNG",
                "userInterface": {
                    "control": "DROPDOWN_LIST",
                    "label": "Output Format (must match file extension)",
                    "groupLabel": "KeyShot Settings",
                },
            },
            {
                "name": "OverrideRenderDevice",
                "type": "STRING",
                "description": "Whether to override the render device set in KeyShot.",
                "allowedValues": ["True", "False"],
                "default": "False",
                "userInterface": {
                    "control": "CHECK_BOX",
                    "label": "Override KeyShot render device",
                    "groupLabel": "KeyShot Settings",
                },
            },
            {
                "name": "RenderDevice",
                "type": "STRING",
                "description": "The render device to use (CPU or GPU).",
                "allowedValues": ["CPU", "GPU"],
                "default": get_current_render_device(),
                "userInterface": {
                    "control": "DROPDOWN_LIST",
                    "label": "Render Device (For GPU: must set host requirement min GPUs to 1)",
                    "groupLabel": "KeyShot Settings",
                },
            },
        ],
        "steps": [
            {
                "name": "Render",
                "hostRequirements": {
                    "attributes": [{"name": "attr.worker.os.family", "anyOf": ["windows"]}]
                },
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"}
                    ]
                },
                "stepEnvironments": [
                    {
                        "name": "KeyShot",
                        "description": "Runs KeyShot in the background.",
                        "script": {
                            "actions": {
                                "onEnter": {
                                    "command": "python",
                                    "args": [
                                        "{{Param.AdaptorScriptsDir}}/session_manager.py",
                                        "start",
                                        "--scene-file",
                                        "{{Param.KeyShotFile}}",
                                        "--keyshot-command-handler-script",
                                        "{{Param.AdaptorScriptsDir}}/keyshot_command_handler.py",
                                        "--keyshot-bridge-script",
                                        "{{Param.AdaptorScriptsDir}}/keyshot_bridge.py",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                    "timeout": KEYSHOT_ENVIRON_ENTER_TIMEOUT,
                                },
                                "onExit": {
                                    "command": "python",
                                    "args": [
                                        "{{Param.AdaptorScriptsDir}}/session_manager.py",
                                        "stop",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                    "timeout": KEYSHOT_ENVIRON_EXIT_TIMEOUT,
                                },
                            },
                        },
                    },
                ],
                "script": {
                    "actions": {
                        "onRun": {
                            "command": "python",
                            "args": [
                                "{{Param.AdaptorScriptsDir}}/task_manager.py",
                                "--frame",
                                "{{Task.Param.Frame}}",
                                "--output-path",
                                "{{Param.OutputFilePath}}",
                                "--output-format",
                                "{{Param.OutputFormat}}",
                                "--render-device",
                                "{{Param.RenderDevice}}",
                                "--override-render-device",
                                "{{Param.OverrideRenderDevice}}",
                                "--render-options",
                                f"{json.dumps(lux.getRenderOptions().getDict())}",
                            ],
                            "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                        }
                    },
                },
            }
        ],
    }


def construct_asset_references(settings: Settings) -> dict:
    """
    Constructs and returns the asset references in a dict that is safe to convert/dump to JSON or YAML.
    """
    return {
        "assetReferences": {
            "inputs": {
                "directories": sorted(settings.input_directories),
                "filenames": sorted(
                    list(set([*settings.input_filenames, *settings.auto_detected_input_filenames]))
                ),
            },
            "outputs": {"directories": sorted(settings.output_directories)},
            "referencedPaths": sorted(settings.referenced_paths),
        }
    }


def construct_parameter_values(settings: Settings) -> dict:
    """
    Constructs and returns the parameter values in a dict that is safe to convert/dump to JSON or YAML.
    """
    return {
        "parameterValues": settings.parameter_values,
    }


def dump_json_to_dir(contents: dict, directory: str, filename: str) -> None:
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as file:
        file.write(json.dumps(contents))


def substitute_suffix(path: str, suffix: str) -> str:
    root, _ext = os.path.splitext(path)
    return root + suffix


def load_sticky_settings(scene_filename: str) -> Optional[dict[Any, Any]]:
    sticky_settings_filename = substitute_suffix(scene_filename, RENDER_SUBMITTER_SETTINGS_FILE_EXT)
    if os.path.exists(sticky_settings_filename) and os.path.isfile(sticky_settings_filename):
        try:
            with open(sticky_settings_filename, encoding="utf8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except (OSError, json.JSONDecodeError):
            # Fall back to defaults if there's an error loading sticky settings
            import traceback

            traceback.print_exc()
            print(
                f"WARNING: Failed to load {sticky_settings_filename}. Reverting to the default settings."
            )
    return None


def save_sticky_settings(scene_file: str, settings: Settings) -> None:
    sticky_settings_filename = substitute_suffix(scene_file, RENDER_SUBMITTER_SETTINGS_FILE_EXT)
    with open(sticky_settings_filename, "w", encoding="utf8") as f:
        json.dump(settings.output_sticky_settings(), f, indent=2)


def bundle_submit(bundle_directory: str, show_gui: bool = True) -> Optional[dict[str, Any]]:
    deadline_bundle_command = "gui-submit" if show_gui else "submit"
    additional_args = ["--output", "json", "--install-gui"] if show_gui else []
    try:
        if platform.system() == "Darwin" or platform.system() == "Linux":
            # Execute the command using an bash in interactive mode so it loads loads the bash profile to set
            # the PATH correctly. Attempting to run `deadline` directly will probably fail since Keyshot's default
            # PATH likely doesn't include the Deadline client.
            shell_executable = os.environ.get("SHELL", "/bin/bash")
            result = subprocess.run(
                [
                    shell_executable,
                    "-i",
                    "-c",
                    f"echo \"START_DEADLINE_OUTPUT\"; deadline bundle {deadline_bundle_command} '{bundle_directory}' {' '.join(additional_args)} --submitter-name KeyShot",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            # Hack to ignore any output from the bash profile script
            output = result.stdout.split("START_DEADLINE_OUTPUT")[-1]
        else:
            result = subprocess.run(
                [
                    "deadline",
                    "bundle",
                    deadline_bundle_command,
                    str(bundle_directory),
                    *additional_args,
                    "--submitter-name",
                    "KeyShot",
                ],
                check=True,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
            )
            output = result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"AWS Deadline Cloud KeyShot submitter could not open: {e.stderr}")
    try:
        return json.loads(output)  # type: ignore[no-any-return]
    except json.JSONDecodeError as e:
        print(f"Error parsing deadline CLI output as json: {e}")
        return None


def options_dialog(show_gui: bool = True) -> dict[str, Any]:
    """
    Builds and displays a dialog within KeyShot to get the submission options
    reuired before the main gui submission window is opened outside of KeyShot.
    Options:
        Option 1: Dropdown to select whether to submit just the scene file itself
                  or all external file references as well by packing/unpacking a
                  KSP bundle before submission.
    Returns a dictionary of the selected option values in the format:
        {'SUBMISSION_MODE_KEY': [1, 'only the scene BIP file']}
    """
    BIP_AND_REFERENCES = "The scene BIP file and all external files references"
    ONLY_BIP = "Only the scene BIP file"
    if not show_gui:
        return {SUBMISSION_MODE_KEY: [0, BIP_AND_REFERENCES]}
    dialog_items = [
        (
            SUBMISSION_MODE_KEY,
            lux.DIALOG_ITEM,
            "What files would you like to attach to the job?",
            0,
            [BIP_AND_REFERENCES, ONLY_BIP],
        ),
    ]
    selections = lux.getInputDialog(
        title="AWS Deadline Cloud Submission Options",
        values=dialog_items,
        id=DEADLINE_CLOUD_DIALOG_ID,
    )

    return selections  # type: ignore[no-any-return]


def save_ksp_bundle(directory: str, bundle_name: str) -> str:
    """
    Saves out the current scene and any file references to a ksp bundle in a
    directory.
    Returns the file path where the bundle was saved to.
    """
    full_ksp_path = os.path.join(directory, bundle_name)

    if not lux.savePackage(path=full_ksp_path):
        raise RuntimeError("KSP was not able to be saved!")

    return full_ksp_path


def get_ksp_bundle_files(directory: str) -> Tuple[str, list[str]]:
    """
    Creates a ksp bundle from the current scene containing the scene file and
    any external file references. The bundle is unpacked into a directory passed
    in.
    Returns the scene file and a list of the external files from the directory
    where the ksp was extracted to.
    """

    ksp_dir = os.path.join(directory, "ksp")
    unpack_dir = os.path.join(directory, "unpack")
    ksp_archive = save_ksp_bundle(ksp_dir, "temp_deadline_cloud.zip")
    if platform.system() == "Darwin" or platform.system() == "Linux":
        subprocess.run(
            ["unzip", "-o", ksp_archive, "-d", unpack_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    else:
        subprocess.run(
            [
                "PowerShell",
                "-Command",
                '$ProgressPreference = "SilentlyContinue"',  # don't display progress bar, up to 4x speedup
                ";",
                "Expand-Archive",
                "-Path",
                ksp_archive,
                "-DestinationPath",
                unpack_dir,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    input_filenames = [
        os.path.join(unpack_dir, file)
        for file in os.listdir(unpack_dir)
        if not file.endswith(".bip")
    ]
    bip_files = glob.glob(os.path.join(unpack_dir, "*.bip"))

    if not bip_files:
        raise RuntimeError("No .bip files found in the KSP bundle.")
    elif len(bip_files) > 1:
        raise RuntimeError("Multiple .bip files found in the KSP bundle.")

    bip_file = bip_files[0]

    return bip_file, input_filenames


def main(show_gui: bool = True, export_dir: Optional[str] = None) -> None:
    """
    Args:
        * show_gui:
            Show the submission GUI components.
            If this is False, all submitter settings will use the defaults during submission/export.
        * export_dir:
            The bundle will be exported to the specified directory instead of submitted.
            Only usable when show_gui=False.
    """
    if export_dir and show_gui:
        raise RuntimeError(
            "The export_dir argument can only be used when the show_gui flag is False."
        )
    if lux.isPaused():
        # If rendering is already paused, run the function normally
        main_inner(show_gui, export_dir)
    else:
        # If render is not already paused, pause while running then resume
        try:
            lux.pause()
            main_inner(show_gui, export_dir)
        finally:
            lux.unpause()


def main_inner(show_gui: bool = True, export_dir: Optional[str] = None) -> None:
    if lux.isSceneChanged():
        result = lux.getInputDialog(
            title="Unsaved changes",
            values=[(lux.DIALOG_LABEL, "You have unsaved changes. Do you want to save your file?")],
        )
        # result is {} if the user clicks Ok and None if the user clicks cancel
        if result is None:
            # Raise an exception so Keyshot shows the script's result status as "Failure" instead of "Success"
            raise Exception("Changes must be saved before submitting.")
        else:
            lux.saveFile()

    dialog_selections = options_dialog(show_gui)

    if not dialog_selections:
        # Dialog was canceled. Raise an exception so Keyshot does not show the script's result status as "Success"
        raise Exception("Submission was canceled.")

    scene_info = lux.getSceneInfo()
    scene_file = scene_info["file"]
    scene_name, _ = os.path.splitext(scene_info["name"])
    current_frame = lux.getAnimationFrame()
    frame_count = lux.getAnimationInfo().get("frames")

    settings = Settings(
        parameter_values=[
            {
                "name": "Frames",
                "value": f"1-{frame_count}" if frame_count else f"{current_frame}",
            },
            {
                "name": "OutputFilePath",
                "value": os.path.join(os.path.dirname(scene_file), f"{scene_name}.%d.png"),
            },
            {
                "name": "OutputFormat",
                "value": "PNG",
            },
        ],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    sticky_settings = load_sticky_settings(scene_file)
    if sticky_settings:
        settings.apply_sticky_settings(sticky_settings)

    if export_dir:
        create_bundle(settings, dialog_selections, scene_file, scene_name, export_dir)
        output: Optional[dict] = {"status": "SUCCEEDED"}
    else:
        with tempfile.TemporaryDirectory() as bundle_temp_dir:
            create_bundle(settings, dialog_selections, scene_file, scene_name, bundle_temp_dir)
            output = bundle_submit(bundle_temp_dir, show_gui)

    if output:
        if output.get("status") == "CANCELED":
            # Raise an exception so Keyshot does not show the script's result status as "Success"
            raise Exception("Submission was canceled.")

        settings.apply_submitter_settings(output)
        save_sticky_settings(scene_file, settings)


def create_bundle(
    settings: Settings,
    dialog_selections: dict[str, Any],
    scene_file: str,
    scene_name: str,
    bundle_dir: str,
) -> None:
    # {'submission_mode': [0, 'the scene BIP file and all external files references']}
    if not dialog_selections[SUBMISSION_MODE_KEY][0]:
        temp_scene_file, input_filenames = get_ksp_bundle_files(bundle_dir)
        settings.auto_detected_input_filenames = input_filenames
        settings.parameter_values.append({"name": "KeyShotFile", "value": temp_scene_file})
    else:
        settings.parameter_values.append({"name": "KeyShotFile", "value": scene_file})

    override_enabled = False
    override_param_found = False
    for param in settings.parameter_values:
        if param["name"] == "OverrideRenderDevice":
            override_enabled = param["value"] == "True"
            override_param_found = True
            break
    if not override_param_found:
        settings.parameter_values.append({"name": "OverrideRenderDevice", "value": "False"})

    if not override_enabled:
        render_device = get_current_render_device()

        render_device_found = False
        for param in settings.parameter_values:
            if param["name"] == "RenderDevice":
                param["value"] = render_device
                render_device_found = True
                break

        if not render_device_found:
            settings.parameter_values.append({"name": "RenderDevice", "value": render_device})
    else:
        render_device = None
        for param in settings.parameter_values:
            if param["name"] == "RenderDevice":
                render_device = param["value"]
                break

        if render_device is None:
            render_device = get_current_render_device()
            settings.parameter_values.append({"name": "RenderDevice", "value": render_device})

    # Add default value for CondaPackages. Deadline Cloud does not provide a KeyShot conda package, so
    # CondaChannels is left to the queue environment so it can point at the channel hosting your own package.
    major_version, _minor_version = lux.getKeyShotDisplayVersion()
    settings.parameter_values.append(
        {
            "name": "CondaPackages",
            "value": f"keyshot={major_version}.*",
        }
    )

    # Add adaptor scripts
    scripts_dir = os.path.join(bundle_dir, "adaptor")
    os.makedirs(scripts_dir, exist_ok=True)

    # Contents in the f.write calls will be replaced with the actual script contents by build.py
    with open(os.path.join(scripts_dir, "session_manager.py"), "w", encoding="utf-8") as f:
        f.write("SESSION_MANAGER_SCRIPT")
    with open(os.path.join(scripts_dir, "keyshot_bridge.py"), "w", encoding="utf-8") as f:
        f.write("KEYSHOT_BRIDGE_SCRIPT")
    with open(os.path.join(scripts_dir, "keyshot_command_handler.py"), "w", encoding="utf-8") as f:
        f.write("KEYSHOT_COMMAND_HANDLER_SCRIPT")
    with open(os.path.join(scripts_dir, "task_manager.py"), "w", encoding="utf-8") as f:
        f.write("TASK_MANAGER_SCRIPT")

    job_template = construct_job_template(scene_name)
    asset_references = construct_asset_references(settings)
    parameter_values = construct_parameter_values(settings)

    # Add GPU requirements if needed
    if override_enabled and render_device == "GPU":
        job_template["steps"][0]["hostRequirements"]["amounts"] = [
            {"name": "amount.worker.gpu", "min": 1}
        ]

    dump_json_to_dir(job_template, bundle_dir, "template.json")
    dump_json_to_dir(asset_references, bundle_dir, "asset_references.json")
    dump_json_to_dir(parameter_values, bundle_dir, "parameter_values.json")


def get_current_render_device() -> str:
    current_engine = lux.getRenderEngine()
    is_gpu = current_engine in [lux.RENDER_ENGINE_PRODUCT_GPU, lux.RENDER_ENGINE_INTERIOR_GPU]
    return "GPU" if is_gpu else "CPU"


if __name__ == "__main__":
    import sys

    # Check for --bundle flag for headless testing
    if len(sys.argv) >= 3 and sys.argv[1] == "--bundle":
        bundle_path = os.path.abspath(sys.argv[2])
        # Create directory if it doesn't exist
        os.makedirs(bundle_path, exist_ok=True)
        main(show_gui=False, export_dir=bundle_path)
    else:
        main()
