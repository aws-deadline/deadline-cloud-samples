# Architecture diagram source

`vfx_pipeline_architecture.drawio` is the editable source for
[`../../../.images/vfx_pipeline_architecture.png`](../../../.images/vfx_pipeline_architecture.png),
shown at the top of the sample's [README](../README.md).

It is a [draw.io](https://www.drawio.com/) / diagrams.net document. Every shape
and arrow is hand-placed at fixed coordinates (there is no auto-layout), so
editing is deliberate: move a box by changing its `mxGeometry`, reroute an arrow
by editing its waypoints.

## Edit

Open `vfx_pipeline_architecture.drawio` in the draw.io desktop app or at
[app.diagrams.net](https://app.diagrams.net), or hand-edit the XML.

## Regenerate the PNG

With the draw.io desktop app installed (`brew install --cask drawio`), export
headlessly from this directory:

```bash
/Applications/draw.io.app/Contents/MacOS/draw.io \
  --export --format png --scale 2 --border 10 \
  -o ../../../.images/vfx_pipeline_architecture.png \
  vfx_pipeline_architecture.drawio
```

`--scale 2` gives a crisp ~3300px-wide image. `--border 10` adds a small margin.

## Conventions

- Icons use the built-in AWS 2019 shape library (`mxgraph.aws4.*`): S3 for the
  bucket and shared storage, Deadline Cloud for the queue, EC2 for the worker,
  and the user shape for the artist workstation.
- Edge colours are a legend without a legend box:
  blue = asset/file movement, orange = job submission, grey dashed = scheduling
  (control plane), purple = the on-worker step graph and publish, green = results
  coming home.
- The main flow is one left-to-right band (workstation → S3 → queue → worker →
  step graph → Autodesk Flow); the two green return arrows ride a dedicated lower
  lane so they never cross the forward arrows.
