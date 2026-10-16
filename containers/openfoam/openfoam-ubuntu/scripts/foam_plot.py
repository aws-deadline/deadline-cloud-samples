#!/opt/foamplot/bin/python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Turn the VTK output of an OpenFOAM case into PNG plots.

``foamToVTK`` writes data, not pictures. This reads that data and draws it with
matplotlib's Agg backend: a pure software rasteriser that needs no OpenGL
context, no X server and no ParaView. That matters in a container, where the
usual answer -- ParaView's ``pvbatch`` -- costs about 400 MB and a Qt stack.

The ``.vtu`` files are parsed with the standard library rather than with the
``vtk`` Python module, which on Ubuntu pulls in LLVM and mesa (about 800 MB) to
link an OpenGL renderer that Agg never calls. ``foamToVTK`` writes both cell
fields and point-interpolated fields, and the point values are what the
plotting routines want, so the parser only has to find two arrays: the mesh
points and the point field.

Two plot kinds, matching the two things people want out of a CFD run:

``field``
    A picture of one case. Filled contours of velocity magnitude with
    streamlines over them.

``profile``
    A graph comparing cases. Horizontal velocity along the vertical centreline,
    one line per case. For the lid-driven cavity this is the standard benchmark
    plot, and it is where a Reynolds number sweep actually shows itself.

Both read the newest time directory under a case's ``VTK/`` directory.

Usage:
    foam-plot field   OUT.png CASE_DIR
    foam-plot profile OUT.png CASE_DIR [CASE_DIR ...]

