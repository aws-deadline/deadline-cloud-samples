#!/bin/sh
set -xeuo pipefail

# Copy the VRED installation into the prefix
INSTALL_DIR="$PREFIX/opt/Autodesk/VRED_2025"
mkdir -p $INSTALL_DIR
find $SRC_DIR/installer
chmod +x $SRC_DIR/installer/VREDCore-2025.sh
$SRC_DIR/installer/VREDCore-2025.sh --target $INSTALL_DIR

# Install dependencies not available on Deadline Cloud service-managed fleets
# from the system package manager, dnf.
mkdir -p "$SRC_DIR/download"
cd "$SRC_DIR/download"
dnf download --resolve -y xorg-x11-server-Xorg xorg-x11-server-common \
    libX11-xcb pixman libXfont2 libepoxy cairo xkbcomp libunwind libgudev \
    freetype fontconfig harfbuzz libbrotli graphite2 libfontenc \
    xcb-util-cursor libXfixes libXdmcp libxkbfile

# Extract and install dependencies
for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Copy and patch shared libraries
for SO_FILE in $(find usr/lib64 -type f,l); do
    DEST_FILE="$INSTALL_DIR/lib/$(basename $SO_FILE)"
    cp --preserve=links $SO_FILE $DEST_FILE
    if file $DEST_FILE | grep -q ELF; then
        patchelf --add-rpath '$ORIGIN/.' $DEST_FILE
    fi
done

# Copy binaries to the installation
mkdir -p $INSTALL_DIR/usr/bin
for BINARY in $(find usr/bin -type f); do
    cp --preserve=links $BINARY $INSTALL_DIR/$BINARY
    if file $BINARY | grep -q ELF; then
        patchelf --add-rpath '$ORIGIN/../../lib' $INSTALL_DIR/$BINARY
    fi
done

# Change the location of Xorg.wrap and Xorg
LIBEXEC_DIR="$INSTALL_DIR/usr/libexec"

cat <<EOF > $INSTALL_DIR/usr/bin/Xorg
#!/usr/bin/sh
#
# Execute Xorg.wrap if it exists otherwise execute Xorg directly.
# This allows distros to put the suid wrapper in a separate package.

if [ -x "$LIBEXEC_DIR"/Xorg.wrap ]; then
    exec "$LIBEXEC_DIR"/Xorg.wrap "\$@"
else
    exec "$LIBEXEC_DIR"/Xorg "\$@"
fi
EOF
chmod +x $INSTALL_DIR/usr/bin/Xorg

# Copy stuff in $SRC_DIR/download/usr/libexec to the installation
mkdir -p $INSTALL_DIR/usr/libexec
for LIBEXEC in $(find usr/libexec -type f); do
    DEST_DIR="$INSTALL_DIR/$(dirname $LIBEXEC)"
    mkdir -p $DEST_DIR
    cp --preserve=links $LIBEXEC "$DEST_DIR/$(basename $LIBEXEC)"
    if file $LIBEXEC | grep -q ELF; then
        patchelf --add-rpath '$ORIGIN/../../lib' $INSTALL_DIR/$LIBEXEC
    fi
done

