"""
This is some sample shared library code use by the entrypoint commands.
"""


def add_standard_args(parser):
    """Add standard options to the argparse parser."""
    parser.add_argument(
        "--debug",
        action="store_true",
    )


def process_standard_args(args):
    if args.debug:
        print("Debug mode is enabled")
