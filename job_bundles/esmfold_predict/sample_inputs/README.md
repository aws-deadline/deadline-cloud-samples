# Sample inputs

`demo.fasta` contains three short, well-characterized monomer benchmarks used as smoke-test inputs for the bundle.

| ID | Length | Description | PDB |
|---|---|---|---|
| `1l2y` | 20 aa | Trp-cage miniprotein | [1L2Y](https://www.rcsb.org/structure/1L2Y) |
| `2jof` | 20 aa | Trp-cage variant | [2JOF](https://www.rcsb.org/structure/2JOF) |
| `1vii` | 36 aa | Villin headpiece | [1VII](https://www.rcsb.org/structure/1VII) |

These three sequences are short enough to fold in under a minute on a single A10G and have well-characterized experimental structures, which makes them suitable for verifying the bundle end-to-end including the optional `Validate` step. They are not CASP benchmark targets. For CASP15 sequences, see https://predictioncenter.org/casp15/targetlist.cgi.

## Reference PDBs

The `reference_pdbs/` directory is empty by default. To enable the optional `Validate` step, populate it with experimental references from RCSB:

```bash
cd job_bundles/esmfold_predict/sample_inputs/reference_pdbs
for id in 1l2y 2jof 1vii; do
  curl -s "https://files.rcsb.org/download/${id}.pdb" -o "${id}.pdb"
done
```

Then submit with:

```bash
deadline bundle submit ./job_bundles/esmfold_predict/ \
  --parameter InputFasta=./job_bundles/esmfold_predict/sample_inputs/demo.fasta \
  --parameter ReferencePdbDir=./job_bundles/esmfold_predict/sample_inputs/reference_pdbs
```
