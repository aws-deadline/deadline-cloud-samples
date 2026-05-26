#!/usr/bin/env bash
set -e  # Exit on any error

# Configuration - update these for your environment
S3_FONTS_URI="s3://your-bucket-name/Fonts/"
JOB_USER="job-user"

echo "[$(date)] Starting font installation..."
echo "S3 URI: $S3_FONTS_URI"
echo "Job User: $JOB_USER"

# Install fontconfig (required for font management)
echo "Installing fontconfig..."
yum install -y fontconfig

# Create fonts directory
echo "Creating fonts directory..."
mkdir -p "/home/$JOB_USER/.fonts"

# Download fonts with error checking
echo "Downloading fonts from S3..."
if aws s3 cp "$S3_FONTS_URI" "/home/$JOB_USER/.fonts" --recursive; then
    echo "Fonts downloaded successfully"
else
    echo "ERROR: Failed to download fonts from S3. Ensure the fleet role has access to the S3 bucket"
    exit 1
fi

# Set proper ownership
echo "Setting font ownership..."
chown -R "$JOB_USER:$JOB_USER" "/home/$JOB_USER/.fonts"

# Refresh font cache
echo "Refreshing font cache..."
runuser -l "$JOB_USER" -c "fc-cache -fv /home/$JOB_USER/.fonts"

# List installed fonts for verification
echo "Installed fonts:"
ls -la "/home/$JOB_USER/.fonts/"

# Test font detection
echo "Available fonts to applications:"
runuser -l "$JOB_USER" -c "fc-list"

echo "[$(date)] Font installation completed successfully"