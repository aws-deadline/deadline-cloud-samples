# Using Files in Your Jobs

Many of the jobs that you submit to AWS Deadline Cloud will have input and output in the form
of files. Your input files and output directories may be located on a combination of your shared filesystems
and local drive. Your jobs require a way to locate the content in those locations. Deadline Cloud's
[job attachments](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-job-attachments.html) and
[storage profiles](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-shared.html) features work
in concert to help your jobs locate the files that they need.

Deadline Cloud's job attachments feature helps you move files to your worker hosts from filesystem locations on your
workstation that are not available on your worker hosts, and vice versa. It shuttles files between hosts using
[Amazon S3](https://aws.amazon.com/pm/serv-s3/) as an intermediary. Job attachments can be enabled individually
on each of your queues to make it available to jobs in those queues. You will primarily be using 
job attachments to manage the input and output files of your jobs when you are using Deadline Cloud's 
[service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html), but
the feature is also available to use with your 
[customer-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-cmf.html).

You use Deadline Cloud's storage profiles to model the layout of shared filesystem locations on your workstation and
worker hosts. This helps your jobs locate shared files and directories when their locations differ between your workstation
and worker hosts, such as in cross-platform setups with Windows based workstations and Linux based worker hosts.
Storage profile's model of your filesystem configuration is also leveraged by job attachments to identify which files
it needs to shuttle between hosts through Amazon S3.

Note that if you are not using Deadline Cloud's job attachments feature, and you do not need to remap file and
directory locations between workstations and worker hosts then you do not need to model your fileshares with
storage profiles.

## 1. Sample Project Infrastructure

For the purpose of demonstration, consider the following hypothetical infrastructure that is set up to
support two separate projects. To follow along, set up a farm, fleet, and two queues using the console for
AWS Deadline Cloud and then be sure to delete these resources when you are done:

1. [Farm](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/farms.html#create-farm):
    1. Named: `AssetDemoFarm`
    2. All other settings default.
2. Two [queues](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue.html):
    1. The first is for jobs for only the first of the two projects:
        1. Named: `Q1`.
        2. Job attachments: Create a new Amazon S3 bucket.
        3. Association with customer-managed fleets: Enabled.
        4. Run as user configuration: `jobuser` as both the user name and group name for POSIX credentials.
        5. Queue service role: Create a new role the name `AssetDemoFarm-Q1-Role`
        6. Default Conda queue environment: Unselect the checkbox for the default queue environment.
        7. All other settings default.
    2. The second is for jobs for only the second of the two projects:
        1. Named: `Q2`.
        2. Job attachments: Create a new Amazon S3 bucket.
        3. Association with customer-managed fleets: Enabled.
        4. Run as user configuration: `jobuser` as both the user name and group name for POSIX credentials.
        5. Queue service role: Create a new role with the name `AssetDemoFarm-Q2-Role`
        6. Default Conda queue environment: Unselect the checkbox for the default queue environment.
        7. All other settings default.
3. A single customer-managed [Fleet](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-a-cmf.html)
   that will run the jobs from both queues:
    1. Named: `Fleet`
    2. Fleet type: Customer-managed.
    3. Fleet service role: Create a new role with a name of your choosing. e.g. `AssetDemoFarm-Fleet-Role`
    4. All other settings default. Importantly, do not associate the fleet with any queues at this time.

This hypothetical infrastructure has three filesystem locations that are shared between hosts via network fileshares. We
refer to these locations by the following names:

1. `FSComm` - Containing input job assets that are common to both projects.
2. `FS1` - Containing input and output job assets for project 1.
3. `FS3` - Containing input and output job assets for project 2.

The infrastructure has three workstation configurations that we'll refer to as `WS1`, `WS2`, and `WSAll`:

1. `WSAll` - A Linux-based workstation set up for developers to assist with all projects. The shared filesystem locations are:
    1. `FSComm`: `/shared/common`
    2. `FS1`: `/shared/projects/project1`
    3. `FS2`: `/shared/projects/project2`
2. `WS1` - A Windows-based workstation set up to work on only project 1. The shared filesystem locations are:
    1. `FSComm`: `S:\`
    2. `FS1`: `Z:\`
    3. `FS2`: Not available
3. `WS2` - A MacOS-based workstation set up to work on only project 2. The shared filesystem locations are:
    1. `FSComm`: `/Volumes/common`
    2. `FS1`: Not available
    3. `FS2`: `/Volumes/projects/project2`

Finally, we'll refer to the fleet's worker configuration as `WorkerCfg`. The shared filesystem locations for `WorkerCfg` are:

1. `FSComm`: `/mnt/common`
2. `FS1`: `/mnt/projects/project1`
3. `FS2`: `/mnt/projects/project2`

Note that you do not need to set up any shared filesystems, workstations, or workers that match this configuration to follow along.
We will be modeling these shared locations, but they do not need to exist to be modeled.

## 2. Storage Profiles and Path Mapping

You use AWS Deadline Cloud's storage profiles to model the filesystems on your workstation and worker hosts.
Each storage profile describes the operating system and filesystem layout of one of your system configurations.
This chapter describes how you can use storage profiles to model the filesystem configurations of your hosts so that
Deadline Cloud can automatically generate path mapping rules for your jobs, and how those path mapping rules
are generated from your storage profiles.

When you submit a job to Deadline Cloud you can optionally provide a storage profile id for that job. This storage
profile is the submitting workstation's profile and describes the filesystem configuration that the file paths in
the job's input and output file references are written for. 

You can also associate a storage profile with a [customer managed fleet](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-cmf.html).
That storage profile describes the filesystem configuration of all worker hosts in that fleet. If you have
workers with different filesystem configurations, then those workers must be assigned to different fleets in your
farm. Storage profiles are not supported in [service managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html).

Path mapping rules describe how paths should be remapped from how they are specified in the job to the
path's actual location on a worker host. Deadline Cloud compares the filesystem configuration described
in a job's storage profile with the storage profile of the fleet that is running the job to derive these
path mapping rules.

### 2.1. Modeling Your Shared Filesystem Locations with Storage Profiles

A storage profile models the filesystem configuration of one of your host configurations. There are four different host configurations in
the [sample project infrastructure](#1-sample-project-infrastructure), so we will create a separate storage profile for each. You can create
a storage profile with the [CreateStorageProfile API](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_CreateStorageProfile.html),
[AWS::Deadline::StorageProfile](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-deadline-storageprofile.html)
[AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) resource, or 
[AWS Console](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-shared.html#storage-profile). 

A Storage Profile is made up of a list of filesystem locations that each tell Deadline Cloud the location and type of a filesystem
location that is relevant for jobs submitted from or run on a host. A storage profile should only model the locations that are
relevant for jobs. For example, the shared `FSComm` location is located on workstation `WS1` at `S:\`, so the corresponding
filesystem location is:

```json
{
    "name": "FSComm",
    "path": "S:\\",
    "type": "SHARED"
}
```

Now, create the storage profile for workstation configurations `WS1`, `WS2`, and `WS3` and the worker configuration `WorkerCfg`
using the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) in
[AWS CloudShell](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html):

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff

aws deadline create-storage-profile --farm-id $FARM_ID \
  --display-name WSAll \
  --os-family LINUX \
  --file-system-locations \
  '[
      {"name": "FSComm", "type":"SHARED", "path":"/shared/common"},
      {"name": "FS1", "type":"SHARED", "path":"/shared/projects/project1"},
      {"name": "FS2", "type":"SHARED", "path":"/shared/projects/project2"}
  ]'

aws deadline create-storage-profile --farm-id $FARM_ID \
  --display-name WS1 \
  --os-family WINDOWS \
  --file-system-locations \
  '[
      {"name": "FSComm", "type":"SHARED", "path":"S:\\"},
      {"name": "FS1", "type":"SHARED", "path":"Z:\\"}
   ]'

aws deadline create-storage-profile --farm-id $FARM_ID \
  --display-name WS2 \
  --os-family MACOS \
  --file-system-locations \
  '[
      {"name": "FSComm", "type":"SHARED", "path":"/Volumes/common"},
      {"name": "FS2", "type":"SHARED", "path":"/Volumes/projects/project2"}
  ]'

aws deadline create-storage-profile --farm-id $FARM_ID \
  --display-name WorkerCfg \
  --os-family LINUX \
  --file-system-locations \
  '[
      {"name": "FSComm", "type":"SHARED", "path":"/mnt/common"},
      {"name": "FS1", "type":"SHARED", "path":"/mnt/projects/project1"},
      {"name": "FS2", "type":"SHARED", "path":"/mnt/projects/project2"}
  ]'
```

> **IMPORTANT NOTE**: It is essential that the file system locations in your storage profiles are referenced using the same values
for the `name` property across all storage profiles in your farm. Deadline Cloud compares these names to determine whether
filesystem locations from different storage profiles are referencing the same location when generating path mapping rules.

### 2.2. Configuring Storage Profiles for Fleets

A customer-managed fleet's configuration can include a storage profile that models the filesystem locations on all
workers in that fleet. The host filesystem configuration of all workers in a fleet must match their fleet's storage
profile. Workers with different filesystem configurations must be in separate fleets.

Update your fleet's configuration to set its storage profile to the `WorkerCfg` storage profile using the
[AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) in
[AWS CloudShell](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html):

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of FLEET_ID to your fleet's identifier
FLEET_ID=fleet-00112233445566778899aabbccddeeff
# Change the value of WORKER_CFG_ID to your storage profile named WorkerCfg
WORKER_CFG_ID=sp-00112233445566778899aabbccddeeff

FLEET_WORKER_MODE=$( \
  aws deadline get-fleet --farm-id $FARM_ID --fleet-id $FLEET_ID \
    --query 'configuration.customerManaged.mode' \
)
FLEET_WORKER_CAPABILITIES=$( \
  aws deadline get-fleet --farm-id $FARM_ID --fleet-id $FLEET_ID \
    --query 'configuration.customerManaged.workerCapabilities' \
)

aws deadline update-fleet --farm-id $FARM_ID --fleet-id $FLEET_ID \
  --configuration \
  "{
    \"customerManaged\": {
      \"storageProfileId\": \"$WORKER_CFG_ID\",
      \"mode\": $FLEET_WORKER_MODE,
      \"workerCapabilities\": $FLEET_WORKER_CAPABILITIES
    }
  }"
