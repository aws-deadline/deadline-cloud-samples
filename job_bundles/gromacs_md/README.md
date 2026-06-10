# GROMACS Molecular Dynamics

Runs a complete molecular dynamics simulation pipeline using GROMACS: system preparation, energy minimization, equilibration (NVT + NPT), production MD, and structural analysis. Supports parallel fan-out across multiple independent replica simulations.

## How It Works

```
Step 1: PrepareSystem  (per replica)
  PDB → pdb2gmx → editconf → solvate → genion (topology + solvated box)

Step 2: EnergyMinimization  (per replica, depends on Step 1)
  grompp + mdrun with steepest descent

Step 3: Equilibration  (per replica, depends on Steps 1+2)
  NVT (100 ps, V-rescale thermostat) → NPT (100 ps, Parrinello-Rahman barostat)

Step 4: ProductionMD  (per replica, depends on Steps 1+3)
  Unrestrained NPT simulation (configurable length)

Step 5: Analysis  (per replica, depends on Steps 1+4)
  RMSD, RMSF, radius of gyration, hydrogen bonds, energy
```

For multi-replica campaigns, all replicas run through the full pipeline independently in parallel via the `ReplicaIndex` parameter space.

## Prerequisites

1. **Deadline Cloud farm** with a Linux SMF fleet (x86_64, min 4 vCPU).

2. **Fleet host configuration script** — install GROMACS on workers at boot.
   See [`host_configuration_scripts/gromacs/`](../../host_configuration_scripts/gromacs/) in this repo.

3. **Deadline CLI**:
   ```bash
   pip install deadline
   ```

## Sample Data

Sample data for a quick test — hen egg-white lysozyme (PDB: 1AKI), the standard GROMACS tutorial system:

- **Protein**: `https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/protein.pdb`
- **MDP files**: `https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/mdp/minimization.mdp`
- **Host config**: See [`host_configuration_scripts/gromacs/`](../../host_configuration_scripts/gromacs/)

Download them locally:
```bash
mkdir -p sample_data/mdp && cd sample_data
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/protein.pdb
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/mdp/minimization.mdp
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/mdp/nvt.mdp
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/mdp/npt.mdp
curl -LO https://downloads.deadlinecloud.amazonaws.com/samples/gromacs-md/mdp/production.mdp
```

## Usage

```bash
deadline bundle submit path/to/gromacs_md \
  -p "InputPdb=sample_data/protein.pdb" \
  -p "MdpMinimization=sample_data/mdp/minimization.mdp" \
  -p "MdpNvt=sample_data/mdp/nvt.mdp" \
  -p "MdpNpt=sample_data/mdp/npt.mdp" \
  -p "MdpProduction=sample_data/mdp/production.mdp" \
  -p "OutputDir=output" \
  -p "ProductionSteps=500000" \
  -p "MaxReplicaIndex=0"
```

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| ForceField | GROMACS force field | amber99sb-ildn |
| WaterModel | Water model | tip3p |
| BoxDistance | Distance from solute to box edge (nm) | 1.0 |
| ProductionSteps | MD steps (500000 = 1 ns at 2 fs) | 500000 |
| MaxReplicaIndex | Last replica index (for parallel replicas) | 0 |

### Multi-Replica Example

Run 10 independent simulations in parallel:
```bash
deadline bundle submit path/to/gromacs_md \
  -p "InputPdb=protein.pdb" \
  -p "MdpMinimization=mdp/minimization.mdp" \
  -p "MdpNvt=mdp/nvt.mdp" \
  -p "MdpNpt=mdp/npt.mdp" \
  -p "MdpProduction=mdp/production.mdp" \
  -p "ProductionSteps=5000000" \
  -p "MaxReplicaIndex=9" \
  -p "JobName=lysozyme-10replicas"
```

## Performance

Tested with lysozyme (1AKI) on c5d.xlarge (4 vCPU, Spot):
- 10,000 steps (20 ps) completed in 90 seconds
- Performance: 19 ns/day
- Full pipeline (prep + EM + NVT + NPT + production + analysis) in ~30 minutes

For longer simulations, consider larger instances (c5.4xlarge, 16 vCPU) or GPU instances (g5.xlarge with CUDA-enabled GROMACS).

## Host Configuration Script

The fleet requires GROMACS pre-installed. Use the host configuration script from [`host_configuration_scripts/gromacs/`](../../host_configuration_scripts/gromacs/) on your SMF fleet.

## Use Cases

- **Drug binding studies** — simulate protein-ligand complexes to validate virtual screening hits
- **Protein stability** — compare wild-type vs mutant dynamics (fan out across variants)
- **Free energy perturbation** — parallel lambda windows for binding affinity prediction
- **Conformational sampling** — multiple replicas for enhanced sampling statistics
