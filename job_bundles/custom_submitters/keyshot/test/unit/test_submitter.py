# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

import pytest

# Add src directory to path to import submitter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from . import lux_import_override  # noqa F401
import submitter

RENDER_ENGINE_PRODUCT = 0
RENDER_ENGINE_INTERIOR = 1
RENDER_ENGINE_PRODUCT_GPU = 2
RENDER_ENGINE_INTERIOR_GPU = 3


@pytest.fixture
def mock_lux_is_scene_changed():
    with mock.patch.object(submitter.lux, "isSceneChanged") as is_scene_changed_mock:
        yield is_scene_changed_mock


@pytest.fixture
def mock_lux_get_input_dialog():
    with mock.patch.object(submitter.lux, "getInputDialog") as get_input_dialog_mock:
        yield get_input_dialog_mock


@pytest.fixture
def mock_lux_save_file():
    with mock.patch.object(submitter.lux, "saveFile") as save_file_mock:
        yield save_file_mock


@pytest.fixture
def mock_lux_save_package():
    with mock.patch.object(submitter.lux, "savePackage") as save_package_mock:
        yield save_package_mock


@pytest.fixture
def mock_lux_is_paused():
    with mock.patch.object(submitter.lux, "isPaused") as is_paused_mock:
        yield is_paused_mock


@pytest.fixture
def mock_lux_pause():
    with mock.patch.object(submitter.lux, "pause") as pause_mock:
        yield pause_mock


@pytest.fixture
def mock_lux_unpause():
    with mock.patch.object(submitter.lux, "unpause") as unpause_mock:
        yield unpause_mock


@pytest.fixture(autouse=True)
def mock_lux_get_render_options():
    class MockRenderOptions:
        def __init__(self):
            self.__dict__ = {}

        def getDict(self):
            return {"__VERSION": 5}

    with mock.patch.object(submitter.lux, "getRenderOptions") as get_render_options_mock:
        get_render_options_mock.return_value = MockRenderOptions()
        yield get_render_options_mock


def test_construct_job_template():
    filename = "test_filename"

    job_template = submitter.construct_job_template(filename)

    assert job_template["name"] == filename


def test_construct_asset_references():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "KeyShotFile", "value": "test_scene_file"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        input_filenames=["test_filename_1"],
        auto_detected_input_filenames=["test_filename_2"],
        input_directories=["test_directory_1", "test_directory_2"],
        output_directories=["test_directory_3"],
        referenced_paths=["reference_path_1", "reference_path_2"],
    )

    asset_references = submitter.construct_asset_references(settings)

    assert asset_references["assetReferences"]["inputs"]["filenames"] == [
        "test_filename_1",
        "test_filename_2",
    ]
    assert (
        asset_references["assetReferences"]["inputs"]["directories"] == settings.input_directories
    )
    assert (
        asset_references["assetReferences"]["outputs"]["directories"] == settings.output_directories
    )
    assert asset_references["assetReferences"]["referencedPaths"] == settings.referenced_paths


