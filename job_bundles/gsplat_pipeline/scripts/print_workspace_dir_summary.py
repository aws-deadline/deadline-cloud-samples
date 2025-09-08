import argparse
import os
import re
import sys

def split_numbered_filename(filename):
    """
    Checks if a filename follows a numbered file pattern, to enable summarizing these.
    If so, returns (pattern, (filename, index))
    Otherwise returns (filename, None)
    """
    m = re.match(r"(^.*\D)(\d+)\.(.+)$", filename)
    if m:
        return f"{m.group(1)}#.{m.group(3)}", (filename, int(m.group(2)))
    else:
        return filename, None


def int_set_to_range_expr(int_values):
    """
    Converts a set of integers into a range expression.
    For example, {1,2,3,4,5,7,8,9,10} -> "1-5,7-10"
    """
    int_list = sorted(set(int_values))
    range_expr_components = []
    last_interval_start = last_interval_end = int_list[0]

    def add_interval(start, end):
        if start == last_interval_end:
            range_expr_components.append(str(start))
        else:
            range_expr_components.append(f"{start}-{end}")

    for value in int_list[1:]:
        if value == last_interval_end + 1:
            last_interval_end = value
        else:
            add_interval(last_interval_start, last_interval_end)
            last_interval_start = last_interval_end = value
    add_interval(last_interval_start, last_interval_end)
    return ",".join(range_expr_components)



def summarize_workspace_dir(workspace_dir):
    """
    Prints a summary of all the files in a workspace directory,
    grouping numbered filenames by their pattern.

    Example output:

      Summary of workspace directory .
       images/InputVideoName_#.jpg
          With 99 indexes: 1-99
       images/frame_#.jpg
          With 99 indexes: 1-99
       images_2/frame_#.jpg
          With 99 indexes: 1-99
       images_4/frame_#.jpg
          With 99 indexes: 1-99
       images_8/frame_#.jpg
          With 99 indexes: 1-99
       nerfstudio_workspace/splatfacto/2025-03-18_001317/config.yml
       nerfstudio_workspace/splatfacto/2025-03-18_001317/dataparser_transforms.json
       nerfstudio_workspace/splatfacto/2025-03-18_001317/nerfstudio_models/step-000009999.ckpt
       sfm_workspace/database.db
       sfm_workspace/sparse/0/cameras.bin
       sfm_workspace/sparse/0/images.bin
       sfm_workspace/sparse/0/points3D.bin
       source_images/InputVideoName_#.jpg
          With 99 indexes: 1-99
       sparse/cameras.bin
       sparse/images.bin
       sparse/points3D.bin
       sparse_pc.ply
       transforms.json
    """
    # Walk the entire tree to get all the filenames, and group them by pattern
    combined_patterns = {}
    for root, dirs, files in os.walk(workspace_dir):
        for filename in files:
            pattern, info = split_numbered_filename(os.path.normpath(os.path.join(workspace_dir, root, filename)))
            if info:
                combined_patterns[pattern] = combined_patterns.get(pattern, []) + [info]
            else:
                combined_patterns[pattern] = None

    print()
    print(f"Summary of workspace directory {workspace_dir}")
    for pattern, info_list in sorted(combined_patterns.items()):
        if info_list is None:
            # Not a numbered filename
            print(f" {pattern}")
        elif len(info_list) == 1:
            # A numbered filename, but nothing to summarize
            print(f" {info_list[0][0]}")
        else:
            # A set of numbered filenames, summarize as the pattern and a range expression
            print(f" {pattern}")
            print(f"    With {len(info_list)} indexes: {int_set_to_range_expr(index for _, index in info_list)}")
    print()


def main(args_list):
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace_dir", help="The workspace directory to summarize.")
    args = parser.parse_args(args_list)

    summarize_workspace_dir(args.workspace_dir)


if __name__ == "__main__":
    main(sys.argv[1:])