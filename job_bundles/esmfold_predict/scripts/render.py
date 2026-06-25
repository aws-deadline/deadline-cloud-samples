#!/usr/bin/env python3
"""Render PNG images of folded structures for visual review.

Walks OutputDir/results/<seq_id>/<seq_id>.pdb and produces:
  - <seq_id>_plddt_<NN>.png  (CA-trace, colored by per-residue pLDDT)

Uses matplotlib (CPU only). PyMOL's cartoon-ribbon renderer would look prettier
but pymol-open-source has heavy graphics deps that destabilize the conda solve
on the worker (rattler#2292) — switching to matplotlib trades visual polish for
a solver-stable build matching unsloth_finetune's package profile.
"""
import argparse
import json
import sys
from pathlib import Path


def render_pdb(pdb_path: Path, png_path: Path, mean_plddt: float) -> None:
    """Render a CA-trace plot colored by pLDDT, saved to png_path."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    import numpy as np
    from biotite.structure.io.pdb import PDBFile

    structure = PDBFile.read(str(pdb_path)).get_structure(
        model=1, altloc="first", extra_fields=["b_factor"]
    )
    ca = structure[structure.atom_name == "CA"]
    coords = ca.coord
    plddt = ca.b_factor

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")

    # Draw the backbone as line segments colored by pLDDT (the AlphaFold/ESMFold
    # convention: orange < 50, yellow 50-70, cyan 70-90, blue > 90).
    cmap = plt.get_cmap("plasma_r")
    norm = plt.Normalize(vmin=50, vmax=90)
    for i in range(len(coords) - 1):
        seg = coords[i:i + 2]
        # Colour by the avg pLDDT of the two endpoints; clamp at 50/90 caps.
        c_val = max(min((plddt[i] + plddt[i + 1]) / 2, 90), 50)
        ax.plot(seg[:, 0], seg[:, 1], seg[:, 2], color=cmap(norm(c_val)), linewidth=3)

    seq_id = pdb_path.stem
    ax.set_title(f"{seq_id.upper()}  ({len(coords)} aa)  mean pLDDT = {mean_plddt:.1f}")
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])

    # pLDDT colorbar legend
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
    cbar.set_label("pLDDT")

    fig.tight_layout()
    fig.savefig(png_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()

    results_dir = args.output_dir / "results"
    if not results_dir.exists():
        raise SystemExit(f"openjd_fail: results directory not found: {results_dir}")

    pdbs = sorted(results_dir.glob("*/*.pdb"))
    if not pdbs:
        raise SystemExit(f"openjd_fail: no PDB files under {results_dir}")

    rendered = 0
    for pdb_path in pdbs:
        seq_dir = pdb_path.parent
        summary_path = seq_dir / "summary.json"
        mean_plddt = 0.0
        if summary_path.exists():
            mean_plddt = json.loads(summary_path.read_text()).get("mean_plddt", 0.0)
        png_path = seq_dir / f"{pdb_path.stem}_plddt_{int(round(mean_plddt)):02d}.png"
        print(f"openjd_status: rendering {pdb_path.name} -> {png_path.name}")
        render_pdb(pdb_path, png_path, mean_plddt)
        rendered += 1

    print(f"openjd_status: rendered {rendered} structures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