def test_construct_parameter_values():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "KeyShotFile", "value": "test_scene_file"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    parameter_values = submitter.construct_parameter_values(settings)

    assert parameter_values == {
        "parameterValues": [
            {"name": "KeyShotFile", "value": "test_scene_file"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ]
    }


def test_settings_serialize_correctly():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "KeyShotFile", "value": "test_scene_file"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        input_filenames=["test_filename_1"],
        auto_detected_input_filenames=["test_directory_3"],
        input_directories=["test_directory_1"],
        output_directories=["test_directory_2"],
        referenced_paths=["test_ref_path"],
    )

    assert settings.output_sticky_settings() == {
        "parameterValues": [
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        "inputFilenames": ["test_filename_1"],
        "inputDirectories": ["test_directory_1"],
        "outputDirectories": ["test_directory_2"],
        "referencedPaths": ["test_ref_path"],
    }


def test_settings_apply_sticky_settings():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "KeyShotFile", "value": "test_scene_file"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        input_filenames=["test_filename_1"],
        auto_detected_input_filenames=["test_filename_2"],
        input_directories=["test_directory_1"],
        output_directories=["test_directory_2"],
        referenced_paths=["test_ref_path"],
    )
    initial_settings = settings.output_sticky_settings()

    settings.apply_sticky_settings({})
    assert settings.output_sticky_settings() == initial_settings

    settings.apply_sticky_settings(
        {
            "parameterValues": [
                {"name": "OutputFilePath", "value": "test_output_2"},
                {"name": "OutputFormat", "value": "JPEG"},
                {"name": "Frames", "value": "20-27"},
            ],
            "inputFilenames": ["test_filename_10"],
            "inputDirectories": ["test_directory_11"],
            "outputDirectories": ["test_directory_12"],
            "referencedPaths": ["test_ref_path_2"],
        }
    )

    assert settings.parameter_values == [
        {"name": "KeyShotFile", "value": "test_scene_file"},
        {"name": "OutputFilePath", "value": "test_output_2"},
        {"name": "OutputFormat", "value": "JPEG"},
        {"name": "Frames", "value": "20-27"},
    ]
    assert settings.input_filenames == ["test_filename_10"]
    assert settings.input_directories == ["test_directory_11"]
    assert settings.output_directories == ["test_directory_12"]
    assert settings.referenced_paths == ["test_ref_path_2"]

    settings.apply_sticky_settings(
        {
            "parameterValues": [
                # Some parameters should not be sticky
                {"name": "KeyShotFile", "value": "scene_file_from_sticky_settings"},
                {"name": "CondaPackages", "value": "keyshot=2023.* keyshot-openjd=0.0.1"},
                # CondaChannels should be sticky so users can point at their own channel
                {"name": "CondaChannels", "value": "s3://my-bucket/conda-channel"},
            ],
            "inputFilenames": ["test_filename_20"],
            "inputDirectories": ["test_directory_21"],
            "outputDirectories": ["test_directory_22"],
            "referencedPaths": ["test_ref_path_3"],
        }
    )

    assert settings.parameter_values == [
        {"name": "KeyShotFile", "value": "test_scene_file"},
        {"name": "OutputFilePath", "value": "test_output_2"},
        {"name": "OutputFormat", "value": "JPEG"},
        {"name": "Frames", "value": "20-27"},
        {"name": "CondaChannels", "value": "s3://my-bucket/conda-channel"},
    ]
    assert settings.input_filenames == ["test_filename_20"]
    assert settings.input_directories == ["test_directory_21"]
    assert settings.output_directories == ["test_directory_22"]
    assert settings.referenced_paths == ["test_ref_path_3"]


def test_settings_apply_submitter_settings():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "KeyShotFile", "value": "scene_file_from_scene"},
            {"name": "OutputFilePath", "value": r"test_scene_file.%d.png"},
            {"name": "OutputFormat", "value": "PNG"},
            {"name": "Frames", "value": "10-17"},
        ],
        input_filenames=["test_filename_1"],
        auto_detected_input_filenames=["test_filename_2"],
        input_directories=["test_directory_1"],
        output_directories=["test_directory_2"],
        referenced_paths=["test_ref_path"],
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        with open(
            os.path.join(temp_dir, "parameter_values.json"), "w", encoding="utf-8"
        ) as parameter_values_file:
            json.dump(
                {
                    "parameterValues": [
                        {"name": "KeyShotFile", "value": "scene_file_from_gui_submit"},
                        {"name": "Frames", "value": "20-27"},
                        {"name": "OutputFilePath", "value": "test_output_2"},
                        {"name": "OutputFormat", "value": "JPEG"},
                    ],
                },
                parameter_values_file,
            )
        with open(
            os.path.join(temp_dir, "asset_references.json"), "w", encoding="utf-8"
        ) as asset_references_file:
            json.dump(
                {
                    "assetReferences": {
                        "inputs": {
                            "filenames": [
                                "test_filename_1",
                                "test_filename_2",
                                "test_filename_3",
                            ],
                            "directories": ["test_directory_2"],
                        },
                        "outputs": {
                            "directories": [
                                "test_directory_2",
                                "test_directory_3",
                            ]
                        },
                        "referencedPaths": ["test_ref_path_2"],
                    },
                },
                asset_references_file,
            )
        settings.apply_submitter_settings({"jobHistoryBundleDirectory": temp_dir})

    assert settings.parameter_values == [
        {"name": "KeyShotFile", "value": "scene_file_from_gui_submit"},
        {"name": "Frames", "value": "20-27"},
        {"name": "OutputFilePath", "value": "test_output_2"},
        {"name": "OutputFormat", "value": "JPEG"},
    ]
    assert sorted(settings.input_filenames) == ["test_filename_1", "test_filename_3"]
    assert sorted(settings.input_directories) == ["test_directory_2"]
    assert sorted(settings.output_directories) == ["test_directory_2", "test_directory_3"]
    assert sorted(settings.referenced_paths) == ["test_ref_path_2"]


