# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import re

import deadline.isaac_sim_submitter as sub


def test_package_imports() -> None:
    assert sub.__name__ == "deadline.isaac_sim_submitter"


def test_ships_the_kit_extension() -> None:
    ext = sub.extension_path()
    assert ext.name == sub.EXTENSION_NAME and ext.parent == sub.extension_folder()
    text = (ext / "config" / "extension.toml").read_text(encoding="utf-8")
    # Source keeps the placeholder; the wheel build stamps the package version.
    package = text.split("[package]", 1)[1].split("\n[", 1)[0]
    assert re.search(r'^version = "0\.0\.0"$', package, re.MULTILINE)
    assert f'[[python.module]]\nname = "{sub.EXTENSION_NAME}"' in text
    assert (ext / "isaacsim" / "deadline" / "submitter" / "__init__.py").is_file()


def test_extension_is_not_an_importable_top_level_package() -> None:
    """The folder name has dots, so the extension never shadows Isaac Sim's isaacsim."""
    assert "." in sub.EXTENSION_NAME
    assert not (sub.extension_folder() / "__init__.py").exists()