```

### 2.3. Storage Profiles for Queues

A queue's configuration includes a list of case-sensitive names of the shared filesystem locations that jobs submitted to the queue
require access to. In the sample infrastructure, jobs submitted to queue `Q1` require filesystem locations `FSComm` and `FS1`, and
jobs submitted to queue `Q2` require filesystem locations `FSComm` and `FS2`. Update the queue's configurations to require these
filesystem locations:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of QUEUE2_ID to queue Q2's identifier
QUEUE2_ID=queue-00112233445566778899aabbccddeeff

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
  --required-file-system-location-names-to-add FSComm FS1

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE2_ID \
  --required-file-system-location-names-to-add FSComm FS2
```

Note that if a queue has any required filesystem locations, then that queue cannot be associated with a
[service-managed fleet](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html) because
that fleet has no way to mount your shared filesystems.

A queue's configuration also includes a list of allowed storage profiles that applies to jobs submitted to
and fleets associated with that queue. Only storage profiles that define filesystem locations for all of the required filesystem
locations of that queue are allowed in the queue's list of allowed storage profiles. 

Submitting a job with a storage profile other than one in the list of allowed storage profiles for a queue will fail. A job with
no storage profile can always be submitted to a queue.
The workstation configurations labeled `WSAll` and `WS1` both have the required filesystem locations (`FSComm` and `FS1`) for queue `Q1`
and need to be allowed to submit jobs to the queue. Similarly, workstation configurations `WSAll` and `WS2` meet the requirements for 
queue `Q2` and need to be allowed to submit jobs to that queue. So, update both queue's configurations to allow jobs to be submitted
with these storage profiles:

```bash
# Change the value of WSALL_ID to the identifier of the WSALL storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff
# Change the value of WS1 to the identifier of the WS1 storage profile
WS1_ID=sp-00112233445566778899aabbccddeeff
# Change the value of WS2 to the identifier of the WS2 storage profile
WS2_ID=sp-00112233445566778899aabbccddeeff

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
  --allowed-storage-profile-ids-to-add $WSALL_ID $WS1_ID

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE2_ID \
  --allowed-storage-profile-ids-to-add $WSALL_ID $WS2_ID
```

If you were to try to add the `WS2` storage profile to the list of allowed storage profiles for queue `Q1` then it would fail:

```bash
$ aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
  --allowed-storage-profile-ids-to-add $WS2_ID

An error occurred (ValidationException) when calling the UpdateQueue operation: Storage profile id: sp-00112233445566778899aabbccddeeff does not have required file system location: FS1
```