def test_unsaved_changes_prompt(
    mock_lux_is_scene_changed, mock_lux_get_input_dialog, mock_lux_save_file
):
    mock_lux_is_scene_changed.return_value = True
    mock_lux_get_input_dialog.return_value = None  # emulate clicking Cancel
    with pytest.raises(Exception):
        submitter.main()
    mock_lux_save_file.assert_not_called()

    mock_lux_get_input_dialog.return_value = {}  # emulate clicking Ok
    # Raise an exception so the main() handler exits after the file save operation is called.
    # We want to verify that the saveFile call is made, but don't want to run the rest of the
    # submitter.
    mock_lux_save_file.side_effect = Exception()
    with pytest.raises(Exception):
        submitter.main()
    mock_lux_save_file.assert_called()


def test_auto_pause_resume(
    mock_lux_is_paused, mock_lux_pause, mock_lux_unpause, mock_lux_is_scene_changed
):
    # Throw an exception to cut the submitter short
    mock_lux_is_scene_changed.side_effect = Exception()

    mock_lux_is_paused.return_value = True
    with pytest.raises(Exception):
        submitter.main()
    mock_lux_pause.assert_not_called()
    mock_lux_unpause.assert_not_called()

    mock_lux_is_paused.return_value = False
    with pytest.raises(Exception):
        submitter.main()
    mock_lux_pause.assert_called()
    mock_lux_unpause.assert_called()


def test_error_if_export_dir_but_also_gui():
    with pytest.raises(RuntimeError):
        submitter.main(show_gui=True, export_dir="test_dir")


def test_save_ksp_bundle(mock_lux_save_package):
    test_dir = os.path.normpath("/testdir/test")
    bundle_name = "test_bundle.ksp"
    expected_bundle_path = os.path.normpath(f"{test_dir}/{bundle_name}")

    output = submitter.save_ksp_bundle(test_dir, bundle_name)

    assert output == expected_bundle_path
    mock_lux_save_package.assert_called_once_with(path=expected_bundle_path)


def test_get_ksp_bundle_files():

    TEST_SCENE_FILE = "test_scene_file.bip"
    TEST_ASSET_FILE = "test_asset.png"
    TEST_KSP_BUNDLE_NAME = "test_ksp_bundle"

    with tempfile.TemporaryDirectory() as temp_dir:
        to_zip_dir = os.path.join(temp_dir, "to_zip")
        os.mkdir(to_zip_dir)
        with open(os.path.join(to_zip_dir, TEST_SCENE_FILE), "w", encoding="utf-8") as file:
            file.write("test scene")
        with open(os.path.join(to_zip_dir, TEST_ASSET_FILE), "w", encoding="utf-8") as file:
            file.write("test asset")

        # Creating a zip archive as that's what is used to unpack a ksp and a ksp
        # can't be created easily outside of KeyShot
        shutil.make_archive(os.path.join(temp_dir, TEST_KSP_BUNDLE_NAME), "zip", to_zip_dir)

        with mock.patch.object(
            submitter,
            "save_ksp_bundle",
            return_value=os.path.join(temp_dir, f"{TEST_KSP_BUNDLE_NAME}.zip"),
        ) as mock_save_ksp_bundle:
            scene_file, input_filenames = submitter.get_ksp_bundle_files(temp_dir)

        assert scene_file == os.path.join(temp_dir, "unpack", TEST_SCENE_FILE)
        assert len(input_filenames) == 1
        assert input_filenames[0] == os.path.join(temp_dir, "unpack", TEST_ASSET_FILE)
        mock_save_ksp_bundle.assert_called_once_with(os.path.join(temp_dir, "ksp"), mock.ANY)


