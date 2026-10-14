# Custom submitters

Custom submitters run inside a DCC application and create Deadline Cloud jobs from the open scene. Use one
as a starting point when you need submission behavior that a static job bundle and
`deadline bundle gui-submit` do not cover.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [FuzzyPixel Maya](fuzzypixel_maya/) | A PyQt submitter with a reorganized interface, render layer controls, and fleet attribute selection | You need a Maya submission UI shaped around your studio's workflow |
| [KeyShot](keyshot/) | A KeyShot script that packages the scene and assets, and a job that keeps KeyShot open across frames | You submit KeyShot scenes from inside KeyShot Studio |
