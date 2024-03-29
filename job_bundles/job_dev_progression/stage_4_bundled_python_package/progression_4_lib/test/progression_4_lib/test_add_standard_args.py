import argparse
from progression_4_lib.standard_args import add_standard_args


def test_add_standard_args():
    """An example test to illustrate the pattern."""
    parser = argparse.ArgumentParser(prog="initialize.py")
    add_standard_args(parser)

    args = parser.parse_args(["--debug"])
    assert bool(args.debug) is True

    args = parser.parse_args([])
    assert bool(args.debug) is False