def test_construct_job_template_timeout_values():

    template = submitter.construct_job_template("test_scene.bip")

    actions = template["steps"][0]["stepEnvironments"][0]["script"]["actions"]

    assert actions["onEnter"]["timeout"] == submitter.KEYSHOT_ENVIRON_ENTER_TIMEOUT
    assert actions["onExit"]["timeout"] == submitter.KEYSHOT_ENVIRON_EXIT_TIMEOUT


def test_construct_job_template_includes_render_device_parameter():
    with mock.patch.object(submitter.lux, "getRenderEngine") as get_render_device_mock:
        submitter.lux.RENDER_ENGINE_PRODUCT_GPU = RENDER_ENGINE_PRODUCT_GPU
        submitter.lux.RENDER_ENGINE_INTERIOR_GPU = RENDER_ENGINE_INTERIOR_GPU

        get_render_device_mock.return_value = RENDER_ENGINE_PRODUCT
        template_cpu = submitter.construct_job_template("test_scene")

        get_render_device_mock.return_value = RENDER_ENGINE_PRODUCT_GPU
        template_gpu = submitter.construct_job_template("test_scene")

        render_device_param_cpu = next(
            (p for p in template_cpu["parameterDefinitions"] if p["name"] == "RenderDevice"), None
        )
        render_device_param_gpu = next(
            (p for p in template_gpu["parameterDefinitions"] if p["name"] == "RenderDevice"), None
        )

        assert render_device_param_cpu is not None
        assert render_device_param_cpu["default"] == "CPU"
        assert render_device_param_cpu["allowedValues"] == ["CPU", "GPU"]

        assert render_device_param_gpu is not None
        assert render_device_param_gpu["default"] == "GPU"
        assert render_device_param_gpu["allowedValues"] == ["CPU", "GPU"]


def test_substitute_suffix():
    assert submitter.substitute_suffix("scene.bip", ".json") == "scene.json"
    assert (
        submitter.substitute_suffix("/path/to/scene.bip", ".settings") == "/path/to/scene.settings"
    )
    assert submitter.substitute_suffix("scene", ".ext") == "scene.ext"


def test_get_current_render_device():
    with mock.patch.object(submitter.lux, "getRenderEngine") as get_render_engine_mock:
        submitter.lux.RENDER_ENGINE_PRODUCT_GPU = RENDER_ENGINE_PRODUCT_GPU
        submitter.lux.RENDER_ENGINE_INTERIOR_GPU = RENDER_ENGINE_INTERIOR_GPU

        get_render_engine_mock.return_value = RENDER_ENGINE_PRODUCT
        assert submitter.get_current_render_device() == "CPU"

        get_render_engine_mock.return_value = RENDER_ENGINE_PRODUCT_GPU
        assert submitter.get_current_render_device() == "GPU"

        get_render_engine_mock.return_value = RENDER_ENGINE_INTERIOR_GPU
        assert submitter.get_current_render_device() == "GPU"


def test_load_sticky_settings():
    with tempfile.TemporaryDirectory() as temp_dir:
        scene_file = os.path.join(temp_dir, "scene.bip")
        settings_file = os.path.join(temp_dir, "scene.deadline_render_settings.json")

        # Test non-existent file
        assert submitter.load_sticky_settings(scene_file) is None

        # Test valid settings file
        test_settings = {"parameterValues": [{"name": "Frames", "value": "1-10"}]}
        with open(settings_file, "w", encoding="utf8") as f:
            json.dump(test_settings, f)

        result = submitter.load_sticky_settings(scene_file)
        assert result == test_settings