# Handle Python-specific libraries
for PYSO in "$INSTALL_DIR"/lib/python*/site-packages/*/*.so \
           "$INSTALL_DIR"/lib/python*/lib-dynload/*.so; do
    if file $PYSO | grep -q ELF; then
        patchelf --add-rpath '$ORIGIN/../..' $PYSO
    fi
done

# Xorg tries to call /usr/lib/xkbcomp. This switches that to just call xkbcmp, a symlink to the original
python <<EOF
with open("$INSTALL_DIR/usr/libexec/Xorg", "rb+") as fh:
    data = fh.read()

    old_path = b'"%s%sxkbcomp"'
    new_path = "A=%s%s xkbcmp".encode()
    if len(new_path) <= len(old_path):
        new_path = new_path.ljust(len(old_path), b'\0')
        data = data.replace(old_path, new_path)
    else:
        raise RuntimeError(
            "Cannot patch Xorg binary: New path is longer than original path: manual binary patch required!"
        )
    fh.seek(0)
    fh.write(data)
EOF

# Patches Xorg.wrap binary to redirect hardcoded paths to usr/libexec.
# - /usr/libexec -> usr/libexec (for executable lookup)
# - /etc/X11/Xwrapper.config -> usr/libexec/Xwrap.cfg (for config)
# These modifications allow Xorg to work with files in conda-managed locations 
# via symlinks that will be created to usr/libexec.
python <<EOF
with open("$INSTALL_DIR/usr/libexec/Xorg.wrap", "rb+") as fh:
    data = fh.read()

    old_path = b"/usr/libexec"
    new_path = "usr/libexec".encode()
    if len(new_path) <= len(old_path):
        new_path = new_path.ljust(len(old_path), b'\0')
        data = data.replace(old_path, new_path)
    else:
        raise RuntimeError(
            "Cannot patch Xorg.wrap binary: New path is longer than original path: manual binary patch required!"
        )

    old_config_path = b"/etc/X11/Xwrapper.config"
    new_config_path = "usr/libexec/Xwrap.cfg".encode()
    if len(new_config_path) <= len(old_config_path):
        new_config_path = new_config_path.ljust(len(old_config_path), b'\0')
        data = data.replace(old_config_path, new_config_path)
    else:
        raise RuntimeError(
            "Cannot patch Xorg.wrap binary: New path is longer than original path: manual binary patch required!"
        )

    fh.seek(0)
    fh.write(data)
EOF


# Create X server startup script
mkdir -p $INSTALL_DIR/bin
cat <<EOF > $INSTALL_DIR/bin/start-xserver
#!/bin/bash
set -xeuo pipefail

export DISPLAY=:0

# Create X configuration directory in the package
mkdir -p $INSTALL_DIR/etc/X11

# Generate etc/X11/xorg.conf
/usr/bin/nvidia-xconfig -a \
    --allow-empty-initial-configuration \
    --no-connected-monitor \
    --output-xconfig $INSTALL_DIR/etc/X11/xorg.conf

# Edit "Files" section
sed -i "/^Section \"Files\"/a\\
    ModulePath \"/usr/lib64/xorg/modules\"\\
    ModulePath \"$PREFIX/opt/Autodesk/VRED_2025/lib\"" $INSTALL_DIR/etc/X11/xorg.conf

# Create symbolic link
ln -sf $INSTALL_DIR/usr/bin/xkbcomp $INSTALL_DIR/usr/bin/xkbcmp

# Create a Xorg wrapper config file
if [ -f  $INSTALL_DIR/usr/libexec/Xwrap.cfg ]; then
  echo "Xwrapper Config file already exists"
else
  echo "Creating a new Xwrapper Config"
  mkdir -p $INSTALL_DIR/usr/libexec
  cat << EOF2 > $INSTALL_DIR/usr/libexec/Xwrap.cfg
needs_root_rights=no
allowed_users=anybody
EOF2
  echo "New Xwrapper conf file created at $INSTALL_DIR/usr/libexec/Xwrap.cfg"
  cat $INSTALL_DIR/usr/libexec/Xwrap.cfg
fi

mkdir -p $INSTALL_DIR/var/run
# Go to $INSTALL_DIR just for launching X Server
pushd $INSTALL_DIR

# Start X Server
$INSTALL_DIR/usr/bin/Xorg -keeptty -sharevts -novtswitch -ignoreABI -nolisten tcp -config $INSTALL_DIR/etc/X11/xorg.conf &
sleep 3

# Write Xorg PID to a file
echo \$! > "$INSTALL_DIR/var/run/xorg.pid"

# Go back to the original location
popd
EOF

chmod +x $INSTALL_DIR/bin/start-xserver

# Create VRED wrapper scripts
mkdir -p $PREFIX/bin
cat <<EOF > $PREFIX/bin/VREDCore
#!/bin/bash
PATH="$INSTALL_DIR/usr/bin:$INSTALL_DIR/usr/libexec:\$PATH"

# If Xorg is not running, run the X server startup script
if ! pgrep -x Xorg > /dev/null; then
    $INSTALL_DIR/bin/start-xserver
fi
export DISPLAY=:0

"$INSTALL_DIR/bin/VREDCore" "\$@"
EOF
chmod +x $PREFIX/bin/VREDCore


# Setup environment variables for activation
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export VREDCORE=\$CONDA_PREFIX/bin/VREDCore
EOF

# Setup environment variables for deactivation
mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
#!/bin/bash

unset VREDCORE

# Kill Xorg server if it's running
if [ -f "$INSTALL_DIR/var/run/xorg.pid" ]; then
    XORG_PID=\$(cat "$INSTALL_DIR/var/run/xorg.pid")
    if ps -p \$XORG_PID > /dev/null; then
        kill \$XORG_PID
        # Wait for X server to completely shut down
        sleep 2
    fi
fi
EOF