This is because the `WS2` storage profile does not contain a definition for the filesystem location named `FS1` that queue `Q1` requires.

Associating a fleet that is configured with a storage profile that is not in the queue's list of allowed storage profiles will also fail. For example:

```bash
$ aws deadline create-queue-fleet-association --farm-id $FARM_ID \
   --fleet-id $FLEET_ID \
   --queue-id $QUEUE1_ID

An error occurred (ValidationException) when calling the CreateQueueFleetAssociation operation: Mismatch between storage profile ids.
```

So, add the storage profile named `WorkerCfg` to the lists of allowed storage profiles for both queue `Q1` and queue `Q2` and then associate
the fleet with these queues so that workers in the fleet can run jobs from both queues.

```bash
# Change the value of FLEET_ID to your fleet's identifier
FLEET_ID=fleet-00112233445566778899aabbccddeeff
# Change the value of WORKER_CFG_ID to your storage profile named WorkerCfg
WORKER_CFG_ID=sp-00112233445566778899aabbccddeeff

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
  --allowed-storage-profile-ids-to-add $WORKER_CFG_ID

aws deadline update-queue --farm-id $FARM_ID --queue-id $QUEUE2_ID \
  --allowed-storage-profile-ids-to-add $WORKER_CFG_ID

aws deadline create-queue-fleet-association --farm-id $FARM_ID \
  --fleet-id $FLEET_ID \
  --queue-id $QUEUE1_ID

aws deadline create-queue-fleet-association --farm-id $FARM_ID \
  --fleet-id $FLEET_ID \
  --queue-id $QUEUE2_ID
```

### 2.4. Deriving Path Mapping Rules from Storage Profiles

Path mapping rules describe how paths should be remapped from how they are specified in the job to the
path's actual location on a worker host. When a task from a job is running on a worker, the storage
profile that the job was submitted with is compared to the storage profile of the worker's fleet to
derive the path mapping rules that are given to the task. 

A mapping rule is created for each of the required filesystem locations in the queue's configuration.
For instance, a job submitted with the `WSAll` storage profile to queue `Q1` in the sample infrastructure
will have the path mapping rules:

1. `FSComm`: `/shared/common -> /mnt/common`
2. `FS1`: `/shared/projects/project1 -> /mnt/projects/project1`

Rules are created for the `FSComm` and `FS1` filesystem locations, but not the `FS2`
filesystem location even though both the `WSAll` and `WorkerCfg` storage profiles define filesystem
locations for `FS2`. This is because queue `Q1`'s list of required filesystem locations is `["FSComm", "FS1"]`.

You can confirm the path mapping rules that are available to jobs submitted with a particular
storage profile by submitting a job that prints out 
[Open Job Description's path mapping rules file](https://github.com/OpenJobDescription/openjd-specifications/wiki/How-Jobs-Are-Run#path-mapping),
and then reading the session log after the job has completed:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of WSALL_ID to the identifier of the WSALL storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

aws deadline create-job --farm-id $FARM_ID --queue-id $QUEUE1_ID \
  --priority 50 \
  --storage-profile-id $WSALL_ID \
  --template-type JSON --template \
  '{
    "specificationVersion": "jobtemplate-2023-09",
    "name": "DemoPathMapping",
    "steps": [
      {
        "name": "ShowPathMappingRules",
        "script": {
          "actions": {
            "onRun": {
              "command": "/bin/cat",
              "args": [ "{{Session.PathMappingRulesFile}}" ]
            }
          }
        }
      }
    ]
  }'