def test_save_sticky_settings():
    settings = submitter.Settings(
        parameter_values=[{"name": "Frames", "value": "1-5"}],
        input_filenames=["test.png"],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        scene_file = os.path.join(temp_dir, "scene.bip")
        submitter.save_sticky_settings(scene_file, settings)

        settings_file = os.path.join(temp_dir, "scene.deadline_render_settings.json")
        assert os.path.exists(settings_file)

        with open(settings_file, "r", encoding="utf8") as f:
            saved_data = json.load(f)

        assert saved_data["parameterValues"] == [{"name": "Frames", "value": "1-5"}]
        assert saved_data["inputFilenames"] == ["test.png"]


def test_create_bundle_conda_parameters():
    settings = submitter.Settings(
        parameter_values=[],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    with tempfile.TemporaryDirectory() as bundle_dir:
        with mock.patch.object(submitter.lux, "getKeyShotDisplayVersion", return_value=(2024, 1)):
            submitter.create_bundle(
                settings,
                {"submission_mode": [1, "Only the scene BIP file"]},
                "scene.bip",
                "scene",
                bundle_dir,
            )

        # Check conda parameters were added
        conda_packages = next(
            (p for p in settings.parameter_values if p["name"] == "CondaPackages"), None
        )
        conda_channels = next(
            (p for p in settings.parameter_values if p["name"] == "CondaChannels"), None
        )

        assert conda_packages is not None
        assert conda_packages["value"] == "keyshot=2024.*"
        assert conda_channels is None


def test_create_bundle_gpu_requirements():
    settings = submitter.Settings(
        parameter_values=[
            {"name": "OverrideRenderDevice", "value": "True"},
            {"name": "RenderDevice", "value": "GPU"},
        ],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    with tempfile.TemporaryDirectory() as bundle_dir:
        with mock.patch.object(submitter.lux, "getKeyShotDisplayVersion", return_value=(2024, 1)):
            submitter.create_bundle(
                settings,
                {"submission_mode": [1, "Only the scene BIP file"]},
                "scene.bip",
                "scene",
                bundle_dir,
            )

        # Check job template has GPU requirements
        with open(os.path.join(bundle_dir, "template.json"), "r", encoding="utf-8") as f:
            template = json.load(f)

        amounts = template["steps"][0]["hostRequirements"].get("amounts", [])
        gpu_requirement = next((a for a in amounts if a["name"] == "amount.worker.gpu"), None)

        assert gpu_requirement is not None
        assert gpu_requirement["min"] == 1


def test_create_bundle_adaptor_scripts():
    settings = submitter.Settings(
        parameter_values=[],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    with tempfile.TemporaryDirectory() as bundle_dir:
        with mock.patch.object(submitter.lux, "getKeyShotDisplayVersion", return_value=(2024, 1)):
            submitter.create_bundle(
                settings,
                {"submission_mode": [1, "Only the scene BIP file"]},
                "scene.bip",
                "scene",
                bundle_dir,
            )

        # Check adaptor scripts were created
        scripts_dir = os.path.join(bundle_dir, "adaptor")
        assert os.path.exists(os.path.join(scripts_dir, "session_manager.py"))
        assert os.path.exists(os.path.join(scripts_dir, "keyshot_bridge.py"))
        assert os.path.exists(os.path.join(scripts_dir, "keyshot_command_handler.py"))
        assert os.path.exists(os.path.join(scripts_dir, "task_manager.py"))


def test_options_dialog_headless():
    result = submitter.options_dialog(show_gui=False)
    expected = {"submission_mode": [0, "The scene BIP file and all external files references"]}
    assert result == expected


def test_create_bundle_render_device_logic():
    # Test override disabled - should use current device
    settings = submitter.Settings(
        parameter_values=[{"name": "OverrideRenderDevice", "value": "False"}],
        input_filenames=[],
        auto_detected_input_filenames=[],
        input_directories=[],
        output_directories=[],
        referenced_paths=[],
    )

    with tempfile.TemporaryDirectory() as bundle_dir:
        with mock.patch.object(submitter.lux, "getKeyShotDisplayVersion", return_value=(2024, 1)):
            with mock.patch.object(submitter, "get_current_render_device", return_value="GPU"):
                submitter.create_bundle(
                    settings,
                    {"submission_mode": [1, "Only the scene BIP file"]},
                    "scene.bip",
                    "scene",
                    bundle_dir,
                )

        render_device = next(
            (p for p in settings.parameter_values if p["name"] == "RenderDevice"), None
        )
        assert render_device is not None
        assert render_device["value"] == "GPU"
