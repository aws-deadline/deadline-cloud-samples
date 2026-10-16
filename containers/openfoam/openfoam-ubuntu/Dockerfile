# OpenFOAM (openfoam.com release) on Ubuntu 24.04, installed from the official apt repository.
#   docker build --platform linux/amd64 --tag openfoam-ubuntu:2512 .

FROM ubuntu:24.04

SHELL ["/bin/bash", "-c"]

# The openfoam.com release number, as it appears in openfoam<VERSION>-default.
ARG OPENFOAM_VERSION=2512
# The apt suite must match the base image's release codename.
ARG APT_SUITE=noble

# dl.openfoam.com redirects to random SourceForge mirrors. Short timeouts make a dead mirror fail fast.
RUN printf '%s\n' \
        'Acquire::Retries "3";' \
        'Acquire::http::Timeout "20";' \
        'Acquire::https::Timeout "20";' \
    > /etc/apt/apt.conf.d/99-openfoam-mirror-retries

# The two steps of the upstream add-debian-repo.sh, spelled out instead of piping a remote script to bash.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://dl.openfoam.com/pubkey.gpg \
        | gpg --dearmor -o /usr/share/keyrings/openfoam.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/openfoam.gpg]" \
            "https://dl.openfoam.com/repos/deb ${APT_SUITE} main" \
        > /etc/apt/sources.list.d/openfoam.list \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# A SourceForge mirror can stall apt indefinitely, so each attempt is timed out and retried on a new mirror.
# apt-get update empties the download cache in this base image, so it only runs until the index arrives.
# hostname and bc are called by OpenFOAM's shell tooling but missing from the minimal base image.
RUN pkg="openfoam${OPENFOAM_VERSION}-default" \
    && for attempt in 1 2 3 4 5 6; do \
        apt-cache show "$pkg" > /dev/null 2>&1 || timeout 120 apt-get update || true; \
        if apt-cache show "$pkg" > /dev/null 2>&1 \
            && timeout 300 apt-get install -y --no-install-recommends "$pkg" hostname bc; then \
            break; \
        fi; \
        if [ "$attempt" -eq 6 ]; then \
            echo "could not install $pkg from the openfoam apt repository after 6 attempts" >&2; \
            exit 1; \
        fi; \
        echo "openfoam install failed (attempt ${attempt}/6), retrying on another mirror" >&2; \
        sleep 5; \
    done \
    && rm -rf /var/lib/apt/lists/*

# matplotlib in a venv: Ubuntu 24.04's Python is externally managed, and the apt package pulls in scipy.
ARG MATPLOTLIB_VERSION=3.10.7
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv \
    && python3 -m venv /opt/foamplot \
    && /opt/foamplot/bin/pip install --no-cache-dir --disable-pip-version-check \
        "matplotlib==${MATPLOTLIB_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# foam-plot draws VTK output as PNGs. Its shebang points at the venv above.
COPY scripts/foam_plot.py /usr/local/bin/foam-plot
RUN chmod +x /usr/local/bin/foam-plot

# Load OpenFOAM in every non-interactive bash, because the queue environment runs commands without a login shell.
# The guard skips the reload when a parent shell already loaded it.
RUN printf '%s\n' \
        '[ -n "${WM_PROJECT_DIR:-}" ] || . /usr/lib/openfoam/openfoam'"${OPENFOAM_VERSION}"'/etc/bashrc' \
    > /etc/profile.d/openfoam.sh
ENV BASH_ENV=/etc/profile.d/openfoam.sh

# Fail the build, not the first job: solve, convert and plot the cavity tutorial through BASH_ENV alone.
RUN cd /tmp \
    && foamCloneCase "$FOAM_TUTORIALS/incompressible/icoFoam/cavity/cavity" /tmp/smoke > /dev/null \
    && cd /tmp/smoke \
    && blockMesh > /dev/null \
    && icoFoam > /dev/null \
    && foamToVTK -latestTime > /dev/null \
    && foam-plot field /tmp/smoke.png /tmp/smoke \
    && bytes=$(stat -c %s /tmp/smoke.png) \
    && if [ "$bytes" -lt 20000 ]; then \
        echo "build check: foam-plot produced a suspiciously small PNG (${bytes} bytes)" >&2; \
        exit 1; \
    fi \
    && echo "build check: solved, converted and plotted the cavity (${bytes} byte PNG)" \
    && rm -rf /tmp/smoke /tmp/smoke.png

# Reports what the image holds. The queue environment replaces this with its own command.
CMD ["bash", "-c", "echo \"OpenFOAM $WM_PROJECT_VERSION (API $FOAM_API), tutorials under $FOAM_TUTORIALS\""]
