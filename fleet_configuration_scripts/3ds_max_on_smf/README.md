# Installation script for 3ds Max

This script takes care of installing 3ds Max, its required depenencies, and the 3ds Max adaptor.
It also takes care of setting up some needed environment variables.

The script makes the following assumptons:
1. A 3ds Max installation package exists in a S3 bucket within the customer account.
1. The IAM role of the fleet using the script has permissions to download the installation package.

Please note that script contains placeholders for some path values. Please make sure to override the placeholders
before using the script.