```

Note that if you are using the [Dealine Cloud CLI](https://pypi.org/project/deadline/) to submit jobs that its
configuration's `settings.storage_profile_id` setting dictates the storage profile that jobs submitted with
the CLI will have. To submit jobs with the `WSAll` storage profile, set:

```bash
deadline config set settings.storage_profile_id $WSALL_ID
```

To run a customer-managed worker as though it was running in the sample infrastructure, follow the
directions from the [Deadline Cloud User Guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/run-worker.html)
on running a worker within AWS CloudShell. If you have run those instructions before, then delete the `~/demoenv-logs`
and `~/demoenv-persist` directories first. Also, set the values of the `DEV_FARM_ID` and `DEV_CMF_ID` environment variables
that the directions reference as follows before doing so:

```bash
DEV_FARM_ID=$FARM_ID
DEV_CMF_ID=$FLEET_ID
```

Once the job is run, look at the job's log file to see the path mapping rules printed out:

```bash
cat demoenv-logs/${QUEUE1_ID}/*.log
...
2024-07-14 20:46:09,446 INFO {"version": "pathmapping-1.0", "path_mapping_rules": [{"source_path_format": "POSIX", "source_path": "/shared/projects/project1", "destination_path": "/mnt/projects/project1"}, {"source_path_format": "POSIX", "source_path": "/shared/common", "destination_path": "/mnt/common"}]}
...
```

Reformatting for readability, this contains remaps for both the `FS1` and `FSComm` filesystems as expected:

```json
{
    "version": "pathmapping-1.0",
    "path_mapping_rules": [
        {
            "source_path_format": "POSIX",
            "source_path": "/shared/projects/project1",
            "destination_path": "/mnt/projects/project1"
        },
        {
            "source_path_format": "POSIX",
            "source_path": "/shared/common",
            "destination_path": "/mnt/common"
        }
    ]
}
```

Submit jobs with different storage profiles to see the changes in the path mapping rules.

## 3. Job Attachments

AWS Deadline Cloud's [job attachments](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-job-attachments.html)
feature is available for you to make files that are not in shared filesystem locations available for your jobs, and to capture
the file outputs of jobs when those files are not written to shared filesystem locations. The job attachments feature
shuttles files betweeen hosts by using Amazon S3 as an intermediary, and stores these files in S3 in a way that
eliminates the need to re-upload a file if its content exactly matches a previously uploaded file.

Job attachments are essential when running jobs on [service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html)
since there are no filesystem locations that are shared between hosts on this kind of fleet. It is also useful for
use with [customer-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-cmf.html) when you
do not want all of a job's input and/or output files to be stored on a shared network filesystem, such as when your 
[job bundle](README) contains shell or Python script files that the job runs.

When using a job bundle to submit a job, either using the [Deadline Cloud CLI](https://pypi.org/project/deadline/)
or a Deadline Cloud submitter, the Deadline Cloud's job attachments feature uses a job's storage profile
and the queue's required filesystem locations to identify the input files that will not be available on a worker host, and
thus should be uploaded to Amazon S3 as part of job submission. Similarly, these same storage profiles help Deadline Cloud
identify which of a job's output files are in locations that will not be available on your workstation and need to
be uploaded to Amazon S3.

This guide to job attachments uses the farm, fleet, queues, and storage profiles configurations as described in the
[sample project infrastructure](#1-sample-project-infrastructure) and [sections describing storage profiles](#2-storage-profiles-and-path-mapping).
We recommend going through those sections before this one.

For this guide, you will use one of Dealine Cloud's sample job bundles as a starting point, and modify it to
explore job attachment's functionality as you go through the subsections. [Job bundles](README) are the best way to formulate
your jobs for use with job attachments. They encapsulate an
[Open Job Description](https://github.com/OpenJobDescription/openjd-specifications/wiki) Job Template in a directory with
additional files that list the files and directories required by jobs that are submitted using the job bundle.
If you are not familiar with job bundles, then we recommend going through the [job bundles README](README) to
learn more before proceeding.

### 3.1. Submitting Files with a Job

AWS Deadline Cloud's job attachment feature enables job workflows where some, or all, of a job's input files
are not available in filesystem locations that are shared to your worker hosts. Such as when running jobs
in a service-managed fleet, or when those files only exist on your workstation's local drive. When you submit a
job using a job bundle, that job bundle can include lists of the input files and directories that the job needs to
run. Deadline Cloud's job attachments feature will identify which of these input files are not located in shared filesystem
locations that will be available on the worker host where the job runs, uploads those files to Amazon S3, and then
downloads them to the worker host when the job is run. This section demonstrates how job attachments
identifies the files to upload, how those files are organized in Amazon S3, and how they are made available
on worker hosts for your jobs to use.

#### 3.1.1. What Job Attachments Uploads to Amazon S3

Start by cloning the [Deadline Cloud samples GitHub repository](https://github.com/aws-deadline/deadline-cloud-samples) into your 
[AWS CloudShell](https://docs.aws.amazon.com/cloudshell/latest/userguide/welcome.html) environment, and copying the
`job_attachments_devguide` job bundle into your home directory:

```bash
git clone https://github.com/aws-deadline/deadline-cloud-samples.git
cp -r deadline-cloud-samples/job_bundles/job_attachments_devguide ~/
```

The [Deadline Cloud CLI](https://pypi.org/project/deadline/) is used to submit job bundles, so install that as well:

```bash
pip install deadline --upgrade
```

The `job_attachments_devguide` job bundle has a single step with one task that runs a bash shell script whose filesystem
location is passed as a job parameter. The job parameter's definition is:

```yaml
...
- name: ScriptFile
  type: PATH
  default: script.sh
  dataFlow: IN
  objectType: FILE
...
```

The `dataFlow` property's `IN` value tells job attachments that the value of the `ScriptFile` parameter should be treated as
an input to the job. The value of the `default` property is a relative location to the job bundle's directory, but can also be an absolute
path. This parameter definition declares the `script.sh` file in the job bundle's directory is an input file that is required
for this job to run.

Next, ensure that the Deadline Cloud CLI does not have a storage profile configured and submit the job to queue `Q1`:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff

deadline config set settings.storage_profile_id ''

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID job_attachments_devguide/
```

The output from the Deadline Cloud CLI when this command is run looks like:

```
Submitting to Queue: Q1
...
Hashing Attachments  [####################################]  100%
Hashing Summary:
    Processed 1 file totaling 39.0 B.
    Skipped re-processing 0 files totaling 0.0 B.
    Total processing time of 0.0327 seconds at 1.19 KB/s.

Uploading Attachments  [####################################]  100%
Upload Summary:
    Processed 1 file totaling 39.0 B.
    Skipped re-processing 0 files totaling 0.0 B.
    Total processing time of 0.25639 seconds at 152.0 B/s.

Waiting for Job to be created...
Submitted job bundle:
   job_attachments_devguide/
Job creation completed successfully
job-74148c13342e4514b63c7a7518657005
```

Two things happened here. First the `script.sh` file was hashed, and then it was uploaded to Amazon S3.

Deadline Cloud's job attachments treats the S3 bucket as a [content-addressable storage](https://en.wikipedia.org/wiki/Content-addressable_storage).
Your files are uploaded to objects in Amazon S3 whose name is derived from a [hash](https://en.wikipedia.org/wiki/Cryptographic_hash_function)
of that file's contents. If two files have identical content, then they have the same hash value regardless of where the files are located or
what they are named. This allows Deadline Cloud to avoid uploading a file if it has previously been uploaded and is still available. So,
the first step is calculating a hash of the `script.sh` file and then checking S3 to determine whether or not the file had previously been uploaded.

You can use the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) to see the objects that were
uploaded to Amazon S3:

```bash
# The name of queue `Q1`'s job attachments S3 bucket
Q1_S3_BUCKET=$(
  aws deadline get-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
    --query 'jobAttachmentSettings.s3BucketName' | tr -d '"'
)

aws s3 ls s3://$Q1_S3_BUCKET --recursive
```

Notice that two objects were uploaded to S3:

1. `DeadlineCloud/Data/87cb19095dd5d78fcaf56384ef0e6241.xxh128` -- The contents of `script.sh`. The value `87cb19095dd5d78fcaf56384ef0e6241` in the
   object key is the hash of the file's contents, and the extension `xxh128` indicates that the hash value was calculated as a 128 bit [xxhash](https://xxhash.com/).
2. `DeadlineCloud/Manifests/<farm-id>/<queue-id>/Inputs/<guid>/a1d221c7fd97b08175b3872a37428e8c_input` -- A manifest object (described below) 
   for the job submission. The values `<farm-id>`, `<queue-id>`, and `<guid>` are shorthanded here for brevity; they are your farm identifier,
   queue identifier, and a random hexidecimal value, respectively. The value `a1d221c7fd97b08175b3872a37428e8c` in this example is a hash
   value calculated from the string `/home/cloudshell-user/job_attachments_devguide`; the directory where `script.sh` is located.

The manifest object contains all of the information for the input files ***from a specific root path*** 
(see: [How Job Attachments Decides What to Upload to Amazon S3](#312-how-job-attachments-decides-what-to-upload-to-amazon-s3) for more
on root paths) that were uploaded to Amazon S3 as part of the job's submission. Downloading this manifest file
(`aws s3 cp s3://$Q1_S3_BUCKET/<objectname>`) and viewing its contents you will see something similar to:

```json
{
    "hashAlg": "xxh128",
    "manifestVersion": "2023-03-03",
    "paths": [
        {
            "hash": "87cb19095dd5d78fcaf56384ef0e6241",
            "mtime": 1721147454416085,
            "path": "script.sh",
            "size": 39
        }
    ],
    "totalSize": 39
}
```

Notably, this is saying that the file named `script.sh` was uploaded, and the hash of that file's contents is `87cb19095dd5d78fcaf56384ef0e6241`.
This hash value matches the value in the object name `DeadlineCloud/Data/87cb19095dd5d78fcaf56384ef0e6241.xxh128` and is used by Deadline Cloud
to know which object to download for this file's contents. If you are curious, the full schema for this file is
[available in GitHub](https://github.com/aws-deadline/deadline-cloud/tree/mainline/src/deadline/job_attachments/asset_manifests/schemas).

Aside: The locations of the manifest objects for a job submission is provided as part of the `attachments` property
when calling [Deadline Cloud's `CreateJob` API](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_CreateJob.html). 
You can see this in the output from [Deadline Cloud's GetJob API](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_GetJob.html):

```json
{
    "attachments": {
        "fileSystem": "COPIED",
        "manifests": [
            {
                "inputManifestHash": "5b0db3d311805ea8de7787b64cbbe8b3",
                "inputManifestPath": "<farm-id>/<queue-id>/Inputs/<guid>/a1d221c7fd97b08175b3872a37428e8c_input",
                "rootPath": "/home/cloudshell-user/job_attachments_devguide",
                "rootPathFormat": "posix"
            }
        ]
    },
    ...
}
```

#### 3.1.2. How Job Attachments Decides What to Upload to Amazon S3

The files and directories that job attachments considers for upload to Amazon S3 as inputs to your job are:

1. The values of all `PATH`-type job parameters, that are defined in the job bundle's job template,
   with a `dataFlow` value of `IN` or `INOUT`; and
2. The files and directories listed as inputs in the job bundle's [asset references file](README#elements---asset-references).

If you submit a job with no storage profile, as you did in [What Job Attachments Uploads to Amazon S3](#311-what-job-attachments-uploads-to-amazon-s3),
then all of the files considered for uploading will be uploaded. If you submit a job with a storage profile, then files are not uploaded to Amazon S3 if
they are located in the storage profile's `SHARED`-type filesystem locations that are also required filesystem locations on the queue. These locations
are expected to be available on the worker hosts that run the job, so there is no need to upload them to Amazon S3.

To explore the behavior of Deadline Cloud's job attachments, create the `SHARED` filesystem locations in `WSAll` within your AWS CloudShell environment,
and add files to all of those filesystem locations:

```bash
# Change the value of WSALL_ID to the identifier of the WSAll storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

sudo mkdir -p /shared/common /shared/projects/project1 /shared/projects/project2
sudo chown -R cloudshell-user:cloudshell-user /shared

for d in /shared/common /shared/projects/project1 /shared/projects/project2; do
  echo "File contents for $d" > ${d}/file.txt
done
```

Next, add an [asset references file](README#elements---asset-references) to the job bundle that includes all of the files that you created as inputs for the job:

```yaml
cat > ${HOME}/job_attachments_devguide/asset_references.yaml << EOF
assetReferences:
  inputs:
    filenames:
    - /shared/common/file.txt
    directories:
    - /shared/projects/project1
    - /shared/projects/project2
EOF
```

Then, configure the Deadline Cloud CLI to submit jobs with the `WSAll` storage profile, and submit the job bundle:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of WSALL_ID to the identifier of the WSAll storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

deadline config set settings.storage_profile_id $WSALL_ID

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID job_attachments_devguide/
```

Two files are uploaded to Amazon S3 when the job is submitted. You can download the manifest objects for the job from Amazon S3
to see which files were uploaded:

```bash
for manifest in $( \
  aws deadline get-job --farm-id $FARM_ID --queue-id $QUEUE1_ID --job-id $JOB_ID \
    --query 'attachments.manifests[].inputManifestPath' \
    | jq -r '.[]'
); do
  echo "Manifest object: $manifest"
  aws s3 cp --quiet s3://$Q1_S3_BUCKET/DeadlineCloud/Manifests/$manifest /dev/stdout | jq .
done
```

In this case, there is a single manifest file with contents:

```json
{
    "hashAlg": "xxh128",
    "manifestVersion": "2023-03-03",
    "paths": [
        {
            "hash": "87cb19095dd5d78fcaf56384ef0e6241",
            "mtime": 1721147454416085,
            "path": "home/cloudshell-user/job_attachments_devguide/script.sh",
            "size": 39
        },
        {
            "hash": "af5a605a3a4e86ce7be7ac5237b51b79",
            "mtime": 1721163773582362,
            "path": "shared/projects/project2/file.txt",
            "size": 44
        }
    ],
    "totalSize": 83
}
```

Look at the result from the GetJob API for this manifest and you will see that the `rootPath` is "/" for this manifest:

```bash
aws deadline get-job --farm-id $FARM_ID --queue-id $QUEUE1_ID --job-id $JOB_ID --query 'attachments.manifests[*]'
```

The root path of a set of input files is always the longest common subpath of those files. If your job was submitted from, say,
Windows instead and you had input files with no common subpath because they were on different drives then you would see a separate
root path on each drive. The paths in a manifest are always relative to the root path of the manifest, so the input files that were
uploaded are:

1. `/home/cloudshell-user/job_attachments_devguide/script.sh`: The script file within the job bundle.
2. `/shared/projects/project2/file.txt`: The file within a `SHARED` filesystem location in the `WSAll` storage profile that is **not** in
   the list of required filesystem locations on queue `Q1`.

Notice that the files contained in filesystem locations `FSComm` (`/shared/common/file.txt`) and `FS1` (`/shared/projects/project1/file.txt`) are not
in that list. This is because those filesystem locations are `SHARED` in the `WSAll` storage profile and they both appear in the list of required
filesystem locations in queue `Q1`.

Aside: You can see which filesystem locations are considered `SHARED` for a job that is submitted with a particular storage profile with
Deadline Cloud's [GetStorageProfileForQueue API](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_GetStorageProfileForQueue.html).
To query that API for storage profile `WSAll` for queue `Q1` and compare that against the definition of storage profile `WSAll`:

```bash
aws deadline get-storage-profile --farm-id $FARM_ID --storage-profile-id $WSALL_ID

aws deadline get-storage-profile-for-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID --storage-profile-id $WSALL_ID
```

#### 3.1.3. How Jobs Find Job Attachment's Input Files

For a job to use the files that Deadline Cloud uploads to Amazon S3 using its job attachments feature, your job needs those
files to be available through the filesystem on the worker hosts where the job is run. When a
[session](https://github.com/OpenJobDescription/openjd-specifications/wiki/How-Jobs-Are-Run#sessions) for your job
runs on a worker host, Deadline Cloud's job attachments feature will download the input files for that job into
a temporary directory on the worker host's local drive and add path mapping rules for each of the job's root paths to its
filesystem location on the local drive.

To see how this works, first start the Deadline Cloud worker agent in an AWS CloudShell tab as you did when following
along in the section on [Deriving Path Mapping Rules from Storage Profiles](#24-deriving-path-mapping-rules-from-storage-profiles).
Let all of the previously submitted jobs finish running, and then delete the job logs from the logs directory:

```bash
rm -rf ~/devdemo-logs/queue-*
```

Then, continuing from the modifications that you made in the previous section to add an assets references file to the job bundle,
further modify the job bundle to show all files that are in the session's temporary working directory and the contents of the path
mapping rules file, and then submit a job with the modified bundle:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of WSALL_ID to the identifier of the WSAll storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

deadline config set settings.storage_profile_id $WSALL_ID

cat > ~/job_attachments_devguide/script.sh << EOF
#!/bin/bash

echo "Session working directory is: \$(pwd)"
echo
echo "Contents:"
find . -type f
echo
echo "Path mapping rules file: \$1"
jq . \$1
EOF

cat > ~/job_attachments_devguide/template.yaml << EOF
specificationVersion: jobtemplate-2023-09
name: "Job Attachments Explorer"
parameterDefinitions:
- name: ScriptFile
  type: PATH
  default: script.sh
  dataFlow: IN
  objectType: FILE
steps:
- name: Step
  script:
    actions:
      onRun:
        command: /bin/bash
        args:
        - "{{Param.ScriptFile}}"
        - "{{Session.PathMappingRulesFile}}"
EOF

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID job_attachments_devguide/
```

You can look at the log of the job's run after it has been run by the worker in your AWS CloudShell environment:

```bash
cat demoenv-logs/queue-*/session*.log
```

Notice that the first thing that occurs in the session is that the two input files for the job are downloaded to
the worker:

```
2024-07-17 01:26:37,824 INFO ==============================================
2024-07-17 01:26:37,825 INFO --------- Job Attachments Download for Job
2024-07-17 01:26:37,825 INFO ==============================================
2024-07-17 01:26:37,825 INFO Syncing inputs using Job Attachments
2024-07-17 01:26:38,116 INFO Downloaded 142.0 B / 186.0 B of 2 files (Transfer rate: 0.0 B/s)
2024-07-17 01:26:38,174 INFO Downloaded 186.0 B / 186.0 B of 2 files (Transfer rate: 733.0 B/s)
2024-07-17 01:26:38,176 INFO Summary Statistics for file downloads:
Processed 2 files totaling 186.0 B.
Skipped re-processing 0 files totaling 0.0 B.
Total processing time of 0.09752 seconds at 1.91 KB/s.
```

Then, after that you will see the output from `script.sh` that was run by the job that shows:

1. The input files that were uploaded when the job was submitted are located under a directory whose
   name begins with "assetroot" within the session's temporary directory;
2. That those input files' paths have been relocated to be relative to that "assetroot" directory
   instead of relative to the root path for the job's input manifest (`"/"`); and
3. The path mapping rules file contains an additional rule that remaps `"/"` to the absolute path
   of the "assetroot" directory.

For example:

```
2024-07-17 01:26:38,264 INFO Output:
2024-07-17 01:26:38,267 INFO Session working directory is: /sessions/session-b041c12fb5ba4dc9aa978bf71138ac34qnysdvxy
2024-07-17 01:26:38,267 INFO 
2024-07-17 01:26:38,267 INFO Contents:
2024-07-17 01:26:38,269 INFO ./tmp_xdhbsdo.sh
2024-07-17 01:26:38,269 INFO ./tmpdi00052b.json
2024-07-17 01:26:38,269 INFO ./assetroot-3751af5bd81011e6d21d/shared/projects/project2/file.txt
2024-07-17 01:26:38,269 INFO ./assetroot-3751af5bd81011e6d21d/home/cloudshell-user/job_attachments_devguide/script.sh
2024-07-17 01:26:38,269 INFO 
2024-07-17 01:26:38,270 INFO Path mapping rules file: /sessions/session-b041c12fb5ba4dc9aa978bf71138ac34qnysdvxy/tmpdi00052b.json
2024-07-17 01:26:38,282 INFO {
2024-07-17 01:26:38,282 INFO   "version": "pathmapping-1.0",
2024-07-17 01:26:38,282 INFO   "path_mapping_rules": [
2024-07-17 01:26:38,282 INFO     {
2024-07-17 01:26:38,282 INFO       "source_path_format": "POSIX",
2024-07-17 01:26:38,282 INFO       "source_path": "/shared/projects/project1",
2024-07-17 01:26:38,283 INFO       "destination_path": "/mnt/projects/project1"
2024-07-17 01:26:38,283 INFO     },
2024-07-17 01:26:38,283 INFO     {
2024-07-17 01:26:38,283 INFO       "source_path_format": "POSIX",
2024-07-17 01:26:38,283 INFO       "source_path": "/shared/common",
2024-07-17 01:26:38,283 INFO       "destination_path": "/mnt/common"
2024-07-17 01:26:38,283 INFO     },
2024-07-17 01:26:38,283 INFO     {
2024-07-17 01:26:38,283 INFO       "source_path_format": "POSIX",
2024-07-17 01:26:38,283 INFO       "source_path": "/",
2024-07-17 01:26:38,283 INFO       "destination_path": "/sessions/session-b041c12fb5ba4dc9aa978bf71138ac34qnysdvxy/assetroot-3751af5bd81011e6d21d"
2024-07-17 01:26:38,283 INFO     }
2024-07-17 01:26:38,283 INFO   ]
2024-07-17 01:26:38,283 INFO }
```

> *IMPORTANT NOTE*: If the job that you submit has multiple manifests with different root paths, then there will be a different "assetroot"-named directory
for each of the root paths.

Finally, if you need to reference the relocated filesystem location of one of your jobs' input files, directories, or filesystem locations then you
can either process the path mapping rules file in your job and perform the remapping yourself or add a `PATH` type job parameter to the job template
in your job bundle and pass the value that you need to remap as the value of that parameter. For example, modify the job bundle again to have
one of these job parameters and then submit a job with the filesystem location `/shared/projects/project2` as its value:

```bash
cat > ~/job_attachments_devguide/template.yaml << EOF
specificationVersion: jobtemplate-2023-09
name: "Job Attachments Explorer"
parameterDefinitions:
- name: LocationToRemap
  type: PATH
