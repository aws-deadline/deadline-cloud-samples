#!/bin/bash
# Unit tests for zzz-blender-plugins-activate.sh and zzz-blender-plugins-deactivate.sh
# Uses an AWS CLI stub to test without real S3 access.
#
# Run: bash test_zzz_scripts.sh
# All tests should print PASS. Any FAIL indicates a bug.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTIVATE_SCRIPT="$SCRIPT_DIR/zzz-blender-plugin-sync-activate.sh"
DEACTIVATE_SCRIPT="$SCRIPT_DIR/zzz-blender-plugin-sync-deactivate.sh"

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

# Create a temp directory for each test
setup() {
    TEST_DIR=$(mktemp -d)
    export OPENJD_SESSION_WORKING_DIR="$TEST_DIR"
    # Create a fake aws CLI that simulates S3 operations
    mkdir -p "$TEST_DIR/bin"
    export PATH="$TEST_DIR/bin:$PATH"
}

teardown() {
    rm -rf "$TEST_DIR"
    unset DEADLINE_JA_S3_BUCKET DEADLINE_JA_ROOT_PREFIX OPENJD_SESSION_WORKING_DIR
    unset BLENDER_VERSION BLENDER_USER_SCRIPTS _SP_PLUGIN_DIR
}

# --- AWS CLI Stub ---
create_aws_stub_with_plugins() {
    # Stub that simulates: s3 ls succeeds, s3 cp creates fake plugin files
    cat > "$TEST_DIR/bin/aws" << 'STUBEOF'
#!/bin/bash
if [ "$1" = "s3" ] && [ "$2" = "ls" ]; then
    exit 0
elif [ "$1" = "s3" ] && [ "$2" = "cp" ]; then
    # $3 is source (s3://...), $4 is destination path
    DEST="$4"
    DEST="${DEST%/}"
    mkdir -p "$DEST/test_addon"
    cat > "$DEST/test_addon/__init__.py" << 'PYEOF'
bl_info = {"name": "Test", "blender": (3, 6, 0), "category": "Testing"}
def register(): pass
def unregister(): pass
PYEOF
    exit 0
fi
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"
}

create_aws_stub_empty() {
    # Stub that simulates: s3 ls fails (no plugins)
    cat > "$TEST_DIR/bin/aws" << 'STUBEOF'
#!/bin/bash
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"
}

# ============================================================
# TEST 1: Silent skip when DEADLINE_JA_S3_BUCKET is not set
# ============================================================
test_skip_no_bucket() {
    setup
    export BLENDER_VERSION=5.1
    # Do NOT set DEADLINE_JA_S3_BUCKET

    (source "$ACTIVATE_SCRIPT") 2>/dev/null
    if [ $? -eq 0 ]; then
        pass "Silent skip when DEADLINE_JA_S3_BUCKET not set"
    else
        fail "Silent skip when DEADLINE_JA_S3_BUCKET not set"
    fi
    teardown
}

# ============================================================
# TEST 2: Silent skip when BLENDER_VERSION is not set
# ============================================================
test_skip_no_version() {
    setup
    export DEADLINE_JA_S3_BUCKET=test-bucket
    # Do NOT set BLENDER_VERSION

    (source "$ACTIVATE_SCRIPT") 2>/dev/null
    if [ $? -eq 0 ]; then
        pass "Silent skip when BLENDER_VERSION not set"
    else
        fail "Silent skip when BLENDER_VERSION not set"
    fi
    teardown
}

# ============================================================
# TEST 3: Activate downloads plugins and sets BLENDER_USER_SCRIPTS
# ============================================================
test_activate_with_plugins() {
    setup
    create_aws_stub_with_plugins
    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=TestPrefix
    export BLENDER_VERSION=5.1

    source "$ACTIVATE_SCRIPT" > /dev/null 2>&1 || true

    if [ -n "${BLENDER_USER_SCRIPTS:-}" ]; then
        pass "Activate sets BLENDER_USER_SCRIPTS"
    else
        fail "Activate sets BLENDER_USER_SCRIPTS (got empty)"
    fi

    if [ -d "${BLENDER_USER_SCRIPTS:-}/addons/test_addon" ]; then
        pass "Activate moves addon into addons/ directory"
    else
        fail "Activate moves addon into addons/ directory"
    fi

    if [ -f "${BLENDER_USER_SCRIPTS:-}/addons/test_addon/__init__.py" ]; then
        pass "Addon __init__.py exists in addons/"
    else
        fail "Addon __init__.py exists in addons/"
    fi

    if [ -f "${BLENDER_USER_SCRIPTS:-}/startup/plugin_sync_auto_enable.py" ]; then
        pass "Auto-enable startup script generated"
    else
        fail "Auto-enable startup script generated"
    fi

    if grep -q "test_addon" "${BLENDER_USER_SCRIPTS:-}/startup/plugin_sync_auto_enable.py" 2>/dev/null; then
        pass "Auto-enable script contains addon name"
    else
        fail "Auto-enable script contains addon name"
    fi

    teardown
}

# ============================================================
# TEST 4: Activate with empty S3 prefix (no plugins)
# ============================================================
test_activate_empty_s3() {
    setup
    create_aws_stub_empty
    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=TestPrefix
    export BLENDER_VERSION=5.1

    source "$ACTIVATE_SCRIPT" > /dev/null 2>&1

    if [ -z "${BLENDER_USER_SCRIPTS:-}" ]; then
        pass "No BLENDER_USER_SCRIPTS when S3 is empty"
    else
        fail "No BLENDER_USER_SCRIPTS when S3 is empty (got: $BLENDER_USER_SCRIPTS)"
    fi
    teardown
}

