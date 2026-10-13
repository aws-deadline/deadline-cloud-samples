#!/bin/bash
# Unit tests for zzz-aftereffects-plugin-sync-activate.sh and
# zzz-aftereffects-plugin-sync-deactivate.sh.
# Uses AWS CLI and rm stubs, so no S3 access or After Effects installation is needed.
#
# Run: bash test_zzz_scripts.sh
# Every test prints PASS. Any FAIL indicates a bug.

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTIVATE_SCRIPT="$SCRIPT_DIR/zzz-aftereffects-plugin-sync-activate.sh"
DEACTIVATE_SCRIPT="$SCRIPT_DIR/zzz-aftereffects-plugin-sync-deactivate.sh"

PASS_COUNT=0
FAIL_COUNT=0

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    echo "PASS: $1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "FAIL: $1"
}

check() {
    # check <description> <command...>
    local description="$1"
    shift
    if "$@"; then
        pass "$description"
    else
        fail "$description"
    fi
}

setup() {
    TEST_DIR=$(mktemp -d)
    ORIGINAL_PATH="$PATH"
    mkdir -p "$TEST_DIR/bin" "$TEST_DIR/env/aftereffects/Plug-ins/Effects"
    # A plugin that ships with After Effects and must never be touched.
    touch "$TEST_DIR/env/aftereffects/Plug-ins/Effects/Builtin.aex"
    export PATH="$TEST_DIR/bin:$PATH"
    export AE_LOCATION="$TEST_DIR/env/aftereffects"
    export AE_PLUGIN_SYNC_VERSION=25.1
    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=TestPrefix
    PLUGIN_DIR="$AE_LOCATION/Plug-ins/deadline-plugin-sync"
}

teardown() {
    export PATH="$ORIGINAL_PATH"
    rm -rf "$TEST_DIR"
    unset DEADLINE_JA_S3_BUCKET DEADLINE_JA_ROOT_PREFIX AE_LOCATION AE_PLUGIN_SYNC_VERSION
    unset _AE_PLUGIN_SYNC_DIR PLUGIN_DIR
}

# The stub records every call in $TEST_DIR/aws_calls.log.
create_aws_stub_with_plugins() {
    cat > "$TEST_DIR/bin/aws" << STUBEOF
#!/bin/bash
echo "\$*" >> "$TEST_DIR/aws_calls.log"
if [ "\$1" = "s3" ] && [ "\$2" = "ls" ]; then
    exit 0
elif [ "\$1" = "s3" ] && [ "\$2" = "cp" ]; then
    DEST="\${4%/}"
    mkdir -p "\$DEST/VideoCopilot"
    touch "\$DEST/Saber.aex" "\$DEST/VideoCopilot/Orb.aex"
    exit 0
fi
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"
}

create_aws_stub_empty() {
    cat > "$TEST_DIR/bin/aws" << STUBEOF
#!/bin/bash
echo "\$*" >> "$TEST_DIR/aws_calls.log"
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"
}

create_aws_stub_failed_copy() {
    cat > "$TEST_DIR/bin/aws" << STUBEOF
#!/bin/bash
echo "\$*" >> "$TEST_DIR/aws_calls.log"
[ "\$2" = "ls" ] && exit 0
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"
}

test_skip_when_variable_missing() {
    local variable
    for variable in DEADLINE_JA_S3_BUCKET AE_PLUGIN_SYNC_VERSION AE_LOCATION; do
        setup
        create_aws_stub_with_plugins
        unset "$variable"
        local output
        output=$( (source "$ACTIVATE_SCRIPT") 2>&1 )
        check "Skip with success when $variable is not set" [ $? -eq 0 ]
        check "Skip message when $variable is not set" grep -q "Skipping" <<< "$output"
        check "No AWS calls when $variable is not set" [ ! -f "$TEST_DIR/aws_calls.log" ]
        teardown
    done
}

test_activate_installs_plugins() {
    setup
    create_aws_stub_with_plugins
    source "$ACTIVATE_SCRIPT" 2>/dev/null

    check "Activate copies a top-level plugin" [ -f "$PLUGIN_DIR/Saber.aex" ]
    check "Activate keeps plugin subdirectories" [ -f "$PLUGIN_DIR/VideoCopilot/Orb.aex" ]
    check "Activate records the plugin directory" [ "${_AE_PLUGIN_SYNC_DIR:-}" = "$PLUGIN_DIR" ]
    check "Activate preserves built-in plugins" [ -f "$AE_LOCATION/Plug-ins/Effects/Builtin.aex" ]
    check "Activate reads the version-specific prefix" \
        grep -q "s3 ls s3://test-bucket/TestPrefix/plugins/windows/aftereffects/25.1/" "$TEST_DIR/aws_calls.log"
    check "Activate skips the startup/ subfolder" \
        grep -q -- "--exclude startup/\*" "$TEST_DIR/aws_calls.log"
    teardown
}

