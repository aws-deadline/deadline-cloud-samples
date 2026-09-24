# OctaneRender licensing on Linux

Use this host configuration script to place an OTOY unattended auth file on Linux AWS Deadline Cloud service-managed fleet workers. OctaneRender can then obtain a license without an interactive sign-in.

OctaneRender requires the file at `/etc/OctaneRender/otoy_unattended_credentials`. Writing there requires the elevated permissions provided to a host configuration script.

## Setup

### 1. Enable unattended authorization

Ask OTOY Support to enable unattended authorization for your account before creating the auth file. See [Authentication and Internet Access](https://docs.otoy.com/standaloneSE/AuthenticationandInternetAccess.html), under **Unattended/Silent Authorization (Online Mode Only)**. This account-level feature requires an active internet connection.

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

## Usage

1. Open the AWS Deadline Cloud console and select the Linux service-managed fleet.
2. Open the fleet's **Host configuration** section.
3. Paste the contents of `linux.sh` into the script field.
4. Save the configuration.

New workers run the script when they start. Check the fleet's CloudWatch logs to confirm that the auth file was downloaded successfully.
