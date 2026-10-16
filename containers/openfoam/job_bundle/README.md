# Job bundle: sweep the OpenFOAM cavity over three viscosities

The job solves an OpenFOAM tutorial case at three viscosities, then plots the cases together.
Submit it to a queue that uses the Docker queue environment, as the [sample README](../README.md#submit-the-job) shows.

## Parameters

| Name | Default | Meaning |
|---|---|---|
| `DockerImage` | None, so pass it with `-p` | The image URI. The queue's Docker environment reads it. |
| `Tutorial` | `incompressible/icoFoam/cavity/cavity` | The case to clone, relative to `$FOAM_TUTORIALS`. |
| `Solver` | `icoFoam` | The solver to run. It must match the tutorial. |
| `EndTime` | `10` | Simulated seconds, replacing the tutorial's `endTime`. |
| `OutputDir` | `output` | Where the cases, plots and summary go. Job attachments upload it. |
| `ScriptsDir` | `scripts` | The scripts below. Hidden in the submitter. |

## Steps and scripts

| Step | Script | Work |
|---|---|---|
| `Solve`, step environment `Mesh` | [`scripts/mesh.sh`](scripts/mesh.sh) | Clones the tutorial and runs `blockMesh`, once per session. |
| `Solve`, one task per viscosity | [`scripts/solve.sh`](scripts/solve.sh) | Copies the mesh, sets `nu` and `endTime`, solves, converts to VTK and plots the case. |
| `Plot`, after every `Solve` task | [`scripts/plot.sh`](scripts/plot.sh) | Draws the centreline graph and writes `summary.txt`. |

Each script takes its values as arguments. The template never pastes a parameter into shell code.
The `Plot` step can run on another worker, and job attachments bring it the `Solve` output.

## Outputs

| Path under `OutputDir` | Contents |
|---|---|
| `cases/nu-<viscosity>/` | The solved case, its solver and `foamToVTK` logs, and `VTK/` |
| `plots/nu-<viscosity>-velocity.png` | Velocity magnitude and flow direction for one case |
| `plots/centreline.png` | Horizontal velocity on the vertical centreline, one line per case |
| `summary.txt` | OpenFOAM version, then the viscosity, end time and run time of each case |

## Other tutorials

The viscosity range suits the cavity. Another tutorial works when it meets three conditions:

- Its setup is `blockMesh` followed by the solver.
- It sets `nu` in `constant/transportProperties`.
- Its mesh is 2D, one cell thick, which the plots require.

Change the `range` of `Viscosity` in `template.yaml` to suit the new case.

## Run without a container

On a Linux host where `bash` already loads OpenFOAM, the [Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli) runs the job directly.
`DockerImage` needs a value, but nothing reads it.

```bash
openjd run template.yaml -p DockerImage=unused \
    -p ScriptsDir="$PWD/scripts" -p OutputDir="$PWD/output"
```
