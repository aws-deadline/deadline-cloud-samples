#!/bin/bash
# Plugin Sync cleanup for Blender
# Unsets env vars set by the activate script. Downloaded files live under
# OPENJD_SESSION_WORKING_DIR which is cleaned up by the worker agent when
# the session ends, so we don't have to remove them ourselves.

unset BLENDER_USER_SCRIPTS
unset BLENDER_USER_CONFIG