test_activate_empty_prefix() {
    setup
    create_aws_stub_with_plugins
    export DEADLINE_JA_ROOT_PREFIX=""
    source "$ACTIVATE_SCRIPT" 2>/dev/null

    check "Empty root prefix builds the path without a leading slash" \
        grep -q "s3 ls s3://test-bucket/plugins/windows/aftereffects/25.1/" "$TEST_DIR/aws_calls.log"
    teardown
}

test_activate_no_plugins() {
    setup
    create_aws_stub_empty
    local output
    output=$(source "$ACTIVATE_SCRIPT" 2>&1; echo "dir=${_AE_PLUGIN_SYNC_DIR:-}")

    check "No plugin directory when the S3 prefix is empty" [ ! -d "$PLUGIN_DIR" ]
    check "No recorded directory when the S3 prefix is empty" grep -q "^dir=$" <<< "$output"
    check "Message when the S3 prefix is empty" grep -q "No After Effects plugins found" <<< "$output"
    teardown
}

test_activate_failed_copy() {
    setup
    create_aws_stub_failed_copy
    local output
    output=$( (source "$ACTIVATE_SCRIPT") 2>&1 )

    check "Failed download does not fail activation" [ $? -eq 0 ]
    check "Failed download prints a warning" grep -q "WARNING: Failed to download" <<< "$output"
    teardown
}

test_activate_replaces_stale_plugins() {
    setup
    create_aws_stub_with_plugins
    mkdir -p "$PLUGIN_DIR"
    touch "$PLUGIN_DIR/Stale.aex"
    source "$ACTIVATE_SCRIPT" 2>/dev/null

    check "Activate removes plugins from an earlier session" [ ! -f "$PLUGIN_DIR/Stale.aex" ]
    check "Activate installs the current plugins" [ -f "$PLUGIN_DIR/Saber.aex" ]
    teardown
}

test_activate_windows_style_location() {
    setup
    create_aws_stub_with_plugins
    # Convert the test path to backslashes, as Conda sets it on Windows workers.
    export AE_LOCATION="${AE_LOCATION//\//\\}"
    source "$ACTIVATE_SCRIPT" 2>/dev/null

    check "Activate accepts a backslash AE_LOCATION" [ -f "$PLUGIN_DIR/Saber.aex" ]
    teardown
}

test_deactivate_cleanup() {
    setup
    create_aws_stub_with_plugins
    source "$ACTIVATE_SCRIPT" 2>/dev/null
    # The After Effects variables hook unsets AE_LOCATION before this hook runs.
    unset AE_LOCATION
    source "$DEACTIVATE_SCRIPT" 2>/dev/null

    check "Deactivate removes the plugin directory" [ ! -d "$PLUGIN_DIR" ]
    check "Deactivate preserves built-in plugins" [ -f "$TEST_DIR/env/aftereffects/Plug-ins/Effects/Builtin.aex" ]
    check "Deactivate unsets the recorded directory" [ -z "${_AE_PLUGIN_SYNC_DIR+x}" ]
    teardown
}

test_deactivate_without_activate() {
    setup
    local output
    output=$( (source "$DEACTIVATE_SCRIPT") 2>&1 )

    check "Deactivate succeeds when nothing was installed" [ $? -eq 0 ]
    check "Deactivate prints nothing when nothing was installed" [ -z "$output" ]
    teardown
}

test_deactivate_ignores_unowned_directory() {
    setup
    export _AE_PLUGIN_SYNC_DIR="$AE_LOCATION/Plug-ins/Effects"
    source "$DEACTIVATE_SCRIPT" 2>/dev/null

    check "Deactivate never removes a directory it does not own" [ -f "$AE_LOCATION/Plug-ins/Effects/Builtin.aex" ]
    teardown
}

test_deactivate_locked_plugin() {
    setup
    create_aws_stub_with_plugins
    source "$ACTIVATE_SCRIPT" 2>/dev/null
    # Simulate a plugin file that another process still has open.
    cat > "$TEST_DIR/bin/rm" << 'STUBEOF'
#!/bin/bash
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/rm"
    # Forget the cached location of the real rm so the stub is found.
    hash -r
    local output
    output=$( (source "$DEACTIVATE_SCRIPT") 2>&1 )

    check "Deactivate succeeds when a plugin is locked" [ $? -eq 0 ]
    check "Deactivate warns when a plugin is locked" grep -q "WARNING: Could not fully remove" <<< "$output"
    # teardown restores PATH, so its rm is the real one.
    teardown
    hash -r
}

echo "Running After Effects Plugin Sync tests..."
echo ""
test_skip_when_variable_missing
test_activate_installs_plugins
test_activate_empty_prefix
test_activate_no_plugins
test_activate_failed_copy
test_activate_replaces_stale_plugins
test_activate_windows_style_location
test_deactivate_cleanup
test_deactivate_without_activate
test_deactivate_ignores_unowned_directory
test_deactivate_locked_plugin

echo ""
echo "Results: $PASS_COUNT passed, $FAIL_COUNT failed"
[ "$FAIL_COUNT" -eq 0 ]
