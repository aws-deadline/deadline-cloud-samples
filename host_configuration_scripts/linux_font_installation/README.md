# AWS Deadline Cloud Font Installation

This script installs fonts from an S3 bucket on AWS Deadline Cloud Linux service managed fleet instances, making them available to applications like Nuke.

Be aware that fonts may render differently from operating system to operating system.

## Setup

### 1. Upload Fonts to S3
Upload your font files to an S3 bucket:
```bash
aws s3 cp /path/to/your/fonts/ s3://your-bucket-name/Fonts/ --recursive
```

Using a separate folder for fonts is optional. Beware this script will copy over everything in that folder. Making sure only fonts are getting moved will save time at instance startup.

### 2. Configure the Script
Edit `font_install_host_config.sh` and update these variables:
```bash
S3_FONTS_URI="s3://your-bucket-name/Fonts/"
JOB_USER="job-user"  # This is job-user by default, update if needed
```

### 3. Add IAM Policy to Fleet
Your Deadline Cloud fleet needs S3 read permissions. Add this policy to your fleet's IAM role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/Fonts/*"
            ]
        }
    ]
}
```

Replace `your-bucket-name` with your actual S3 bucket name.

## Usage

Deploy the script through the AWS Deadline Cloud console:

1. Open the AWS Deadline Cloud console
2. Navigate to your fleet
3. Go to the "Host configuration" section
4. Copy and paste the contents of `font_install_host_config.sh` into the script field
5. Save the configuration

New fleet instances will automatically run the font installation script on startup.
