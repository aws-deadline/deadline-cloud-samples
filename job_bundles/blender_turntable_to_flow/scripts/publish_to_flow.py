"""Publish a turntable render to Autodesk Flow Production Tracking (ShotGrid).

Reads script credentials from AWS Secrets Manager, finds-or-creates the Asset
and its review Task, creates a Version, uploads the movie and the thumbnail,
links the movie path, and advances the Task status.

Run by the PublishToFlow step.
"""
import argparse
import json
import os

import boto3
import shotgun_api3


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--secret-arn", required=True)
    p.add_argument("--project-id", type=int, required=True)
    p.add_argument("--asset-name", required=True)
    p.add_argument("--asset-type", required=True)
    p.add_argument("--step-short-name", required=True)
    p.add_argument("--task-name", required=True)
    p.add_argument("--task-status", required=True)
    p.add_argument("--movie", required=True)
    p.add_argument("--thumbnail", required=True)
    args = p.parse_args()

    # Region: the secret ARN carries it; fall back to the worker's region.
    region = args.secret_arn.split(":")[3] if args.secret_arn.count(":") >= 4 else None
    sm = boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")
    secret = json.loads(sm.get_secret_value(SecretId=args.secret_arn)["SecretString"])

    sg = shotgun_api3.Shotgun(
        secret["site_url"],
        script_name=secret["script_name"],
        api_key=secret["api_key"],
    )
    print(f"Connected to Flow {sg.info().get('version')}")

    project = {"type": "Project", "id": args.project_id}

    # Find-or-create the Asset.
    asset = sg.find_one("Asset", [["project", "is", project], ["code", "is", args.asset_name]], ["code"])
    if not asset:
        asset = sg.create("Asset", {
            "project": project,
            "code": args.asset_name,
            "sg_asset_type": args.asset_type,
            "description": "Created by the deadline-cloud-samples Flow turntable demo.",
        })
        print(f"Created Asset {asset['id']}")
    else:
        print(f"Found Asset {asset['id']}")

    # Find-or-create the review Task on the Asset.
    task = sg.find_one("Task", [
        ["project", "is", project],
        ["entity", "is", asset],
        ["content", "is", args.task_name],
    ], ["content"])
    if not task:
        create = {"project": project, "entity": asset, "content": args.task_name}
        step = sg.find_one("Step", [["entity_type", "is", "Asset"], ["short_name", "is", args.step_short_name]], ["code"])
        if step:
            create["step"] = step
        task = sg.create("Task", create)
        print(f"Created Task {task['id']}")
    else:
        print(f"Found Task {task['id']}")

    # Create the Version (the hero reviewable record).
    version = sg.create("Version", {
        "project": project,
        "code": f"{args.asset_name} turntable",
        "description": "Turntable published by the deadline-cloud-samples demo job.",
        "entity": asset,
        "sg_task": {"type": "Task", "id": task["id"]},
        "sg_path_to_movie": os.path.abspath(args.movie),
        "sg_path_to_frames": os.path.dirname(os.path.abspath(args.movie)),
    })
    print(f"Created Version {version['id']}")

    # Upload the movie -> populates sg_uploaded_movie (the review player source).
    sg.upload("Version", version["id"], args.movie, field_name="sg_uploaded_movie")
    print("Uploaded movie to sg_uploaded_movie")

    # Upload the thumbnail -> populates the Version's image field (review grid).
    sg.upload_thumbnail("Version", version["id"], args.thumbnail)
    print("Uploaded thumbnail to Version image")

    # Advance the Task status.
    sg.update("Task", task["id"], {"sg_status_list": args.task_status})
    print(f"Advanced Task {task['id']} status -> {args.task_status}")

    site = secret["site_url"].rstrip("/")
    print(f"Version: {site}/detail/Version/{version['id']}")


if __name__ == "__main__":
    main()
