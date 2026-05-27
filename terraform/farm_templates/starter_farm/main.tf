# Deadline Cloud Starter Farm with SMF Fleet
# Terraform equivalent of the CloudFormation starter_farm template
# https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/cloudformation/farm_templates/starter_farm/deadline-cloud-starter-farm-template.yaml

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = ">= 1.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "awscc" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "job_attachments_bucket_name" {
  type        = string
  description = "An existing S3 bucket to use for job attachments and the default S3 conda channel."
}

variable "farm_name" {
  type    = string
  default = "Starter Deadline Cloud Farm"
}

variable "farm_description" {
  type    = string
  default = "Deadline Cloud farm deployed from the starter_farm sample Terraform template."
}

variable "prod_queue_name" {
  type    = string
  default = "Production Job Queue"
}

variable "prod_queue_description" {
  type    = string
  default = "The Deadline Cloud queue for running production jobs."
}

variable "prod_conda_channels" {
  type    = string
  default = "deadline-cloud"
}

variable "package_build_queue_name" {
  type    = string
  default = "Package Build Queue"
}

variable "package_build_queue_description" {
  type    = string
  default = "The Deadline Cloud queue for building conda packages."
}

variable "cpu_linux_fleet_name" {
  type    = string
  default = "CPU Linux Fleet"
}

variable "cpu_windows_fleet_name" {
  type    = string
  default = ""
}

variable "cuda_linux_fleet_name" {
  type    = string
  default = ""
}

variable "cpu_linux_instance_market_type" {
  type    = string
  default = "spot"
}

variable "max_cpu_linux_worker_count" {
  type    = number
  default = 10
}

variable "min_cpu_linux_vcpu" {
  type    = number
  default = 2
}

variable "max_cpu_linux_vcpu" {
  type    = number
  default = 8
}

variable "min_cpu_linux_ram_mib" {
  type    = number
  default = 16384
}

variable "cpu_windows_instance_market_type" {
  type    = string
  default = "spot"
}

variable "max_cpu_windows_worker_count" {
  type    = number
  default = 10
}

variable "min_cpu_windows_vcpu" {
  type    = number
  default = 2
}

variable "max_cpu_windows_vcpu" {
  type    = number
  default = 8
}

variable "min_cpu_windows_ram_mib" {
  type    = number
  default = 16384
}

variable "cuda_linux_instance_market_type" {
  type    = string
  default = "on-demand"
}

variable "max_cuda_linux_worker_count" {
  type    = number
  default = 1
}

variable "min_cuda_linux_vcpu" {
  type    = number
  default = 4
}

variable "max_cuda_linux_vcpu" {
  type    = number
  default = 16
}

variable "min_cuda_linux_ram_mib" {
  type    = number
  default = 32768
}

variable "root_ebs_volume_size_gib" {
  type    = number
  default = 300
}

variable "root_ebs_volume_iops" {
  type    = number
  default = 3000
}

variable "root_ebs_volume_throughput_mib" {
  type    = number
  default = 125
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  partition        = data.aws_partition.current.partition
  url_suffix       = data.aws_partition.current.dns_suffix
  has_cpu_linux    = var.cpu_linux_fleet_name != ""
  has_cpu_windows  = var.cpu_windows_fleet_name != ""
  has_cuda_linux   = var.cuda_linux_fleet_name != ""
}

# Farm
resource "awscc_deadline_farm" "main" {
  display_name = var.farm_name
  description  = var.farm_description
}

# Production Queue IAM Role
resource "aws_iam_role" "queue" {
  name = "ProdQueue-${awscc_deadline_farm.main.farm_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["deadline.${local.url_suffix}", "credentials.deadline.${local.url_suffix}"] }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnEquals    = { "aws:SourceArn" = awscc_deadline_farm.main.arn }
      }
    }]
  })
}

resource "aws_iam_role_policy" "queue" {
  name = "QueuePolicy"
  role = aws_iam_role.queue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "JobAttachmentsReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"]
        Resource = ["arn:aws:s3:::${var.job_attachments_bucket_name}", "arn:aws:s3:::${var.job_attachments_bucket_name}/DeadlineCloud/*"]
        Condition = { StringEquals = { "aws:ResourceAccount" = local.account_id } }
      },
      {
        Sid      = "CondaChannelReadOnly"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = ["arn:aws:s3:::${var.job_attachments_bucket_name}", "arn:aws:s3:::${var.job_attachments_bucket_name}/Conda/*"]
        Condition = { StringEquals = { "aws:ResourceAccount" = local.account_id } }
      },
      {
        Sid      = "JobLogsReadOnly"
        Effect   = "Allow"
        Action   = ["logs:GetLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/deadline/${awscc_deadline_farm.main.farm_id}/*"
      },
      {
        Sid      = "DeadlineServiceManagedFleetSoftwareAccess"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = ["*"]
        Condition = {
          ArnLike      = { "s3:DataAccessPointArn" = "arn:aws:s3:*:*:accesspoint/deadline-software-*" }
          StringEquals = { "s3:AccessPointNetworkOrigin" = "VPC" }
        }
      }
    ]
  })
}

