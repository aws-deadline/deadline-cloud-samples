# Germline variant calling with bwa, samtools, and bcftools

Finds the genetic differences between an individual and a reference genome.

A DNA sequencing machine does not read a genome end to end. It produces hundreds of millions of
short fragments, each a few hundred letters long, from random positions. Turning those fragments
into a list of differences takes three stages, and this job bundle runs all three:

1. **Align.** Work out where each fragment came from by matching it against a reference genome.
   `bwa` does this.
2. **Call.** At every position, compare the stacked-up fragments to the reference and decide whether
   the difference is real or a sequencing error. `bcftools` does this.
3. **Merge.** Collect the results into one file listing every confident difference.

The differences are **variants**, and finding them is **variant calling**, the workhorse analysis
behind everything from diagnosing inherited disease to breeding drought-tolerant crops. *Germline*
means the variants an individual was born with, rather than ones a tumor acquired later. The input
format is **FASTQ** (the sequencer's fragments) and the output a **VCF** (the list of variants).

Both expensive stages divide cleanly, which is what suits this to Deadline Cloud. Each sample aligns
on its own worker, and separate stretches of the genome are then called independently and stitched
back together.

## What this sample demonstrates

* **Software from bioconda.** `bwa`, `samtools`, `bcftools`, and `fastqc` are declared as conda
  packages rather than built into container images. See
  [Conda channel order](#conda-channel-order) for why `conda-forge` must come first.
* **Fan-out over samples and over genome regions.** `AlignReads` fans out over samples and
  `CallVariants` over regions, using different task parameters in different steps. `CallVariants`
  is the scatter and `MergeVariants` the gather.
* **A job environment as a precondition check.** `BioToolchain` verifies every command in
  `RequiredTools` is on `PATH` once per session and, if any is missing, prints the exact packages and
  channels to configure.
* **Scripts bundled beside the template.** The shell lives in [`scripts/`](scripts/) rather than
  embedded in `template.yaml`, following stage 2 of the
  [job development progression](../job_dev_progression/). See
  [Bundled scripts](#bundled-scripts) for what that changes.

The tool sequence comes from the
[AWS HealthOmics WDL variant-calling tutorial pipeline](https://github.com/aws-samples/aws-healthomics-tutorials/tree/main/example-workflows/wdl/variant-calling-pipeline),
reimplemented here for Open Job Description. [WDL](https://openwdl.org/) and Open Job Description are
both open workflow specifications with independent implementations, so having the same pipeline in
both is a good way to compare their designs. WDL infers the order of work from how data
flows between tasks and delivers software as containers; this bundle declares step dependencies
explicitly and installs its tools from conda. Either way the tool builds are equivalent, since the
BioContainers images WDL uses are themselves built from bioconda packages.

This pipeline also differs from the original in two ways. That one scatters over samples and gathers
them into a single whole-genome call; this one adds a second scatter over regions, so calling is
distributed rather than left on one worker. It also takes paired-end reads, the form most sequencers
produce, where the original takes one FASTQ per sample.

## How it works

```
QualityControl  (1 task/sample)     BuildIndex  (1 task)
  fastqc on each read pair            samtools faidx + bwa index
  → output/qc/                        → output/reference/
  no dependencies, starts at once             │
           │                                  ▼
           │                        AlignReads  (1 task/sample)
           │                          bwa mem | samtools sort, then index
           │                          → output/alignments/<sample>.sorted.bam
           │                                  │
           │                                  ▼
           │                        CallVariants  (1 task/region)  ── the scatter
           │                          bcftools mpileup | call | filter,
           │                          all samples jointly per region
           │                          → output/vcf_by_region/
           │                                  │
           └────────────────┬─────────────────┘
                            ▼
                  MergeVariants  (1 task)                          ── the gather
                    bcftools concat -d exact | norm, stats, MultiQC
                    → output/variants.vcf.gz
```

The default parameters (2 samples, 4 regions) produce 10 tasks.

The default regions are four windows of contig `1` rather than whole contigs, because the sample reads
align to only part of it and scattering over every contig would leave most tasks with nothing to call.
Windowing is also how you scatter a real genome: chromosomes vary widely in size, so a per-chromosome
scatter leaves one task running long after the rest finish. Keep windows non-overlapping, since
overlapping ones call the same site twice.

`RegionRange` must cover every entry in `Regions`. The practical ceiling is about 100 entries, because
a job parameter string is capped at 1024 characters. Staging the list as a data file instead lifts that
ceiling; see [Scaling the region list past the parameter limit](#scaling-the-region-list-past-the-parameter-limit).

`CallVariants` calls every sample jointly per region. Joint calling lets the caller distinguish a site
that matches the reference in one sample from one that merely lacked coverage there.

## What this sample leaves out

A production analysis would add steps this bundle omits to stay readable:

* **Duplicate marking** (`samtools fixmate -m` then `samtools markdup`, or Picard). PCR and optical
  duplicates inflate apparent allele support. `bcftools mpileup` already skips reads flagged as
  duplicates, but nothing here sets that flag, so `flagstat` reports `0 duplicates`. The
  `LB:` field in the read group exists for this step.
* **Base quality score recalibration.** A GATK idiom with no direct bcftools equivalent.
* **Adapter and quality trimming.** `bwa mem` soft-clips adapters, so this matters less than it once
  did. Note that `QualityControl` runs alongside `AlignReads` rather than before it, so the FastQC
  report cannot gate alignment.
* **Per-contig ploidy.** `Ploidy` applies job-wide. Real analyses need `bcftools call --ploidy-file`
  so chrX, chrY, and the mitochondrion are treated correctly.

Filtering and normalization are the exception, included because a callset is unusable without them:
`CallVariants` applies `MinQual` and `MinDepth`, and `MergeVariants` runs `bcftools norm` to
left-align indels and split multiallelic records.

One scaling limit worth knowing: `bcftools mpileup` joint calling has no gVCF equivalent, so adding a
sample to a cohort means recalling all of them.

## Prerequisites

1. **A Deadline Cloud farm with a Linux fleet.** The tools are only published for Linux and
   macOS, so the steps declare `attr.worker.os.family: linux`.

2. **A conda queue environment** whose channels include `conda-forge` and `bioconda`. See the
   [queue environment samples](../../queue_environments/) and
   [Create a queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html).
   If the queue is missing the tools, the job fails on entry with the packages and channels it
   needs rather than partway through a step.

3. **The Deadline Cloud CLI:**
   ```console
   pip install deadline
   ```

### Conda channel order

Set the channels to `conda-forge bioconda`, in that order. bioconda packages depend on
conda-forge for their runtime libraries, and [bioconda's documentation](https://bioconda.github.io/)
specifies conda-forge at higher priority, with strict channel priority. Reversing the order causes
dependency resolution failures that can be hard to read.

## Setup

Every command below runs from this sample's directory:

```console
cd job_bundles/variant_calling_bwa
```

The sample data is not committed to this repository. Download it with:

```console
python sample_inputs/fetch_test_data.py
```

That fetches about 950 KB: two paired-end read sets and a small GRCh37 subset as the reference. The
data is provided by
[AWS HealthOmics for their tutorials](https://github.com/aws-samples/aws-healthomics-tutorials) in the
public `aws-genomics-static-us-east-1` bucket, and originates from
[nf-core/test-datasets](https://github.com/nf-core/test-datasets), MIT licensed. See
[`sample_inputs/README.md`](sample_inputs/README.md) for what lands where.

Bring your own data instead by pointing `ReadsDir` at a directory of
`<sample>_R1.fastq.gz` / `<sample>_R2.fastq.gz` pairs, `ReferenceDir` at the directory holding your
reference, and `ReferenceFastaName` at the FASTA filename within it, then setting `Samples` and
`Regions` to match. Remember to update `SampleRange` and `RegionRange` as described below.

If that directory already holds a `.fai` or a bwa index built beside the FASTA, `BuildIndex` reuses
them instead of rebuilding, which is worth minutes on a whole genome. The whole bwa index must be
there to be reused, in either the `<reference>.*` or the `<reference>.64.*` naming that
`bwa index -6` produces. An incomplete set is rebuilt rather than copied.

## Run or submit

```console
# Submit with the defaults
deadline bundle submit .

# Review parameters in a GUI first
deadline bundle gui-submit .

# A fast smoke test: one sample, one region covering all the sample reads
deadline bundle submit . \
  -p Samples=tiny_n -p SampleRange=0 \
  -p Regions=1:131000-140999 -p RegionRange=0

# Your own cohort across whole chromosomes
deadline bundle submit . \
  -p ReadsDir=/data/cohort/reads \
  -p ReferenceDir=/data/refs \
  -p ReferenceFastaName=Homo_sapiens_assembly38.fasta \
  -p Samples=NA12878,NA12891,NA12892 -p SampleRange=0-2 \
  -p Regions=chr20,chr21,chr22 -p RegionRange=0-2
```

Download the results once the job finishes:

```console
deadline job download-output --job-id <job-id>
```

### Run it locally with the Open Job Description CLI

The [Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli) runs the template
without a farm, which is the fastest way to iterate. On a Linux or macOS host with the tools
available:

```console
# Validate the template and inspect the task graph
openjd check template.yaml
openjd summary template.yaml

# Run one sample and one region end to end, including the steps it depends on
openjd run template.yaml --step CallVariants --run-dependencies \
    -p Samples=tiny_n -p SampleRange=0 \
    -p Regions=1:131000-140999 -p RegionRange=0

# Run everything
openjd run template.yaml
```

Create the environment the tools come from with:

```console
conda create -n variant-calling -c conda-forge -c bioconda \
    bwa samtools bcftools fastqc multiqc
conda activate variant-calling
```

## Parameters and outputs

| Parameter | Default | Description |
|---|---|---|
| `ReadsDir` | `sample_inputs/reads` | Directory of `<sample>_R1.fastq.gz` / `_R2.fastq.gz` pairs |
| `ReferenceDir` | `sample_inputs/reference` | Directory holding the reference FASTA and any indexes beside it |
| `ReferenceFastaName` | `human_g1k_v37_decoy.small.fasta` | FASTA filename within the reference directory |
| `OutputDir` | `output` | Destination for all results |
| `Samples` | `tiny_n,tiny_t` | Comma-separated sample names to align in parallel |
| `SampleRange` | `0-1` | Which `Samples` entries to align, as indices from 0 |
| `Regions` | four windows of contig `1` | Comma-separated regions to call in parallel |
| `RegionRange` | `0-3` | Which `Regions` entries to call, as indices from 0 |
| `MinMappingQuality` | `20` | `bcftools mpileup -q` |
| `MinBaseQuality` | `20` | `bcftools mpileup -Q` |
| `Ploidy` | `2` | Ploidy preset for `bcftools call`; job-wide |
| `MinQual` | `20.0` | Discard called sites below this QUAL; 0 keeps everything |
| `MinDepth` | `5` | Discard called sites below this `INFO/DP`; 0 keeps everything |
| `CondaPackages` | `bwa samtools bcftools fastqc multiqc` | Packages the queue environment installs |
| `CondaChannels` | `conda-forge bioconda` | Channels, highest priority first |
| `RequiredTools` | `bwa,samtools,bcftools,fastqc,multiqc` | Commands `BioToolchain` requires on `PATH` |

Outputs, all under `OutputDir`:

| Path | Contents |
|---|---|
| `variants.vcf.gz` (+ `.tbi`) | The merged, deduplicated, normalized VCF, the main result |
| `variant_summary.txt` | Variant counts per contig and `bcftools stats` output |
| `vcf_by_region/region_NNNN_<region>.vcf.gz` | Per-region calls, one per scatter task |
| `alignments/<sample>.sorted.bam` (+ `.bai`) | Sorted alignments per sample |
| `alignments/<sample>.flagstat.txt` | Alignment summary per sample |
| `qc/` | FastQC reports per read file |
| `multiqc/multiqc_report.html` | Aggregate QC report |
| `reference/` | The reference plus its `.fai` and bwa indexes, assembled by `BuildIndex` |

### Bundled scripts

The shell for every step lives in [`scripts/`](scripts/), not inline in `template.yaml`, following
stage 2 of the [job development progression](../job_dev_progression/). At five steps and roughly
400 lines of shell this bundle is past the point where a self-contained template stays readable.

| Script | Runs as |
|---|---|
| `verify_toolchain.sh` | `BioToolchain` environment `onEnter` |
| `build_index.sh` | `BuildIndex` |
| `qc_sample.sh` | `QualityControl` |
| `align_sample.sh` | `AlignReads` |
| `call_region.sh` | `CallVariants` |
| `merge_variants.sh` | `MergeVariants` |
| `common.sh` | sourced by the others, never run directly |

A hidden `JobScriptDir` PATH parameter stages the directory. The tradeoff is that scripts in it
cannot use `{{Param.Name}}` substitution, since they are ordinary files rather than templated
embedded files. Values arrive as `--flag=value` arguments instead:

```yaml
args:
- '{{Param.JobScriptDir}}/call_region.sh'
- '--regions={{Param.Regions}}'
- '--region-index={{Task.Param.RegionIndex}}'
```

Each value is labeled rather than positional, because `call_region.sh` takes ten of them and an
unlabeled list of ten is easy to reorder by accident. Each script rejects an unrecognized flag and
names any required flag it did not receive, so a typo fails on the first task instead of silently
taking a default.

`common.sh` exists for one reason worth knowing: `call_region.sh` writes the per-region VCFs and
`merge_variants.sh` looks for them, so the two must derive the same filename. That derivation is
`region_vcf_path`, defined once and sourced by both, rather than duplicated with a comment asking
each copy to stay in step. `parse_list` is there for the same reason, since every script splits a
comma-separated parameter the same way.

Editing a script does not require touching the template, which also means `openjd run` picks up a
change with no re-submission.

### How steps pass files to each other

Each step runs in its own session on a worker, with its own session directory. That shapes how this
bundle is written, in two ways.

**Every path is derived from a job parameter, never passed between steps.** A path one step writes
down does not exist for the next, whose session directory is elsewhere. `BuildIndex` collects the
reference, its `.fai`, and the bwa index into `OutputDir/reference/`, and the later steps recompute
that location from the `OutputDir` and `ReferenceFastaName` parameters, which each session resolves
for itself.

**A `PATH` parameter stages exactly what it names.** Job attachments uploads the single path a
`FILE`-typed parameter points at and does not sweep in files beside it. That is why the reference is a
`ReferenceDir` directory plus a `ReferenceFastaName` filename rather than one `ReferenceFasta` file
parameter: a `.fai` or bwa index sitting next to the FASTA has to be inside a staged *directory* to
reach the worker at all, and without that, `BuildIndex`'s reuse branches could never fire on a real
submission.

**A step must declare every step whose output it reads.** A step's `dependencies` entitle it to those
steps' outputs, and the entitlement does not chain: given `A → B → C`, step `C` is not promised `A`'s
outputs without its own `dependsOn: A`. `CallVariants` lists both `AlignReads` and `BuildIndex`,
since it needs the BAMs as well as the reference index. `MergeVariants` lists all four earlier steps,
because its MultiQC report covers FastQC output and flagstat summaries as well as the VCFs it merges.

That entitlement is a lower bound: job attachments guarantees the declared inputs and depended-on
outputs are present, not that nothing else is. Extra files may well be there, since a reused session
leaves earlier state behind and one edge brings everything that step wrote. A step reading an
undeclared file can succeed by luck and fail later when scheduling differs, so declare what you read.

### Why the `...Range` parameters exist

A `jobtemplate-2023-09` task parameter range cannot be computed from the length of another parameter,
so `Samples` and `Regions` are each paired with a range that sizes the parameter space and has to be
kept in step with its list.

Each range must cover its whole list, so `SampleRange` and `RegionRange` are `0-1` and `0-3` to match
the default lists. Change a list and its range together.

A range reaching **past** the end of its list is safe: the extra tasks detect it and exit without
doing work. A range that **skips** an entry is not, and fails rather than producing a partial result:
`CallVariants` requires a BAM for every entry in `Samples` and `MergeVariants` a VCF for every entry
in `Regions`, and both name the missing entries and the range that would cover them. For the same
reason neither step globs the output directory for its inputs. Both build the expected filenames, so
files left by an earlier run cannot quietly join the result.

**To work on a subset, shorten the list rather than the range.** `OutputDir` is declared `dataFlow:
OUT`, so job attachments treats it as output only and a new job starts with it empty. A narrowed range
has no earlier results to combine with, so the gather insists on a complete set. Calling one region
means `-p Regions=1:137000-139999 -p RegionRange=0`, not `-p RegionRange=2`:

```console
deadline bundle submit . \
  -p Samples=tiny_n -p SampleRange=0 \
  -p Regions=1:137000-139999 -p RegionRange=0
```

Supporting a true incremental rerun (keeping earlier per-region VCFs and adding to them) needs
`OutputDir` declared `INOUT` so the prior results are staged back in. That is a deliberate design
choice rather than an oversight: `INOUT` uploads and re-downloads the whole output directory on every
run, and for a sample the simpler contract is worth more than incremental reruns.

A task parameter range is capped at 1024 elements, which is the real ceiling on the fan-out of either
axis.

### Scaling the region list past the parameter limit

A job parameter string is capped at 1024 characters, so `Regions` holds roughly 100 windows before it
runs out of room. A real whole-genome scatter wants more: 3-Mb windows over GRCh38 come to about a
thousand, which is also where the 1024-element range cap lands.

To go past that, keep the list in a file rather than a parameter. Add a `FILE`-typed `PATH` parameter
beside the existing ones, one region per line:

```yaml
- name: RegionsFile
  type: PATH
  objectType: FILE
  dataFlow: IN
  default: sample_inputs/regions.txt
  description: >
    One region per line, used instead of the Regions parameter when set. Lifts the
    roughly 100-entry ceiling that the 1024-character parameter limit imposes.
  userInterface:
    control: CHOOSE_INPUT_FILE
    label: Regions File
    groupLabel: Parallelism
```

Pass it to `call_region.sh` and `merge_variants.sh` as `--regions-file={{Param.RegionsFile}}`, and read
it in `common.sh` alongside the existing `parse_list`, so both steps still derive region names and the
per-region VCF filenames from one implementation:

```bash
# Read one region per line, ignoring blank lines and '#' comments.
read_region_file() {
  local -n _out="$1"
  local _path="$2" _line
  _out=()
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    _line="${_line%%#*}"
    _line="${_line#"${_line%%[![:space:]]*}"}"
    _line="${_line%"${_line##*[![:space:]]}"}"
    [[ -n "$_line" ]] && _out+=("$_line")
  done < "$_path"
}
```

`RegionRange` still has to cover the file's line count, so the range stays a parameter that must be
kept in step. Generating both from a `.fai` is the usual approach, since `cut -f1,2 <reference>.fai`
gives the contig lengths that windowing needs:

```console
# Write 3-Mb windows and report the range that covers them
awk 'BEGIN{OFS=""} {for (s=1; s<=$2; s+=3000000) {e=s+2999999; if (e>$2) e=$2; print $1,":",s,"-",e}}' \
    reference/human_g1k_v37_decoy.small.fasta.fai > sample_inputs/regions.txt
echo "RegionRange=0-$(( $(wc -l < sample_inputs/regions.txt) - 1 ))"
```

This bundle keeps the parameter form because a reader can see the whole scatter in the submission
command, and the sample data needs four windows. The file form is the change to make when the region
count outgrows what a parameter can carry.

The EXPR extension's
[`LIST[STRING]`](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#211-jobliststringparameterdefinition-extension-expr)
type removes the need for the paired range, at the cost of requiring an implementation that supports
the extension. No other sample here uses EXPR yet, so this bundle stays on the base 2023-09 schema.

## Security, cost, and cleanup

Running this job incurs Deadline Cloud worker, storage, and data transfer charges.

`fetch_test_data.py` downloads from a public, unauthenticated S3 bucket over HTTPS and writes only
inside `sample_inputs/`. Re-running it skips files that already exist. `--clean` removes them first.

Genomic sequence data is often subject to consent, privacy, and jurisdictional restrictions. Set
queue, S3, and farm access controls to match before pointing this bundle at real data, and prefer a
dedicated queue whose job attachments bucket has the encryption and access logging your data
governance requires.

The `output/` directory is excluded by this repository's `.gitignore`. Delete it to reclaim space.

## Troubleshooting

**The job fails immediately with "required tool ... is not on PATH."** The queue has no conda
queue environment, or its channels or packages are wrong. The error lists the exact values to set.

**`bcftools mpileup` reports an unknown region, or a region yields zero variants.** Region names
must match the reference exactly. GRCh37-style references name contigs `1`, `2`, `X`. GRCh38
references from UCSC and the GATK resource bundle name them `chr1`, `chr2`, `chrX`. Check with
`samtools faidx <reference> && cut -f1 <reference>.fai`.

**"no VCF for N of M requested region(s)" or "no alignment for N of M requested sample(s)."**
`RegionRange` or `SampleRange` does not cover its whole list, so some entries were never processed.
Both errors name the missing entries and the range that would cover them. If you narrowed a range
deliberately to redo part of a run, shorten the matching list instead. See
[Why the `...Range` parameters exist](#why-the-range-parameters-exist).

**A sample is missing from the VCF's sample columns.** `AlignReads` writes the sample name into the
BAM's `@RG` line, which is what `bcftools` reads. If you supply pre-aligned BAMs from another
pipeline, confirm they carry an `@RG` line with `SM:` set.

**Fewer variants than expected.** `MinQual` (default 20) and `MinDepth` (default 5) discard
low-confidence calls. On shallow data those defaults can remove most sites; set both to 0 to see the
unfiltered output, and read the counts `CallVariants` logs per region.

**`bcftools index` fails with a compression error.** The index requires BGZF-compressed input, not
plain gzip. `bcftools call --output-type z` produces BGZF, so this only arises if you substitute
your own compression step.

**A reference contig longer than 512 Mb fails to index.** Both `CallVariants` and `MergeVariants`
index with `--tbi`, whose format caps contig length at 2^29 bases. Every human chromosome fits
comfortably, but some plant and amphibian genomes do not; switch those to CSI by replacing `--tbi`
with `--csi` in both steps.

Worker logs for a failed task are available through the Deadline Cloud monitor, or with
`deadline job logs --job-id <job-id>`, which also accepts `--session-id` to narrow the output to one
step. See the
[log retrieval guidance](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/view-logs.html).

While iterating, submit with `--max-retries-per-task 0` so a broken step fails once instead of
retrying before the job gives up.

## Related job bundles

* [ESMFold protein structure prediction](../esmfold_predict/): GPU bioinformatics, FASTA to PDB
* [GROMACS molecular dynamics](../gromacs_md/): multi-stage simulation with replica fan-out
* [AutoDock Vina virtual screening](../virtual_screening_vina/): chunked molecular docking
* [Monte Carlo simulation](../monte_carlo_simulation/): the fan-out/fan-in pattern with task chunking

## Related resources

* [bioconda](https://bioconda.github.io/): channel setup and the package index
* [Open Job Description step parameter space definitions](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#34-stepparameterspacedefinition)