steps:
- name: Step
  script:
    actions:
      onRun:
        command: /bin/echo
        args:
        - "The location of {{RawParam.LocationToRemap}} in the session is {{Param.LocationToRemap}}"
EOF

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID job_attachments_devguide/ \
  -p LocationToRemap=/shared/projects/project2
```

The log file for this job's run contains its output:

```
2024-07-17 01:40:35,283 INFO Output:
2024-07-17 01:40:35,284 INFO The location of /shared/projects/project2 in the session is /sessions/session-23d79bab7e4a4310820c7206c475e978byjtayt9/assetroot-bfadf2c8d83724a6d25e
```

### 3.2. Getting Output Files from a Job

You've explored how Deadline Cloud uses its job attachments feature to get input files that are not in shared filesystem locations
to the worker hosts for your jobs to use in [Submitting Files with a Job](#31-submitting-files-with-a-job). The next thing to explore
is how Deadline Cloud identifies the output files that your jobs generate, decides whether to upload those files to Amazon S3, and how
you can get those output files onto your workstation.

You will use the `job_attachments_devguide_output` job bundle instead of the `job_attachments_devguide` job bundle for this,
so start by making a copy of it in your AWS CloudShell environment from your clone of the Deadline Cloud samples GitHub repository:

```bash
cp -r deadline-cloud-samples/job_bundles/job_attachments_devguide_output ~/
```

The important difference between this job bundle and the `job_attachments_devguide` job bundle is the addition of a new job parameter
in the job template:

```yaml
...
parameterDefinitions:
...
- name: OutputDir
  type: PATH
  objectType: DIRECTORY
  dataFlow: OUT
  default: ./output_dir
  description: This directory the output for all steps.
