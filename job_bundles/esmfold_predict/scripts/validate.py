#!/usr/bin/env python3
"""Layer-3 validation: TM-score predicted structures against reference PDBs.

Optional step. Skipped (early exit 0) when --reference-pdb-dir is empty/missing,
since most users will run the bundle on novel sequences without ground truth.
When references ARE supplied, this is the only validation step that catches
"confident but wrong" outputs that pLDDT-based checks miss.

Reference PDBs must be named <seq_id>.pdb to match results/<seq_id>/<seq_id>.pdb.
TM-score is computed via biotite's structure superimposition; we don't shell out
to USalign/TM-align so the bundle stays pure-Python.
"""
import argparse
import csv
import json
import sys
from pathlib import Path


def compute_metrics(pred_path: Path, ref_path: Path, plot_path: Path) -> dict:
    """Compute TM-score, RMSD, and pLDDT calibration against a reference.

    Returns:
      tm_score, rmsd, aligned_residues — global structural similarity
      plddt_error_pearson — Pearson r between per-residue pLDDT and
        per-residue distance-from-reference. A well-calibrated model produces
        a strongly negative correlation (high pLDDT → small error). This is
        the most direct test of "does the model know when it's wrong" and
        catches confidently-wrong failure modes that aggregate scores miss.

    Side effect: writes a per-residue calibration plot to plot_path.

    Uses biotite >=1.2 native tm_score + superimpose_structural_homologs
    (BSD-3) for alignment-aware residue correspondence. References read with
    model=1 to handle NMR ensembles per CASP/CAMEO convention.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from biotite.structure.io.pdb import PDBFile
    from biotite.structure import superimpose_structural_homologs, tm_score

    pred = PDBFile.read(str(pred_path)).get_structure(
        model=1, altloc="first", extra_fields=["b_factor"]
    )
    ref = PDBFile.read(str(ref_path)).get_structure(model=1, altloc="first")

    pred_ca = pred[pred.atom_name == "CA"]
    ref_ca = ref[ref.atom_name == "CA"]

    if len(pred_ca) < 3 or len(ref_ca) < 3:
        return {
            "tm_score": 0.0,
            "rmsd": float("nan"),
            "aligned_residues": min(len(pred_ca), len(ref_ca)),
            "plddt_error_pearson": float("nan"),
        }

    fitted, _, ref_indices, sub_indices = superimpose_structural_homologs(
        ref_ca, pred_ca
    )

    tm = float(
        tm_score(ref_ca, fitted, ref_indices, sub_indices, reference_length="shorter")
    )

    diff = fitted.coord[sub_indices] - ref_ca.coord[ref_indices]
    per_residue_err = np.sqrt((diff ** 2).sum(axis=-1))
    rmsd = float(np.sqrt((per_residue_err ** 2).mean()))

    # pLDDT lives in the B-factor column of the predicted CA atoms (rescaled
    # to [0, 100] in fold.py). Pull the pLDDT for each residue that participated
    # in the superposition.
    plddt = pred_ca.b_factor[sub_indices]
    seq_id = pred_path.stem

    if len(per_residue_err) >= 3 and plddt.std() > 0 and per_residue_err.std() > 0:
        pearson = float(np.corrcoef(plddt, per_residue_err)[0, 1])
    else:
        pearson = float("nan")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(plddt, per_residue_err, c=plddt, cmap="viridis", s=60, edgecolor="k", linewidth=0.5)
    ax.set_xlabel("Predicted confidence (pLDDT)")
    ax.set_ylabel("Distance from experimental (Å)")
    ax.set_title(f"{seq_id.upper()}  per-residue calibration\n"
                 f"Pearson r = {pearson:.2f}   (negative = well calibrated)")
    ax.set_xlim(0, 100)
    ax.axvline(70, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.axvline(90, color="gray", linestyle="--", linewidth=0.7, alpha=0.5)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)

    return {
        "tm_score": round(tm, 4),
        "rmsd": round(rmsd, 3),
        "aligned_residues": int(len(ref_indices)),
        "plddt_error_pearson": round(pearson, 4) if pearson == pearson else float("nan"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--reference-pdb-dir", type=Path, default=None)
    args = ap.parse_args()

    if not args.reference_pdb_dir or str(args.reference_pdb_dir).strip() == "" \
            or not args.reference_pdb_dir.exists():
        print("openjd_status: no reference PDB directory provided, skipping TM-score validation")
        return 0

    # Print biotite version up-front so any "no attribute tm_score" failure is
    # diagnosable from the log (tm_score requires biotite >= 1.2.0).
    import biotite
    print(f"openjd_status: biotite version={biotite.__version__}")

    results_dir = args.output_dir / "results"
    pred_pdbs = sorted(results_dir.glob("*/*.pdb"))
    if not pred_pdbs:
        raise SystemExit(f"openjd_fail: no predicted PDBs under {results_dir}")

    rows = []
    for pred_path in pred_pdbs:
        seq_id = pred_path.stem
        ref_path = args.reference_pdb_dir / f"{seq_id}.pdb"
        if not ref_path.exists():
            print(f"openjd_status: no reference for {seq_id}, skipping")
            continue
        print(f"openjd_status: comparing {seq_id} vs reference")
        plot_path = pred_path.parent / "calibration.png"
        metrics = compute_metrics(pred_path, ref_path, plot_path)

        summary_path = pred_path.parent / "summary.json"
        existing = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        existing.update({
            "tm_score": metrics["tm_score"],
            "rmsd": metrics["rmsd"],
            "plddt_error_pearson": metrics["plddt_error_pearson"],
        })
        summary_path.write_text(json.dumps(existing, indent=2))

        rows.append({"seq_id": seq_id, **metrics, "mean_plddt": existing.get("mean_plddt")})

    if not rows:
        print("openjd_status: no matching references found")
        return 0

    csv_path = args.output_dir / "validation.csv"
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["seq_id", "tm_score", "rmsd", "aligned_residues",
                        "mean_plddt", "plddt_error_pearson"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"openjd_status: wrote {csv_path} with {len(rows)} comparisons")

    avg_tm = sum(r["tm_score"] for r in rows) / len(rows)
    valid_pearson = [r["plddt_error_pearson"] for r in rows
                     if r["plddt_error_pearson"] == r["plddt_error_pearson"]]
    print(f"openjd_status: mean TM-score across {len(rows)} structures = {avg_tm:.3f}")
    if valid_pearson:
        print(f"openjd_status: mean pLDDT/error Pearson r = {sum(valid_pearson)/len(valid_pearson):.3f} "
              f"(negative = well calibrated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
