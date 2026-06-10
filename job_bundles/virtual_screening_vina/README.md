# Virtual Screening with AutoDock VINA

Screens a compound library against a protein target to identify drug candidates using AutoDock VINA molecular docking. The job splits the library into chunks and docks them in parallel across a fleet of Spot workers — a common drug discovery pattern that scales from thousands to millions of compounds.

## How It Works

```
Step 1: PrepareReceptor  (1 task)
  Convert protein PDB → PDBQT format via Open Babel

Step 2: SplitLibrary  (1 task, depends on Step 1)
  Split SDF compound library into N chunks

Step 3: DockCompounds  (N tasks, parallel, depends on Steps 1+2)
  ┌────────┐ ┌────────┐ ┌────────┐     ┌────────┐
  │Chunk 0 │ │Chunk 1 │ │Chunk 2 │ ... │Chunk N │
  └───┬────┘ └───┬────┘ └───┬────┘     └───┬────┘
      │          │          │               │
      ▼          ▼          ▼               ▼
  obabel → VINA dock → extract scores (per chunk, idempotent)

Step 4: ScoreAndRank  (1 task, depends on Step 3)
  Aggregate all chunk results → ranked CSV of top hits by binding affinity
```

Each docking task is idempotent (safe for Spot preemption — skips if results already exist).

## Prerequisites

1. **Deadline Cloud farm** with a Linux SMF fleet (x86_64, Spot recommended).

2. **Fleet host configuration script** — install AutoDock VINA and Open Babel on workers at boot.
   See [`host_configuration_scripts/autodock_vina/`](../../host_configuration_scripts/autodock_vina/) in this repo.

3. **Deadline CLI**:
   ```bash
   pip install deadline
   ```

## Sample Data

Sample data for a quick test — screen compounds against the COVID-19 Main Protease:

- **Receptor**: Download directly from RCSB Protein Data Bank:
  ```bash
  curl -LO https://files.rcsb.org/download/6LU7.pdb
  grep "^ATOM" 6LU7.pdb > receptor.pdb  # strip to protein atoms only
  ```
- **Compound library**: Pre-processed subset hosted on CDN:
  ```bash
  curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/compound_library.sdf.gz
  ```

### Data Attribution

| File | Source | License |
|------|--------|---------|
| receptor.pdb | [RCSB PDB 6LU7](https://www.rcsb.org/structure/6LU7) — SARS-CoV-2 Main Protease (Jin et al., 2020, Nature) | CC0 1.0 (Public Domain) |
| compound_library.sdf.gz | [ChEMBL 37](https://www.ebi.ac.uk/chembl/) — 100k drug-like compounds extracted from ChEMBL database (Zdrazil et al., 2024, Nucleic Acids Research) | CC BY-SA 3.0 |

## Usage

```bash
deadline bundle submit path/to/virtual_screening_vina \
  -p "ReceptorPdb=receptor.pdb" \
  -p "CompoundLibrary=compound_library.sdf.gz" \
  -p "OutputDir=output" \
  -p "CompoundsPerChunk=100" \
  -p "MaxChunkIndex=499" \
  -p "CenterX=-10.7" \
  -p "CenterY=12.4" \
  -p "CenterZ=68.8" \
  -p "Exhaustiveness=8"
```

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| CompoundsPerChunk | Molecules per parallel task | 1000 |
| MaxChunkIndex | Last chunk index (num_chunks - 1) | 999 |
| CenterX/Y/Z | Docking box center (Angstroms) | 0.0 |
| SizeX/Y/Z | Docking box dimensions (Angstroms) | 20.0 |
| Exhaustiveness | Search thoroughness (1-64) | 8 |
| TopN | Number of top hits to report | 500 |

## Performance

Tested with 100,000 ChEMBL compounds against COVID-19 Main Protease:
- 1,000 parallel tasks across 10 Spot workers
- ~5-8 hours wall clock at exhaustiveness=4
- Best hit: -14.53 kcal/mol
- 44 compounds with affinity < -7.0 kcal/mol (strong binders)

## Host Configuration Script

The fleet requires AutoDock VINA and Open Babel pre-installed. Use the host configuration script from [`host_configuration_scripts/autodock_vina/`](../../host_configuration_scripts/autodock_vina/) on your SMF fleet.