The shebang points into the virtual environment the Dockerfile creates, since
Ubuntu 24.04 is an externally managed Python and matplotlib is not installed
system-wide. Run it as ``python3 foam_plot.py`` anywhere matplotlib is
importable.
"""

from __future__ import annotations

import argparse
import base64
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib

# Selecting Agg before pyplot is imported is what keeps this working with no
# display and no GL libraries present. Without it matplotlib tries to pick an
# interactive backend.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.tri import LinearTriInterpolator, Triangulation  # noqa: E402

# VTK type names as they appear in a DataArray's `type` attribute.
_VTK_DTYPES = {
    "Int8": np.int8,
    "UInt8": np.uint8,
    "Int32": np.int32,
    "UInt32": np.uint32,
    "Int64": np.int64,
    "UInt64": np.uint64,
    "Float32": np.float32,
    "Float64": np.float64,
}


def _read_data_array(element: ET.Element, header_dtype: np.dtype) -> np.ndarray:
    """Decode one <DataArray>, ascii or uncompressed base64 binary."""
    dtype = _VTK_DTYPES.get(element.get("type", ""))
    if dtype is None:
        raise SystemExit(f"unsupported DataArray type {element.get('type')!r}")

    text = (element.text or "").strip()
    fmt = element.get("format")

    if fmt == "ascii":
        # foamToVTK -ascii. Splitting and converting is fast enough for the mesh
        # sizes a plot is legible at.
        return np.array(text.split(), dtype=dtype)

    if fmt == "binary":
        # foamToVTK's default. A base64 payload prefixed by a byte count whose
        # width is the file's header_type, which is why that is passed in.
        raw = base64.b64decode(text)
        return np.frombuffer(raw, dtype=dtype, offset=header_dtype.itemsize)

    # 'appended' puts the bytes in a trailing <AppendedData> block instead of in
    # the element. foamToVTK does not emit it, so supporting it would be
    # untested code.
    raise SystemExit(
        f"DataArray format {fmt!r} is not supported; re-run foamToVTK without "
        "-appended, or with -ascii"
    )


class CaseData:
    """Mesh points and point fields from the newest VTK time of one case."""

    def __init__(self, case_dir: Path):
        self.case_dir = case_dir
        self.name = case_dir.name

        vtu = _latest_internal_vtu(case_dir)

        root = ET.parse(vtu).getroot()
        if root.get("compressor"):
            raise SystemExit(
                f"{vtu} is compressed ({root.get('compressor')}); re-run "
                "foamToVTK with -ascii"
            )
        header_dtype = np.dtype(_VTK_DTYPES.get(root.get("header_type", "UInt32")))

        piece = root.find(".//Piece")
        if piece is None:
            raise SystemExit(f"{vtu} has no <Piece>")

        # foamToVTK records the simulation time in FieldData. Prefer it over the
        # directory name, which carries the time *index* -- so a run ending at
        # 10 s with a 0.005 s step would otherwise be labelled 2000.
        self.time = _simulation_time(root, header_dtype)

        points = piece.find("Points")
        if points is None:
            raise SystemExit(f"{vtu} has no <Points>")
        coords = _read_data_array(_find_array(points, "Points", "Points"), header_dtype)
        coords = coords.reshape(-1, 3)

        point_data = piece.find("PointData")
        if point_data is None:
            raise SystemExit(f"{vtu} has no <PointData>")
        u = _find_array(point_data, "U", "PointData")
        self.u = _read_data_array(u, header_dtype).reshape(-1, 3)

        self.x = coords[:, 0]
        self.y = coords[:, 1]

        # A 2D OpenFOAM case is a single cell thick, so its mesh points sit on
        # exactly two planes in z. More than that is a genuinely 3D mesh, which
        # these plots would silently flatten -- so refuse rather than mislead.
        z_planes = np.unique(np.round(coords[:, 2], 9))
        if z_planes.size > 2:
            raise SystemExit(
                f"{self.name}: mesh spans {z_planes.size} planes in z; these "
                "plots only handle a 2D (one cell thick) case"
            )

        # Both planes carry identical values in a 2D case, so collapsing to the
        # unique (x, y) pairs halves the work and avoids a degenerate
        # triangulation from coincident points.
        _, keep = np.unique(np.column_stack((self.x, self.y)), axis=0, return_index=True)
        keep.sort()
        self.x = self.x[keep]
        self.y = self.y[keep]
        self.u = self.u[keep]

        self.triangulation = Triangulation(self.x, self.y)

    @property
    def speed(self) -> np.ndarray:
        return np.linalg.norm(self.u, axis=1)

    def sample_column(self, x: float, count: int = 200):
        """Interpolate u_x up a vertical line at the given x."""
        y = np.linspace(self.y.min(), self.y.max(), count)
        interp = LinearTriInterpolator(self.triangulation, self.u[:, 0].astype(float))
        ux = interp(np.full_like(y, x), y)
        # Points that fall outside the triangulation come back masked; drop them
        # so the line does not break at the walls.
        return y[~np.ma.getmaskarray(ux)], ux.compressed()


def _find_array(parent: ET.Element, name: str, where: str) -> ET.Element:
    for element in parent.findall("DataArray"):
        if element.get("Name") == name:
            return element
    raise SystemExit(f"no DataArray named {name!r} in <{where}>")


def _latest_internal_vtu(case_dir: Path) -> Path:
    vtk_dir = case_dir / "VTK"
    if not vtk_dir.is_dir():
        raise SystemExit(f"no VTK directory in {case_dir}; run foamToVTK first")

    candidates = sorted(vtk_dir.glob("*/internal.vtu"), key=lambda p: _time_index(p.parent.name))
    if not candidates:
        raise SystemExit(f"no */internal.vtu under {vtk_dir}")
    return candidates[-1]


def _time_index(dirname: str) -> int:
    """foamToVTK names time directories '<case>_<index>'; sort on that index."""
    _, _, tail = dirname.rpartition("_")
    return int(tail) if tail.isdigit() else -1


def _simulation_time(root: ET.Element, header_dtype: np.dtype) -> str:
    field_data = root.find(".//FieldData")
    if field_data is not None:
        for element in field_data.findall("DataArray"):
            if element.get("Name") == "TimeValue":
                value = float(_read_data_array(element, header_dtype)[0])
                return f"{value:g}"
    return "?"


def plot_field(out_png: Path, case: CaseData) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=140)

    contour = ax.tricontourf(case.triangulation, case.speed, levels=32, cmap="viridis")
    fig.colorbar(contour, ax=ax, label="velocity magnitude  |U|  (m/s)")

    # streamplot needs a regular grid, so interpolate the point vectors onto
    # one. LinearTriInterpolator keeps this matplotlib-only -- no scipy.
    grid_x, grid_y = np.meshgrid(
        np.linspace(case.x.min(), case.x.max(), 60),
        np.linspace(case.y.min(), case.y.max(), 60),
    )
    ux = LinearTriInterpolator(case.triangulation, case.u[:, 0].astype(float))(grid_x, grid_y)
    uy = LinearTriInterpolator(case.triangulation, case.u[:, 1].astype(float))(grid_x, grid_y)
    ax.streamplot(
        grid_x,
        grid_y,
        np.ma.filled(ux, 0.0),
        np.ma.filled(uy, 0.0),
        color="white",
        linewidth=0.6,
        density=1.3,
        arrowsize=0.7,
    )

    ax.set_title(f"{case.name}    t = {case.time} s")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_profile(out_png: Path, cases: list[CaseData]) -> None:
    fig, ax = plt.subplots(figsize=(6.0, 5.6), dpi=140)

    for case in cases:
        x_mid = 0.5 * (case.x.min() + case.x.max())
        y, ux = case.sample_column(x_mid)
        ax.plot(ux, y, linewidth=1.6, label=case.name)

    ax.axvline(0.0, color="0.7", linewidth=0.8)
    ax.set_title("horizontal velocity along the vertical centreline")
    ax.set_xlabel("$u_x$ (m/s)")
    ax.set_ylabel("y (m)")
    ax.legend(title="case", fontsize="small")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot OpenFOAM VTK output to a PNG.")
    parser.add_argument("kind", choices=("field", "profile"))
    parser.add_argument("out_png", type=Path, help="PNG to write")
    parser.add_argument(
        "case_dirs",
        type=Path,
        nargs="+",
        help="OpenFOAM case directories, each holding a VTK/ directory",
    )
    args = parser.parse_args(argv)

    if args.kind == "field" and len(args.case_dirs) != 1:
        parser.error("field takes exactly one case directory")

    args.out_png.parent.mkdir(parents=True, exist_ok=True)

    cases = [CaseData(directory) for directory in args.case_dirs]
    if args.kind == "field":
        plot_field(args.out_png, cases[0])
    else:
        plot_profile(args.out_png, sorted(cases, key=lambda case: case.name))

    print(f"wrote {args.out_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
