# OctaneRender licensing and cuDNN on Linux

Use this host configuration script to prepare Linux AWS Deadline Cloud service-managed fleet workers for OctaneRender. It places an OTOY unattended auth file so OctaneRender can obtain a license without an interactive sign-in, and it installs the cuDNN runtime that OctaneRender loads when its render engine starts. The cuDNN runtime is typically installed automatically when OctaneRender first starts, but because OctaneRender saves it to directories outside the worker's session folders, where it is shared between sessions, it's best to download the runtime during host configuration instead.

OctaneRender reads both from fixed paths under `/etc/OctaneRender`:

- The auth file at `/etc/OctaneRender/otoy_unattended_credentials`.
- OTOY's cuDNN libraries under `/etc/OctaneRender/thirdparty/cudnn_<version>`.

Writing there requires the elevated permissions provided to a host configuration script.

## Setup

### 1. Enable unattended authorization

Ask OTOY Support to enable unattended authorization for your account before creating the auth file. See [Authentication and Internet Access](https://docs.otoy.com/standaloneSE/AuthenticationandInternetAccess.html), under **Unattended/Silent Authorization (Online Mode Only)**.

> [!WARNING]
> This licensing method requires an active internet connection so the workers can connect to the OTOY licensing servers.

### 2. Generate the auth file

Create an unattended auth file at [account.otoy.com/auth_files](https://account.otoy.com/auth_files). A valid Otoy account is required to view the auth files page.

Service-managed fleet workers do not pull IP addresses from a fixed pool, so you will need to set `0.0.0.0/0` as the IP allowlist when creating auth files for service-managed fleets. When creating auth files for customer-managed fleets, adjust the IP allowlist to match your network configurations.

> [!WARNING]
> An allowlist of `0.0.0.0/0` allows any IP address to use your OctaneRender licenses.
> For that reason, it is important to follow [Security best practices](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/security-best-practices.html) to prevent leaking any auth files.
> We also recommend restricting the allowlist to fit your workers' IP addresses for customer-managed fleets.
> To disable an auth file, navigate to the [auth files page](https://account.otoy.com/auth_files) and click the **Delete** button next to your auth file.

### 3. Upload the auth file to S3

Keep the object private and upload it to a bucket the fleet can read:

```bash
aws s3 cp otoy_unattended_credentials s3://amzn-s3-demo-bucket/octane/
```

### 4. Configure the script

In `linux.sh`, set the S3 URI for the uploaded file:

```bash
S3_CREDENTIAL_URI="s3://amzn-s3-demo-bucket/octane/otoy_unattended_credentials"
```

> [!WARNING]
> The script, as provided, enables read permissions on the auth file for all users on your worker nodes.
> If your fleet shares worker nodes with untrusted users, edit the `linux.sh` script to restrict read permissions on the auth file to only the users associated with your queue.

### 5. Grant the fleet access

Add an IAM policy to the fleet role that grants read access to only the auth file:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::amzn-s3-demo-bucket/octane/otoy_unattended_credentials"
        }
    ]
}
```

If your S3 bucket is encrypted with customer-managed KMS keys, make sure your policy also allows `kms:Decrypt` like in the example below:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::amzn-s3-demo-bucket/octane/otoy_unattended_credentials"
        },
        {
            "Effect": "Allow",
            "Action": "kms:Decrypt",
            "Resource": "arn:aws:kms:<region>:<account>:key/<key-id>"
        }
    ]
}
```

### 6. Set the cuDNN archive

> [!WARNING]
> This host configuration script downloads cuDNN directly from OTOY. The download requires an active internet connection on your fleet workers.

1. Extract the OctaneRender installer. The following example shows the process for the Linux installer for Octane for Maya:

   ```bash
   chmod u+x OctaneRender_Studio+_2026.4_for_Maya_v25.20.run
   ./OctaneRender_Studio+_2026.4_for_Maya_v25.20.run --extract
   ```

2. Print the cuDNN download URL and directory name embedded in `liboctane.so`. The Maya plugin installer extracts `liboctane.so` to `OctaneForMaya/install/lib/`.

   ```bash
   strings OctaneForMaya/install/lib/liboctane.so | grep -E 'render\.otoy\.com.*cudnn|thirdparty/cudnn'
   ```

   For OctaneRender 2026.4 for Maya (plugin v25.20), the following is printed. Your version of OctaneRender may print something else:

   ```text
   https://render.otoy.com/downloads/13/0e/43/b5/cudnn_9_7_0_linux.zip
   thirdparty/cudnn_9_7_0
   ```

3. In `linux.sh`, set `CUDNN_URL` to the URL from step 2. For OctaneRender 2026.4 for Maya:

   ```bash
   CUDNN_URL="https://render.otoy.com/downloads/13/0e/43/b5/cudnn_9_7_0_linux.zip"
   ```

   The script creates the install directory from the archive name, so `cudnn_9_7_0_linux.zip` installs to `/etc/OctaneRender/thirdparty/cudnn_9_7_0`. Confirm that this matches the `thirdparty/cudnn_...` line from step 2.

## Usage

1. Open the AWS Deadline Cloud console and select the Linux service-managed fleet.
2. Open the fleet's **Host configuration** section.
3. Edit `linux.sh` by following the steps above.
4. Paste the contents of your edited `linux.sh` into the script field.
5. Save the configuration.

New workers run the script when they start. Check the fleet's CloudWatch logs to confirm that the auth file was downloaded and the cuDNN runtime was installed successfully.
