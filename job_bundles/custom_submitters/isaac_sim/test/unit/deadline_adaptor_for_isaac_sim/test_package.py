# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import deadline.isaac_sim_adaptor


def test_package_imports() -> None:
    assert deadline.isaac_sim_adaptor.__name__ == "deadline.isaac_sim_adaptor"
