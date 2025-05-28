# V-Ray sample job bundle
Use this job bundle to create a V-Ray job to use with AWS Deadline Cloud. \
Read more about job bundle and how to use it with AWS Deadline Cloud [here](../README.md). \
Read more about how to customize this job bundle bellow

## Prerequisite
- Have V-Ray conda package host on a conda channel. \
Read more about how to create V-Ray conda package [here](../../conda_recipes/vray/README.md)
- Have a sample `.vrscene` and its dependencies files. For example the [Chaos ENVISION documentation samples](https://docs.chaos.com/display/ENVISION/Sample+Scenes) include vrscene files as part of Sample Scene 01.

## Job submission

To submit using a GUI submission dialog, run this command:

```sh
$ deadline bundle gui-submit vray_render
```

To submit one of the Chaos ENVISION sample files from the CLI, run commands like:

```sh
$ SAMPLE_DIR=/path/to/sample
$ deadline bundle submit vray_render \
    -p VraySceneFile="$SAMPLE_DIR"/Building.vrscene \
    -p InputAssetDir="$SAMPLE_DIR"/Building.data
```

## Job bundle customization
- All available customization flags could be found on [Chaos guide](https://docs.chaos.com/display/VNS/V-Ray+Standalone+Command+Line+Options) to tailor this job bundle
- Sample command line for V-Ray could be found on [Chaos example](https://docs.chaos.com/display/VNS/Getting+Started+with+Commands)