# ============================================================
# TEST 5: Activate with empty DEADLINE_JA_ROOT_PREFIX
# ============================================================
test_activate_empty_prefix() {
    setup
    create_aws_stub_with_plugins
    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=""
    export BLENDER_VERSION=5.1

    source "$ACTIVATE_SCRIPT" > /dev/null 2>&1 || true

    if [ -n "${BLENDER_USER_SCRIPTS:-}" ]; then
        pass "Activate works with empty root prefix"
    else
        fail "Activate works with empty root prefix"
    fi
    teardown
}

# ============================================================
# TEST 6: Deactivate cleans up plugin directory
# ============================================================
test_deactivate_cleanup() {
    setup
    export OPENJD_SESSION_WORKING_DIR="$TEST_DIR"
    local plugin_dir="$TEST_DIR/deadline-plugins/blender"
    mkdir -p "$plugin_dir/addons/test_addon"
    touch "$plugin_dir/addons/test_addon/__init__.py"
    export _SP_PLUGIN_DIR="$plugin_dir"
    export BLENDER_USER_SCRIPTS="$plugin_dir"

    source "$DEACTIVATE_SCRIPT" > /dev/null 2>&1

    if [ ! -d "$plugin_dir" ]; then
        pass "Deactivate removes plugin directory"
    else
        fail "Deactivate removes plugin directory"
    fi
    teardown
}

# ============================================================
# TEST 7: Deactivate unsets BLENDER_USER_SCRIPTS
# ============================================================
test_deactivate_unsets_env() {
    setup
    export OPENJD_SESSION_WORKING_DIR="$TEST_DIR"
    local plugin_dir="$TEST_DIR/deadline-plugins/blender"
    mkdir -p "$plugin_dir"
    export _SP_PLUGIN_DIR="$plugin_dir"
    export BLENDER_USER_SCRIPTS="$plugin_dir"

    source "$DEACTIVATE_SCRIPT" > /dev/null 2>&1

    if [ -z "${BLENDER_USER_SCRIPTS:-}" ]; then
        pass "Deactivate unsets BLENDER_USER_SCRIPTS"
    else
        fail "Deactivate unsets BLENDER_USER_SCRIPTS (got: $BLENDER_USER_SCRIPTS)"
    fi
    teardown
}

# ============================================================
# TEST 8: Deactivate is safe when _SP_PLUGIN_DIR is not set
# ============================================================
test_deactivate_safe_when_unset() {
    setup
    # Don't set _SP_PLUGIN_DIR or BLENDER_USER_SCRIPTS

    source "$DEACTIVATE_SCRIPT" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        pass "Deactivate safe when _SP_PLUGIN_DIR not set"
    else
        fail "Deactivate safe when _SP_PLUGIN_DIR not set"
    fi
    teardown
}

# ============================================================
# TEST 9: Activate preserves BLENDER_VERSION
# ============================================================
test_activate_preserves_blender_version() {
    setup
    create_aws_stub_with_plugins
    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=TestPrefix
    export BLENDER_VERSION=5.1

    source "$ACTIVATE_SCRIPT" > /dev/null 2>&1

    if [ "$BLENDER_VERSION" = "5.1" ]; then
        pass "Activate preserves BLENDER_VERSION"
    else
        fail "Activate preserves BLENDER_VERSION (got: $BLENDER_VERSION)"
    fi
    teardown
}

# ============================================================
# TEST 10: Activate handles single .py file addon
# ============================================================
test_activate_single_py_addon() {
    setup
    # Custom stub that creates a single .py file instead of a directory
    cat > "$TEST_DIR/bin/aws" << 'STUBEOF'
#!/bin/bash
if [ "$1" = "s3" ] && [ "$2" = "ls" ]; then
    exit 0
elif [ "$1" = "s3" ] && [ "$2" = "cp" ]; then
    DEST="$4"
    DEST="${DEST%/}"
    mkdir -p "$DEST"
    cat > "$DEST/my_addon.py" << 'PYEOF'
bl_info = {"name": "My Addon", "blender": (3, 6, 0), "category": "Testing"}
def register(): pass
def unregister(): pass
PYEOF
    exit 0
fi
exit 1
STUBEOF
    chmod +x "$TEST_DIR/bin/aws"

    export DEADLINE_JA_S3_BUCKET=test-bucket
    export DEADLINE_JA_ROOT_PREFIX=TestPrefix
    export BLENDER_VERSION=5.1

    source "$ACTIVATE_SCRIPT" > /dev/null 2>&1 || true

    if [ -f "${BLENDER_USER_SCRIPTS:-}/addons/my_addon.py" ] 2>/dev/null; then
        pass "Single .py addon moved to addons/"
    else
        fail "Single .py addon moved to addons/"
    fi
    teardown
}

# ============================================================
# Run all tests
# ============================================================
echo "=== Running plugin sync unit tests ==="
echo

test_skip_no_bucket
test_skip_no_version
test_activate_with_plugins
test_activate_empty_s3
test_activate_empty_prefix
test_deactivate_cleanup
test_deactivate_unsets_env
test_deactivate_safe_when_unset
test_activate_preserves_blender_version
test_activate_single_py_addon

echo
echo "=== Results: $PASS_COUNT passed, $FAIL_COUNT failed ==="
if [ $FAIL_COUNT -gt 0 ]; then
    exit 1
fi
