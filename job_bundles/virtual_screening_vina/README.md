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

2. **Fleet host configuration script** — install AutoDock VINA and Open Babel on workers at boot. See `host-config-script.sh` in the sample data:
   ```
   https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/host-config-script.sh
   ```

3. **Deadline CLI**:
   ```bash
   pip install deadline
   ```

## Sample Data

Sample data is available for a quick test run — 50 FDA-approved drugs screened against the COVID-19 Main Protease (PDB: 6LU7):

- **Receptor**: `https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/receptor.pdb`
- **Compound library**: `https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/compound_library.sdf.gz`
- **Host config script**: `https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/host-config-script.sh`

Download them locally before submitting:
```bash
mkdir -p sample_data && cd sample_data
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/receptor.pdb
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/virtual-screening-vina/compound_library.sdf.gz
```

## Usage

```bash
deadline bundle submit path/to/virtual_screening_vina \
  -p "ReceptorPdb=sample_data/receptor.pdb" \
  -p "CompoundLibrary=sample_data/compound_library.sdf.gz" \
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

The fleet requires AutoDock VINA and Open Babel pre-installed. Use this host configuration script on your SMF fleet:

```bash
#!/bin/bash
set -euo pipefail
# Install VINA binary
curl -sL "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64" \
  -o /usr/local/bin/vina
chmod 755 /usr/local/bin/vina

# Install Open Babel via micromamba
curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C /usr/local bin/micromamba
/usr/local/bin/micromamba create -p /opt/openbabel -c conda-forge openbabel -y --quiet
chmod -R a+rX /opt/openbabel

# Create wrapper with correct library paths
cat > /usr/local/bin/obabel << 'EOF'
#!/bin/bash
export LD_LIBRARY_PATH="/opt/openbabel/lib:${LD_LIBRARY_PATH:-}"
export BABEL_DATADIR="/opt/openbabel/share/openbabel/3.1.0"
exec /opt/openbabel/bin/obabel "$@"
EOF
chmod 755 /usr/local/bin/obabel
echo "/opt/openbabel/lib" > /etc/ld.so.conf.d/openbabel.conf && ldconfig
```
