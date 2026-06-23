# CARLA + scenario_runner image for Deadline Cloud
# Multi-sensor capture: Up to 6-cam RGB ring + up to 6-cam semantic seg + LiDAR + bounding boxes
#
# Base: carlasim/carla:0.9.16 (~8 GB compressed, ~25 GB on disk)
#   - Ubuntu 20.04
#   - Python 3.8 default (no pip!)
#   - CARLA Python wheels at /workspace/PythonAPI/carla/dist/ (cp310/cp311/cp312)
#
# We install Python 3.10 via `uv` (Astral) which downloads a pre-built portable
# Python in seconds (no PPA, no apt fragility). Then we use the bundled CARLA
# cp310 wheel, since PyPI's `carla==0.9.16` doesn't ship cp38 wheels.
#
# Adds: scenario_runner v0.9.16 + Python deps, in /opt/venv

FROM carlasim/carla:0.9.16

USER root

# Minimal apt deps + uv installation. uv brings its own Python.
# UV_PYTHON_INSTALL_DIR puts the standalone Python under /opt instead of /root,
# so the non-root 'carla' user (which runs the entrypoint) can read it.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_INSTALL_DIR=/usr/local/bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        git \
        wget \
        netcat-openbsd \
        ffmpeg \
        xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | env INSTALLER_NO_MODIFY_PATH=1 sh \
    && uv --version

# Pre-fetch Python 3.10 into /opt/uv-python (visible to non-root users)
RUN mkdir -p /opt/uv-python \
    && uv python install 3.10 \
    && chmod -R a+rX /opt/uv-python

# Create venv with that Python
RUN uv venv --python 3.10 /opt/venv \
    && /opt/venv/bin/python --version

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

# Install the bundled CARLA Python wheel (cp310 → 3.10 venv)
RUN uv pip install --no-cache --python /opt/venv/bin/python \
        /workspace/PythonAPI/carla/dist/carla-0.9.16-cp310-cp310-manylinux_2_31_x86_64.whl \
    && /opt/venv/bin/python -c "import carla; print('carla OK')"

# Clone scenario_runner v0.9.16
WORKDIR /opt
RUN git clone --depth=1 --branch v0.9.16 \
        https://github.com/carla-simulator/scenario_runner.git

WORKDIR /opt/scenario_runner

# Install scenario_runner requirements (drop the carla pin; already installed)
RUN sed -i '/^carla[<>=! ]/d' requirements.txt \
    && uv pip install --no-cache --python /opt/venv/bin/python \
        -r requirements.txt

# Copy entrypoint + sensor capture scripts, make /outputs writable
COPY entrypoint.sh /opt/entrypoint.sh
COPY capture_sensors.py /opt/capture_sensors.py
RUN chmod +x /opt/entrypoint.sh \
    && mkdir -p /outputs \
    && chown -R carla:carla /outputs /opt/scenario_runner /opt/venv

# CARLA image runs as the 'carla' user by default
USER carla
WORKDIR /home/carla

ENV PYTHONPATH=/opt/scenario_runner:/workspace/PythonAPI/carla:${PYTHONPATH:-}
ENV CARLA_PYTHON=/opt/venv/bin/python

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["/inputs/scenario.osc", "/outputs"]