# Production Queue
resource "awscc_deadline_queue" "prod" {
  display_name = var.prod_queue_name
  description  = var.prod_queue_description
  farm_id      = awscc_deadline_farm.main.farm_id
  role_arn     = aws_iam_role.queue.arn
  job_attachment_settings = {
    s3_bucket_name = var.job_attachments_bucket_name
    root_prefix    = "DeadlineCloud"
  }
}

# Conda Queue Environment
resource "awscc_deadline_queue_environment" "conda" {
  farm_id   = awscc_deadline_farm.main.farm_id
  queue_id  = awscc_deadline_queue.prod.queue_id
  priority  = 1
  template  = templatefile("${path.module}/conda_queue_env.yaml.tftpl", {
    job_attachments_bucket_name = var.job_attachments_bucket_name
    prod_conda_channels         = var.prod_conda_channels
  })
  template_type = "YAML"
}

# Package Build Queue IAM Role
resource "aws_iam_role" "queue_package_build" {
  name = "PackageBuildQueue-${awscc_deadline_farm.main.farm_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = ["deadline.${local.url_suffix}", "credentials.deadline.${local.url_suffix}"] }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnEquals    = { "aws:SourceArn" = awscc_deadline_farm.main.arn }
      }
    }]
  })
}

resource "aws_iam_role_policy" "queue_package_build" {
  name = "QueuePolicy"
  role = aws_iam_role.queue_package_build.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "JobAttachmentsReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"]
        Resource = ["arn:aws:s3:::${var.job_attachments_bucket_name}", "arn:aws:s3:::${var.job_attachments_bucket_name}/DeadlineCloudPkgBld/*"]
        Condition = { StringEquals = { "aws:ResourceAccount" = local.account_id } }
      },
      {
        Sid      = "CondaChannelReadWrite"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject", "s3:DeleteObject"]
        Resource = ["arn:aws:s3:::${var.job_attachments_bucket_name}", "arn:aws:s3:::${var.job_attachments_bucket_name}/Conda/*"]
        Condition = { StringEquals = { "aws:ResourceAccount" = local.account_id } }
      },
      {
        Sid      = "JobLogsReadOnly"
        Effect   = "Allow"
        Action   = ["logs:GetLogEvents"]
        Resource = "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/deadline/${awscc_deadline_farm.main.farm_id}/*"
      },
      {
        Sid      = "DeadlineServiceManagedFleetSoftwareAccess"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = ["*"]
        Condition = {
          ArnLike      = { "s3:DataAccessPointArn" = "arn:aws:s3:*:*:accesspoint/deadline-software-*" }
          StringEquals = { "s3:AccessPointNetworkOrigin" = "VPC" }
        }
      }
    ]
  })
}

# Package Build Queue
resource "awscc_deadline_queue" "package_build" {
  display_name = var.package_build_queue_name
  description  = var.package_build_queue_description
  farm_id      = awscc_deadline_farm.main.farm_id
  role_arn     = aws_iam_role.queue_package_build.arn
  job_attachment_settings = {
    s3_bucket_name = var.job_attachments_bucket_name
    root_prefix    = "DeadlineCloudPkgBld"
  }
}

# Fleet IAM Role (shared by all fleets)
resource "aws_iam_role" "fleet" {
  name = "Fleet-${awscc_deadline_farm.main.farm_id}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "credentials.deadline.${local.url_suffix}" }
      Action    = "sts:AssumeRole"
      Condition = {
        StringEquals = { "aws:SourceAccount" = local.account_id }
        ArnEquals    = { "aws:SourceArn" = awscc_deadline_farm.main.arn }
      }
    }]
  })
  managed_policy_arns = ["arn:${local.partition}:iam::aws:policy/AWSDeadlineCloud-FleetWorker"]
}

resource "aws_iam_role_policy" "fleet_logs" {
  name = "FleetWorkerLogs"
  role = aws_iam_role.fleet.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream"]
        Resource = "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:*:/aws/deadline/${awscc_deadline_farm.main.farm_id}/*"
        Condition = { "ForAnyValue:StringEquals" = { "aws:CalledVia" = "deadline.${local.url_suffix}" } }
      },
      {
        Effect   = "Allow"
        Action   = ["logs:PutLogEvents", "logs:GetLogEvents"]
        Resource = "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:*:/aws/deadline/${awscc_deadline_farm.main.farm_id}/*"
      }
    ]
  })
}

# CPU Linux Fleet
resource "awscc_deadline_fleet" "cpu_linux" {
  count            = local.has_cpu_linux ? 1 : 0
  display_name     = var.cpu_linux_fleet_name
  farm_id          = awscc_deadline_farm.main.farm_id
  role_arn         = aws_iam_role.fleet.arn
  min_worker_count = 0
  max_worker_count = var.max_cpu_linux_worker_count
  configuration = {
    service_managed_ec_2 = {
      instance_capabilities = {
        cpu_architecture_type = "x86_64"
        os_family             = "LINUX"
        v_cpu_count           = { min = var.min_cpu_linux_vcpu, max = var.max_cpu_linux_vcpu }
        memory_mi_b           = { min = var.min_cpu_linux_ram_mib }
        root_ebs_volume       = { size_gi_b = var.root_ebs_volume_size_gib, iops = var.root_ebs_volume_iops, throughput_mi_b = var.root_ebs_volume_throughput_mib }
      }
      instance_market_options = { type = var.cpu_linux_instance_market_type }
    }
  }
}

