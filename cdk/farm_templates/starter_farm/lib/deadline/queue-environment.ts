// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as fs from 'node:fs';

import { CondaChannel } from './conda-channel';

/**
 * The maximum length AWS Deadline Cloud accepts for a serialized queue
 * environment template (API model shape `EnvironmentTemplate`).
 *
 * Checked at synth time so an over-long template fails during `cdk synth`
 * rather than during `CreateQueueEnvironment` partway through a deployment.
 */
export const ENVIRONMENT_TEMPLATE_MAX_CHARS = 15000;

/**
 * Something that can be added to a {@link Queue} with
 * {@link Queue.addEnvironment}.
 *
 * A queue environment is an
 * {@link https://github.com/OpenJobDescription/openjd-specifications/wiki Open Job Description}
 * environment template that runs before the steps of every job in the queue --
 * to install software, mount a file system, or set environment variables.
 * Anything exposing the template as YAML can be one, so a farm can add its own
 * without subclassing anything here.
 */
export interface IQueueEnvironment {
  /** The OpenJD environment template, as a YAML document. */
  readonly templateYaml: string;
}

/**
 * A queue environment read from an OpenJD environment template file.
 *
 * Keeping the template in its own file, rather than a string in TypeScript,
 * means `openjd check` can validate it directly.
 */
export class QueueEnvironmentFile implements IQueueEnvironment {
  /** The OpenJD environment template, as a YAML document. */
  public readonly templateYaml: string;

  /**
   * @param templatePath the path to the YAML environment template, read at
   * synth time.
   */
  constructor(templatePath: string) {
    this.templateYaml = fs.readFileSync(templatePath, 'utf-8');
    assertWithinServiceLimit(this.templateYaml.length, templatePath);
  }
}

export interface CondaQueueEnvironmentProps {
  /**
   * The channels jobs install Conda packages from, in order of preference.
   *
   * Pass a {@link CondaChannel} for the farm's own packages and a string for a
   * named public channel: `'deadline-cloud'` for the
   * {@link https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment applications Deadline Cloud provides},
   * or `'conda-forge'` for the {@link https://conda-forge.org/ conda-forge community} packages.
   *
   * A job can override this per submission with the `CondaChannels` parameter.
   */
  readonly channels: readonly (CondaChannel | string)[];
  /**
   * The path to the OpenJD environment template to render.
   *
   * @default the `conda_queue_env_inline_improved_caching.yaml` shipped beside
   * this app
   */
  readonly templatePath?: string;
}

/**
 * A queue environment that installs the Conda packages a job asks for.
 *
 * Jobs name the applications they need in the `CondaPackages` parameter, and
 * this environment creates and activates a Conda virtual environment holding
 * them before the job's steps run. It comes from
 * {@link https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/queue_environments the shared queue environment sample}
 * of the same name, with the default channel list pointed at this farm's
 * {@link channels}.
 *
 * The queue's role needs read access to any {@link CondaChannel} in that list;
 * grant it with {@link CondaChannel.grantRead}.
 */
export class CondaQueueEnvironment implements IQueueEnvironment {
  /** The OpenJD environment template, as a YAML document. */
  public readonly templateYaml: string;
  /** The channels jobs install packages from by default. */
  public readonly channels: readonly (CondaChannel | string)[];

  constructor(props: CondaQueueEnvironmentProps) {
    if (props.channels.length === 0) {
      throw new Error(
        'A Conda queue environment needs at least one channel to install packages ' +
          "from. Pass the farm's CondaChannel, 'deadline-cloud', or both.",
      );
    }

    this.channels = props.channels;
    const templatePath = props.templatePath ?? DEFAULT_CONDA_TEMPLATE_PATH;
    this.templateYaml = renderChannels(fs.readFileSync(templatePath, 'utf-8'), props.channels);

    // A CondaChannel URL embeds its bucket name, which is usually an unresolved
    // token at synth time and shorter than the name it resolves to. Add the
    // growth from the token to the longest name S3 allows, so the estimate stays
    // conservative. The channel's prefix and name need no adjustment: they are
    // literal in the rendered URL and so already counted. `Math.max` guards the
    // case of a bucket whose synth-time name is already at least that long,
    // where the resolved template is no longer than the rendered one.
    const worstCaseLength = this.channels.reduce(
      (length, channel) =>
        typeof channel === 'string'
          ? length
          : length +
            Math.max(0, MAX_S3_BUCKET_NAME_LENGTH - channel.bucket.bucketName.length),
      this.templateYaml.length,
    );
    assertWithinServiceLimit(worstCaseLength, templatePath);
  }
}

/** The Conda environment template shipped beside this app. */
const DEFAULT_CONDA_TEMPLATE_PATH = `${__dirname}/../../conda_queue_env_inline_improved_caching.yaml`;

/** The longest bucket name Amazon S3 allows. */
const MAX_S3_BUCKET_NAME_LENGTH = 63;

/**
 * The placeholder the shared queue environment samples use for their default
 * channel list.
 *
 * Rewriting it, rather than templating the file, keeps the app's copy
 * byte-identical to `queue_environments/conda_queue_env_inline_improved_caching.yaml`
 * so a fix to one is a fix to both.
 */
const CHANNELS_PLACEHOLDER = 'default: "deadline-cloud"';

/** Point the template's default `CondaChannels` value at the given channels. */
function renderChannels(
  template: string,
  channels: readonly (CondaChannel | string)[],
): string {
  if (!template.includes(CHANNELS_PLACEHOLDER)) {
    throw new Error(
      `The Conda queue environment template does not contain ` +
        `${JSON.stringify(CHANNELS_PLACEHOLDER)}, so its default CondaChannels value ` +
        'cannot be set. Has the queue environment template changed?',
    );
  }

  const urls = channels.map((channel) =>
    typeof channel === 'string' ? channel : channel.url,
  );
  // A function replacer, so the channel list is substituted verbatim. Passing a
  // string would let a `$&` or `$1` sequence in a channel name expand into the
  // matched text and silently corrupt the rendered template; S3 keys allow `$`.
  return template.replace(
    CHANNELS_PLACEHOLDER,
    () => `default: ${JSON.stringify(urls.join(' '))}`,
  );
}

/** Fail synth if a template would exceed what the service accepts. */
function assertWithinServiceLimit(length: number, templatePath: string): void {
  if (length > ENVIRONMENT_TEMPLATE_MAX_CHARS) {
    throw new Error(
      `The queue environment template ${templatePath} renders to as many as ${length} ` +
        `characters, which exceeds the AWS Deadline Cloud EnvironmentTemplate limit of ` +
        `${ENVIRONMENT_TEMPLATE_MAX_CHARS}. Shorten the template or the channel list.`,
    );
  }
}
