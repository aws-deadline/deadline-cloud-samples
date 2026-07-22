terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # Matches the version range used by the upstream knfsd-file-cache
      # examples so the vendored module resolves a single AWS provider.
      version = "~> 6.55.0"
    }
    # Deadline Cloud is not in the hashicorp/aws provider. The AWSCC (Cloud
    # Control) provider exposes AWS::Deadline::* resources, including the
    # vpc_configuration.resource_configuration_arns field this example uses.
    awscc = {
      source  = "hashicorp/awscc"
      version = ">= 1.30.0"
    }
  }
}

# Compute region (region A): KNFSD cluster, VPC Lattice resource endpoint, and
# the Deadline Cloud service-managed fleet live here.
provider "aws" {
  region = var.compute_region
}

provider "awscc" {
  region = var.compute_region
}

# Origin region (region B): the FSx for OpenZFS filer lives here, reached by the
# KNFSD cache across a VPC peering connection. This distance is what makes the
# cache worth having — it stands in for an on-premises or otherwise-distant filer.
provider "aws" {
  alias  = "origin"
  region = var.origin_region
}