# CPU Windows Fleet
resource "awscc_deadline_fleet" "cpu_windows" {
  count            = local.has_cpu_windows ? 1 : 0
  display_name     = var.cpu_windows_fleet_name
  farm_id          = awscc_deadline_farm.main.farm_id
  role_arn         = aws_iam_role.fleet.arn
  min_worker_count = 0
  max_worker_count = var.max_cpu_windows_worker_count
  configuration = {
    service_managed_ec_2 = {
      instance_capabilities = {
        cpu_architecture_type = "x86_64"
        os_family             = "WINDOWS"
        v_cpu_count           = { min = var.min_cpu_windows_vcpu, max = var.max_cpu_windows_vcpu }
        memory_mi_b           = { min = var.min_cpu_windows_ram_mib }
        root_ebs_volume       = { size_gi_b = var.root_ebs_volume_size_gib, iops = var.root_ebs_volume_iops, throughput_mi_b = var.root_ebs_volume_throughput_mib }
      }
      instance_market_options = { type = var.cpu_windows_instance_market_type }
    }
  }
}

# CUDA Linux Fleet
resource "awscc_deadline_fleet" "cuda_linux" {
  count            = local.has_cuda_linux ? 1 : 0
  display_name     = var.cuda_linux_fleet_name
  farm_id          = awscc_deadline_farm.main.farm_id
  role_arn         = aws_iam_role.fleet.arn
  min_worker_count = 0
  max_worker_count = var.max_cuda_linux_worker_count
  configuration = {
    service_managed_ec_2 = {
      instance_capabilities = {
        cpu_architecture_type = "x86_64"
        os_family             = "LINUX"
        v_cpu_count           = { min = var.min_cuda_linux_vcpu, max = var.max_cuda_linux_vcpu }
        memory_mi_b           = { min = var.min_cuda_linux_ram_mib }
        root_ebs_volume       = { size_gi_b = var.root_ebs_volume_size_gib, iops = var.root_ebs_volume_iops, throughput_mi_b = var.root_ebs_volume_throughput_mib }
        accelerator_capabilities = {
          count = { min = 1, max = 1 }
          selections = [
            { name = "a10g", runtime = "latest" },
            { name = "l4", runtime = "latest" }
          ]
        }
      }
      instance_market_options = { type = var.cuda_linux_instance_market_type }
    }
  }
}

# Queue-Fleet Associations - Production Queue
resource "awscc_deadline_queue_fleet_association" "prod_cpu_linux" {
  count    = local.has_cpu_linux ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.prod.queue_id
  fleet_id = awscc_deadline_fleet.cpu_linux[0].fleet_id
}

resource "awscc_deadline_queue_fleet_association" "prod_cpu_windows" {
  count    = local.has_cpu_windows ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.prod.queue_id
  fleet_id = awscc_deadline_fleet.cpu_windows[0].fleet_id
}

resource "awscc_deadline_queue_fleet_association" "prod_cuda_linux" {
  count    = local.has_cuda_linux ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.prod.queue_id
  fleet_id = awscc_deadline_fleet.cuda_linux[0].fleet_id
}

# Queue-Fleet Associations - Package Build Queue
resource "awscc_deadline_queue_fleet_association" "pkg_cpu_linux" {
  count    = local.has_cpu_linux ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.package_build.queue_id
  fleet_id = awscc_deadline_fleet.cpu_linux[0].fleet_id
}

resource "awscc_deadline_queue_fleet_association" "pkg_cpu_windows" {
  count    = local.has_cpu_windows ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.package_build.queue_id
  fleet_id = awscc_deadline_fleet.cpu_windows[0].fleet_id
}

resource "awscc_deadline_queue_fleet_association" "pkg_cuda_linux" {
  count    = local.has_cuda_linux ? 1 : 0
  farm_id  = awscc_deadline_farm.main.farm_id
  queue_id = awscc_deadline_queue.package_build.queue_id
  fleet_id = awscc_deadline_fleet.cuda_linux[0].fleet_id
}

# Outputs
output "farm_id" {
  value = awscc_deadline_farm.main.farm_id
}

output "farm_arn" {
  value = awscc_deadline_farm.main.arn
}

output "prod_queue_id" {
  value = awscc_deadline_queue.prod.queue_id
}

output "package_build_queue_id" {
  value = awscc_deadline_queue.package_build.queue_id
}

output "cpu_linux_fleet_id" {
  value = local.has_cpu_linux ? awscc_deadline_fleet.cpu_linux[0].fleet_id : null
}

output "cpu_windows_fleet_id" {
  value = local.has_cpu_windows ? awscc_deadline_fleet.cpu_windows[0].fleet_id : null
}

output "cuda_linux_fleet_id" {
  value = local.has_cuda_linux ? awscc_deadline_fleet.cuda_linux[0].fleet_id : null
}
