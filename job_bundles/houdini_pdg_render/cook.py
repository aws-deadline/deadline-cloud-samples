# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Cook the reef chase scene on your Deadline Cloud farm without opening Houdini.

Run it with Houdini's Python:  hython cook.py
It submits to your default farm and queue, and waits until the cook ends.
"""
import os
import sys

import hou
import pdg

SCENE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reef_chase.hip")
# The last node in the TOP network. Cooking it cooks every node above it.
OUTPUT_NODE = "/obj/topnet1/make_video"

hou.hipFile.load(SCENE, suppress_save_prompt=True, ignore_load_warnings=True)
output_node = hou.node(OUTPUT_NODE)
topnet = output_node.parent()
scheduler = hou.node(topnet.path() + "/" + topnet.parm("topscheduler").eval())

print("Cooking the scene on your default farm and queue. This prints nothing more until the")
print("cook ends, so watch the job's progress in Deadline Cloud monitor.", flush=True)

# This is what the Cook button does. It returns once the cook has ended.
try:
    output_node.cookWorkItems(block=True)
except hou.OperationFailed:
    pass

# The scheduler reports a refused cook on its node, once PDG's events are processed.
context = output_node.getPDGGraphContext()
context.waitAllEvents()
for message in scheduler.errors():
    print("Scheduler error: " + message)
    if "Unknown PDG scheduler type" in message:
        print("Turn on the Deadline Cloud Scheduler as the README describes, then run this again.")

items = [item for node in context.graph.nodes() for item in node.workItems]
failed = [item.name for item in items if item.state != pdg.workItemState.CookedSuccess]
if not items or failed or scheduler.errors():
    if failed:
        print(f"{len(failed)} of {len(items)} work items didn't succeed, starting with {failed[0]}.")
    print("The cook didn't finish. See the README's Troubleshooting section.")
    sys.exit(1)
print("The cook finished, and every work item succeeded.")
