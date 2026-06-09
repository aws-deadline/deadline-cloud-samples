# Satellite Imagery Classification

Classifies satellite image tiles into land-cover categories (water, vegetation, bare soil, rock, cloud) and stitches the results into a single map. The job runs each tile in parallel across a fleet, then merges them — a common pattern for any workload where input files are independent.

Five sample tiles simulating the Grand Canyon area are automatically downloaded from the Deadline Cloud samples CDN when the job runs — no external data or accounts needed.

## How It Works

```
Step 1: ClassifyTiles  (5 tasks, parallel)
  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
  │North Rim│ │South Rim│ │ Inner   │ │ Desert  │ │  River  │
  │         │ │         │ │ Canyon  │ │  East   │ │  West   │
  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘
       │           │           │           │           │
       ▼           ▼           ▼           ▼           ▼
  Download tile → classify pixels → write result + color PNG

Step 2: MosaicResults  (1 task, runs after Step 1 finishes)
  Merge all tiles into one map + overview image
```

Each tile is a 4-band satellite image. The classifier looks at the color ratios between bands to decide what's on the ground — water absorbs infrared light, vegetation reflects it, etc.

## Prerequisites

1. **Deadline Cloud farm** with a Conda queue environment. The quickest setup is the
   [starter farm CloudFormation template](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm).

2. **Deadline CLI**:
   ```bash
   pip install deadline
   ```

3. **conda-forge channel** enabled on your queue (needed for the `rasterio` package).
   If you used the starter farm template, set the **ProdCondaChannels** parameter to
   `deadline-cloud conda-forge`. Otherwise, add `conda-forge` to your queue environment's
   channel list in the [Deadline Cloud console](https://console.aws.amazon.com/deadlinecloud/home).

## Usage

> **Note:** When submitting with the default sample tiles (i.e. without specifying `-p TilesDir`),
> you'll see a warning that `sample_tiles` does not exist locally — this is expected. The sample
> tiles are downloaded on the worker at runtime. This warning does not appear when you provide
> your own tiles directory.

```bash
# Submit with the sample tiles (downloaded automatically)
deadline bundle submit job_bundles/satellite_classification/

# Or open the GUI first to review parameters
deadline bundle gui-submit job_bundles/satellite_classification/

# Use your own tiles (skips download)
deadline bundle submit job_bundles/satellite_classification/ \
  -p TilesDir=/path/to/my/tiles
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| TilesDir | sample_tiles | Input directory of satellite image tiles |
| OutputDir | output | Where results are written |
| SampleTilesUrl | (CDN URL) | Base URL for downloading sample tiles |
| CondaPackages | python numpy rasterio matplotlib | Software installed on workers |
| CondaChannels | conda-forge | Package channel |

## Output

After the job completes:

```bash
deadline job download-output --job-id <job-id>
```

You'll get:
- A classified `.tif` and color `.png` per input tile
- `grand_canyon_mosaic.tif` — all tiles merged into one map
- `grand_canyon_mosaic.png` — overview image with legend and class percentages

## Running Locally

```bash
pip install numpy rasterio matplotlib

# Download sample tiles
for tile in T12S_GC_North_Rim T12S_GC_South_Rim T12S_GC_Inner_Canyon T12S_GC_Desert_East T12S_GC_River_West; do
  python scripts/download_tile.py "$tile" \
    https://downloads.deadlinecloud.amazonaws.com/samples/satellite-classification-tiles \
    sample_tiles/
done

# Classify all tiles
for tile in sample_tiles/*.tif; do
  python scripts/classify_tile.py "$tile" output/
done

# Merge into a mosaic
python scripts/mosaic.py output/
```

To regenerate the sample tiles from scratch instead of downloading: `python scripts/generate_sample_tiles.py`
