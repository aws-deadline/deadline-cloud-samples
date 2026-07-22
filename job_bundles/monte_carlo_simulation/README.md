# Pricing Financial Derivatives

Prices a portfolio of autocallable structured notes using Monte Carlo simulation with QuantLib's Heston stochastic volatility model. This sample is a Deadline Cloud port of the [Pricing Financial Derivatives with AWS Batch](https://ec2spotworkshops.com/monte-carlo-with-batch.html) workshop, using the same Eurostoxx 50 vol surface and sample portfolio dataset from the original workshop.

The pricing code is based on [Mikael Katajamäki's](http://mikejuniperhill.blogspot.com/2019/11/quantlib-python-heston-monte-carlo.html) QuantLib autocallable valuation example. The market data such as spot price and vol surface are defined inside the script, so whilst the results are not accurate for production use, they are a good example of how to use QuantLib without getting caught up in the details of connecting to market data sources.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Workstation                         │
│                                                                 │
│  portfolio.json ──► deadline bundle submit ──► results/         │
│                          │                        ▲             │
│                          │ (upload)               │ (download)  │
└──────────────────────────┼────────────────────────┼─────────────┘
                           │                        │
                           ▼                        │
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Deadline Cloud Farm                      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Service-Managed Fleet                  │  │
│  │                  (Linux, conda-forge)                     │  │
│  │                                                           │  │
│  │  Step 1: PricePositions                                   │  │
│  │  ┌──────┐ ┌──────┐ ┌──────┐       ┌──────┐                │  │
│  │  │Pos 0 │ │Pos 1 │ │Pos 2 │ ···   │Pos 47│  (parallel)    │  │
│  │  └──┬───┘ └──┬───┘ └──┬───┘       └──┬───┘                │  │
│  │     └────────┴────────┴──────┬───────┘                    │  │
│  │                              ▼                            │  │
│  │  Step 2: AggregateResults                                 │  │
│  │  ┌──────────────────────────────┐                         │  │
│  │  │ Collect results → summary    │  (1 task)               │  │
│  │  └──────────────────────────────┘                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Conda queue environment installs:                              │
│  quantlib-python, numpy, scipy from conda-forge                 │
└─────────────────────────────────────────────────────────────────┘
```

Two-step pipeline defined in `template.yaml`:

1. **PricePositions**: One task per portfolio position. Tasks are grouped into chunks that calibrate the Heston model once and price all positions in the chunk.
2. **AggregateResults**: Collects all per-position results into a portfolio summary.

## Prerequisites

1. **Deadline Cloud farm**: You need a farm with a queue that has a conda queue
   environment. You can create one in either of these ways:
   - **Console**: Use the [Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home)
     to create a farm, queue, and service-managed fleet through the guided setup wizard.
   - **CloudFormation**: Deploy the
     [starter farm template](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm),
     which creates a ready-to-use farm with service-managed fleets and a conda queue
     environment. Follow its setup instructions to deploy the stack and initialize the
     S3 conda channel.

   When configuring your fleet, consider adjusting the vCPU and RAM settings based on
   your workload requirements.

2. **Deadline CLI**: Install the Deadline Cloud client tools:
   ```bash
   pip install deadline
   ```

3. **conda-forge channel**: This job bundle requires packages from
   [conda-forge](https://conda-forge.org/), namely `quantlib-python`.
   When deploying the CloudFormation template, set the **ProdCondaChannels** parameter
   to `deadline-cloud conda-forge` to enable conda-forge alongside the default
   deadline-cloud channel. If your farm is already deployed without conda-forge, you
   can update the CloudFormation stack and change this parameter, or edit the queue
   environment directly from the
   [Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home)
   by navigating to your queue's environment settings and adding `conda-forge` to the
   channels list.

## Usage

```bash
# Open the GUI to review and edit parameters before submitting
deadline bundle gui-submit monte_carlo_simulation/

# Submit with defaults (48 positions, 10K MC paths)
deadline bundle submit monte_carlo_simulation/

# Quick test with fewer positions and paths
deadline bundle submit monte_carlo_simulation/ \
  -p PositionRange="0-1" -p NumPaths=100

# Submit different portfolios with separate output directories
deadline bundle submit monte_carlo_simulation/ \
  -p PortfolioFile=portfolios/equities.json \
  -p ResultsDir=results/equities

deadline bundle submit monte_carlo_simulation/ \
  -p PortfolioFile=portfolios/rates.json \
  -p ResultsDir=results/rates
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| PortfolioFile | portfolio.json | Input portfolio JSON file |
| ResultsDir | results | Directory for per-position results and final aggregate |
| PositionRange | 0-47 | Range of position indices to price |
| NumPaths | 10000 | Monte Carlo paths per position |
| ChunkSize | 1 | Initial number of tasks per chunk |
| ChunkTargetRuntime | 180 | Target runtime in seconds per chunk |
| CondaPackages | python quantlib-python numpy scipy | Packages to install |
| CondaChannels | conda-forge | Conda channels |
| ScriptsDir | scripts | Directory containing the Python scripts |

## Output

- `results/result_N.json`: Per-position pricing result (PV, greeks, model params)
- `results/portfolio_summary.json`: Aggregated portfolio summary with total PV

To download results after the job completes:

```bash
deadline job download-output --job-id <job-id>
```

## Task Chunking for Load Balancing

This job uses the Open Job Description
[TASK_CHUNKING](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0001-task-chunking.md)
extension to run multiple positions with a single command. Each chunk calibrates the
Heston stochastic volatility model once and then prices all positions in the chunk,
amortizing the calibration cost.

By default, `ChunkSize` is 1 and `ChunkTargetRuntime` is 180 seconds (3 minutes).
The scheduler starts by dispatching individual positions, observes how long they take,
and then automatically grows the chunk size so that each chunk runs for approximately
the target runtime. The chunking balances load without needing to know the
per-position runtime ahead of time:

- **Fast positions**: the scheduler grows chunks to group more together, amortizing
  model calibration and scheduling overhead.
- **Slow positions**: chunks stay small since individual tasks already approach the
  target runtime, keeping work spread across the fleet.

You can override these defaults if you already know the runtime characteristics of
your portfolio:

```bash
# Large chunks for a portfolio with fast-to-price positions
deadline bundle submit monte_carlo_simulation/ -p ChunkSize=20

# Disable automatic sizing and use fixed chunks
deadline bundle submit monte_carlo_simulation/ -p ChunkSize=10 -p ChunkTargetRuntime=0
```

## Differences from the AWS Batch/Lambda Version

This sample separates the deployed Deadline Cloud infrastructure from the workload
definition. You use a Deadline Cloud farm with job attachments enabled, a Linux fleet,
and a conda queue environment. The workload is fully specified by the job bundle,
including the application requirements as `CondaPackages` and scripts to run.

- **Job attachments** handle file I/O (portfolio in, results out)
- **Conda** provides dependencies at runtime (no container build)
- **OpenJD step dependencies** orchestrate pricing → aggregation

## Future

The `PositionRange` parameter requires knowing the number of positions up front. The [VAR_DATA_FLOW](https://github.com/OpenJobDescription/openjd-specifications/discussions/111) feature proposed for Open Job Description would allow replacing this with a step that counts positions from the portfolio file at runtime.
