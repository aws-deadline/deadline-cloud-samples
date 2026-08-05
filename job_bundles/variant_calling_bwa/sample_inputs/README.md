# Sample inputs

The data this sample runs on is downloaded rather than committed, because test data is better
fetched from its upstream source than vendored. A `.gitignore` in this directory keeps the
downloads out of version control.

```console
python fetch_test_data.py
```

That writes about 950 KB:

```
reads/
  tiny_n_R1.fastq.gz   tiny_n_R2.fastq.gz    # "normal" library
  tiny_t_R1.fastq.gz   tiny_t_R2.fastq.gz    # "tumor" library
reference/
  human_g1k_v37_decoy.small.fasta            # 6-contig GRCh37 subset
  human_g1k_v37_decoy.small.fasta.fai
```

The read sets are the normal and tumor libraries of a synthetic pair, but because this sample does no
somatic calling, they act as two independent samples to fan out over.

The reference uses GRCh37-style contig naming with no `chr` prefix, and `fetch_test_data.py` prints the
contig names once the download finishes. The reads align to only part of contig `1`, so the job
template's default `Regions` is a set of windows of that contig rather than the contig names.

Only lane `L001` of each library is downloaded. The upstream location also has `L002`, if you want
roughly twice the reads.

## Provenance

The reads and reference are provided by
[AWS HealthOmics for their tutorials](https://github.com/aws-samples/aws-healthomics-tutorials),
hosted in the public, unauthenticated `aws-genomics-static-us-east-1` bucket under
`omics-data/test-datasets/nf-core-sarek/`. The data originates from
[nf-core/test-datasets](https://github.com/nf-core/test-datasets) and is MIT licensed. A copy of
that license is in the bucket alongside the data.

`fetch_test_data.py --clean` removes what it previously downloaded before fetching again.