...
```

The `dataFlow` property of the parameter has the value `OUT`. Deadline Cloud's job attachments feature treats
the value of job parameters that are defined with a value of `OUT` or `INOUT` for `dataFlow` as outputs of your job.
If the filesystem location that is passed as a value to these kinds of job parameters is remapped to a local filesystem location
on the worker that runs the job, then Deadline Cloud will look for new files at the location and upload those
to Amazon S3 as job outputs.

To see how this works, first start the Deadline Cloud worker agent in an AWS CloudShell tab as you did when following
along in the section on [How Jobs Find Job Attachment's Input Files](#313-how-jobs-find-job-attachments-input-files).
Let all of the previously submitted jobs finish running if there are any, and then delete the job logs from the logs directory:

```bash
rm -rf ~/devdemo-logs/queue-*
```

Next, submit a job with this job bundle, let the worker running in your AWS CloudShell run it, and then look at the logs:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of WSALL_ID to the identifier of the WSAll storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

deadline config set settings.storage_profile_id $WSALL_ID

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID ./job_attachments_devguide_output
```

The log is very similar to the ones that you saw in the section on [How Jobs Find Job Attachment's Input Files](#313-how-jobs-find-job-attachments-input-files),
but now the log indicates that a file was detected as output and uploaded to Amazon S3:

```
2024-07-17 02:13:10,873 INFO ----------------------------------------------
2024-07-17 02:13:10,873 INFO Uploading output files to Job Attachments
2024-07-17 02:13:10,873 INFO ----------------------------------------------
2024-07-17 02:13:10,873 INFO Started syncing outputs using Job Attachments
2024-07-17 02:13:10,955 INFO Found 1 file totaling 117.0 B in output directory: /sessions/session-7efa/assetroot-e7d860e9a7a86e6bbf77/output_dir
2024-07-17 02:13:10,956 INFO Uploading output manifest to DeadlineCloud/Manifests/farm-0011/queue-2233/job-4455/step-6677/task-6677-0/2024-07-17T02:13:10.835545Z_sessionaction-8899-1/c6808439dfc59f86763aff5b07b9a76c_output
2024-07-17 02:13:10,988 INFO Uploading 1 output file to S3: neilsd-job-attach-assets-testing/DeadlineCloud/Data
2024-07-17 02:13:11,011 INFO Uploaded 117.0 B / 117.0 B of 1 file (Transfer rate: 0.0 B/s)
2024-07-17 02:13:11,011 INFO Summary Statistics for file uploads:
Processed 1 file totaling 117.0 B.
Skipped re-processing 0 files totaling 0.0 B.
Total processing time of 0.02281 seconds at 5.13 KB/s.
```

The log shows that a new manifest object was created in the Amazon S3 bucket that you configured for use by job attachments on queue `Q1`.
The name of the manifest object is derived from the farm, queue, job, step, task, and sessionaction identifiers of the task that generated the output.
Download this manifest file to see where Deadline Cloud placed the output files for this task:

```bash
# The name of queue `Q1`'s job attachments S3 bucket
Q1_S3_BUCKET=$(
  aws deadline get-queue --farm-id $FARM_ID --queue-id $QUEUE1_ID \
    --query 'jobAttachmentSettings.s3BucketName' | tr -d '"'
)

# Fill this in with the object name from your log
OBJECT_KEY="DeadlineCloud/Manifests/..."

aws s3 cp --quiet s3://$Q1_S3_BUCKET/$OBJECT_KEY /dev/stdout | jq .
```

The manifest looks like:

```json
{
  "hashAlg": "xxh128",
  "manifestVersion": "2023-03-03",
  "paths": [
    {
      "hash": "34178940e1ef9956db8ea7f7c97ed842",
      "mtime": 1721182390859777,
      "path": "output_dir/output.txt",
      "size": 117
    }
  ],
  "totalSize": 117
}
```

This says that the content of the output file is saved to Amazon S3 the same way that job input files are saved. Similar to
input files, the output file is stored in S3 with an object name containing the hash of the file and the prefix `DeadlineCloud/Data`:

```bash
$ aws s3 ls --recursive s3://$Q1_S3_BUCKET | grep 34178940e1ef9956db8ea7f7c97ed842
2024-07-17 02:13:11        117 DeadlineCloud/Data/34178940e1ef9956db8ea7f7c97ed842.xxh128
```

You can download the outputs of a job to your workstation either using the Deadline Cloud Monitor or the
Deadline Cloud CLI:

```bash
deadline job download-output --farm-id $FARM_ID --queue-id $QUEUE1_ID --job-id $JOB_ID
```

Recall that the value of the `OutputDir` job parameter in the job that was submitted is `./output_dir`, so the outputs
will be downloaded to into a directory called `output_dir` within the job bundle directory. Had you supplied an absolute path
or different relative location as the value for `OutputDir`, then the output files would be downloaded to that location instead.

```
$ deadline job download-output --farm-id $FARM_ID --queue-id $QUEUE1_ID --job-id $JOB_ID
Downloading output from Job 'Job Attachments Explorer: Output'

Summary of files to download:
    /home/cloudshell-user/job_attachments_devguide_output/output_dir/output.txt (1 file)

You are about to download files which may come from multiple root directories. Here are a list of the current root directories:
[0] /home/cloudshell-user/job_attachments_devguide_output
> Please enter the index of root directory to edit, y to proceed without changes, or n to cancel the download (0, y, n) [y]: 

Downloading Outputs  [####################################]  100%
Download Summary:
    Downloaded 1 files totaling 117.0 B.
    Total download time of 0.14189 seconds at 824.0 B/s.
    Download locations (total file counts):
        /home/cloudshell-user/job_attachments_devguide_output (1 file)
```

Note that if a task is run multiple times, due to being requeued for instance, then there may be multiple manifest objects for that task in S3.
In that instance, the manifest with the most recent timestamp in its object key is the one that will be referenced for deciding which files
to download as outputs.

### 3.3. Using Files Output from a Step in a Dependent Step

You've explored how Deadline Cloud uses job attachments to shuttle your job's input files through Amazon S3 in
the section on [Submitting Files with a Job](#31-submitting-files-with-a-job), and how it shuttles your job's output
files through Amazon S3 in [Getting Output Files from a Job](#32-getting-output-files-from-a-job). The final concept
to explore in this guide is how one step in a job can access the outputs from a step that it depends on in the same job.

To make the outputs of one step available to another, Deadline Cloud adds additional actions to a session to download
those outputs before running tasks in the session. You tell it which steps to download the outputs from by declaring
those steps as dependencies of the step that needs to use the outputs.

You will use the `job_attachments_devguide_output` job bundle again for this part, so start by making a copy of it
in your AWS CloudShell environment from your clone of the Deadline Cloud samples GitHub repository, but then modify
it to add a dependent step that only runs after the existing step and uses that step's output:

```bash
cp -r deadline-cloud-samples/job_bundles/job_attachments_devguide_output ~/

cat >> job_attachments_devguide_output/template.yaml << EOF
- name: DependentStep
  dependencies:
  - dependsOn: Step
  script:
    actions:
      onRun:
        command: /bin/cat
        args:
        - "{{Param.OutputDir}}/output.txt"
EOF
```

The job created with this modified job bundle will run as two separate sessions. One for the task in the step named "Step"
and then a second for the task in the step named "DependentStep".

To see how this works, first start the Deadline Cloud worker agent in an AWS CloudShell tab as you did when following
along in the section on [Getting Output Files from a Job](#32-getting-output-files-from-a-job).
Let all of the previously submitted jobs finish running if there are any, and then delete the job logs from the logs directory:

```bash
rm -rf ~/devdemo-logs/queue-*
```

Then, submit a job using the modified `job_attachments_devguide_output` job bundle, wait for it to finish running on the
worker in your AWS CloudShell environment, and then look out the logs for the two sessions that are run:

```bash
# Change the value of FARM_ID to your farm's identifier
FARM_ID=farm-00112233445566778899aabbccddeeff
# Change the value of QUEUE1_ID to queue Q1's identifier
QUEUE1_ID=queue-00112233445566778899aabbccddeeff
# Change the value of WSALL_ID to the identifier of the WSAll storage profile
WSALL_ID=sp-00112233445566778899aabbccddeeff

deadline config set settings.storage_profile_id $WSALL_ID

deadline bundle submit --farm-id $FARM_ID --queue-id $QUEUE1_ID ./job_attachments_devguide_output

# Wait for the job to finish running, and then:

cat demoenv-logs/queue-*/session-*
```

In the session log for the task in the step named `DependentStep`, notice that there are two separate
download actions that are run:

```
2024-07-17 02:52:05,666 INFO ==============================================
2024-07-17 02:52:05,666 INFO --------- Job Attachments Download for Job
2024-07-17 02:52:05,667 INFO ==============================================
2024-07-17 02:52:05,667 INFO Syncing inputs using Job Attachments
2024-07-17 02:52:05,928 INFO Downloaded 207.0 B / 207.0 B of 1 file (Transfer rate: 0.0 B/s)
2024-07-17 02:52:05,929 INFO Summary Statistics for file downloads:
Processed 1 file totaling 207.0 B.
Skipped re-processing 0 files totaling 0.0 B.
Total processing time of 0.03954 seconds at 5.23 KB/s.

2024-07-17 02:52:05,979 INFO 
2024-07-17 02:52:05,979 INFO ==============================================
2024-07-17 02:52:05,979 INFO --------- Job Attachments Download for Step
2024-07-17 02:52:05,979 INFO ==============================================
2024-07-17 02:52:05,980 INFO Syncing inputs using Job Attachments
2024-07-17 02:52:06,133 INFO Downloaded 117.0 B / 117.0 B of 1 file (Transfer rate: 0.0 B/s)
2024-07-17 02:52:06,134 INFO Summary Statistics for file downloads:
Processed 1 file totaling 117.0 B.
Skipped re-processing 0 files totaling 0.0 B.
Total processing time of 0.03227 seconds at 3.62 KB/s.
```

The first of these is downloading the `script.sh` file that is run by the step named "Step", and the second
is downloading the outputs from that step. In the action that is downloading the previous step's output,
Deadline Cloud determines which files need to be downloaded by using the output manifest that was generated by that
step as an input manifest. 

Then later in that same log, you can see the output from the step named "DependentStep":

```
2024-07-17 02:52:06,213 INFO Output:
2024-07-17 02:52:06,216 INFO Script location: /sessions/session-5b33fa6d5ea94861ba4cd88a9e8d31d94kszcb0j/assetroot-e7d860e9a7a86e6bbf77/script.sh
```
