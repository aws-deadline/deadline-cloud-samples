variable "compute_region" {
  description = "Region A — KNFSD cache, VPC Lattice resource endpoint, and the Deadline Cloud service-managed fleet. Must be a region where Deadline Cloud is available."
  type        = string
  default     = "us-west-2"
}

variable "origin_region" {
  description = "Region B — the FSx for OpenZFS origin filer. Must differ from compute_region; the inter-region distance is what the cache absorbs."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.origin_region != var.compute_region
    error_message = "origin_region must differ from compute_region for a cross-region cache demonstration."
  }
}

variable "compute_az_suffix" {
  description = "AZ letter for the compute subnet (KNFSD is single-subnet), e.g. \"a\"."
  type        = string
  default     = "a"
}

variable "origin_az_suffix" {
  description = "AZ letter for the origin subnet, e.g. \"a\"."
  type        = string
  default     = "a"
}

variable "compute_vpc_cidr" {
  description = "CIDR for the compute VPC (region A). Must not overlap origin_vpc_cidr."
  type        = string
  default     = "10.10.0.0/16"
}

variable "origin_vpc_cidr" {
  description = "CIDR for the origin VPC (region B). Must not overlap compute_vpc_cidr."
  type        = string
  default     = "10.20.0.0/16"
}

variable "name_prefix" {
  description = "Prefix applied to created resource names. Keep short; some names must be globally unique per account."
  type        = string
  default     = "dl-knfsd-xr"

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{0,20}[a-zA-Z0-9]$", var.name_prefix))
    error_message = "name_prefix must be 2-22 chars, alphanumeric or hyphen, and not start/end with a hyphen."
  }
}

variable "knfsd_proxy_ami" {
  description = <<-EOT
    AMI ID of the KNFSD proxy image built with Packer from awslabs/knfsd-file-cache
    (see image/ in that repo), built in compute_region. There is no public/managed
    AMI; you must build it first. See the README "Build the KNFSD AMI" step.
  EOT
  type        = string

  validation {
    condition     = can(regex("^ami-[0-9a-f]{8}([0-9a-f]{9})?$", var.knfsd_proxy_ami))
    error_message = "knfsd_proxy_ami must be a valid AMI ID."
  }
}

variable "knfsd_instance_type" {
  description = "EC2 instance type for KNFSD proxies. i3en/i4i families give local NVMe for the L2 (FS-Cache) tier."
  type        = string
  default     = "i3en.2xlarge"
}

variable "knfsd_node_count" {
  description = "Number of KNFSD proxy nodes in the cluster."
  type        = number
  default     = 1
}

variable "knfsd_fsid_mode" {
  description = <<-EOT
    How KNFSD assigns FSIDs: "local", "static", or "external". "external" adds an
    RDS database + Lambda for multi-node FSID consistency; use "local" for a
    single node (default) to avoid that overhead.
  EOT
  type        = string
  default     = "local"

  validation {
    condition     = contains(["local", "static", "external"], var.knfsd_fsid_mode)
    error_message = "knfsd_fsid_mode must be local, static, or external."
  }
}

variable "fsx_storage_capacity_gib" {
  description = "FSx for OpenZFS storage capacity in GiB."
  type        = number
  default     = 1024
}

variable "fsx_throughput_capacity_mbps" {
  description = "FSx for OpenZFS throughput capacity in MB/s. Allowed: 64,128,256,512,1024,2048,3072,4096."
  type        = number
  default     = 512
}

variable "deadline_worker_os" {
  description = "Operating system family for the SMF workers. Only LINUX is supported: the host configuration is a bash script (mount, dnf/apt-get, chmod) that cannot run on Windows."
  type        = string
  default     = "LINUX"

  validation {
    condition     = contains(["LINUX"], var.deadline_worker_os)
    error_message = "deadline_worker_os must be LINUX. This sample's host configuration script only supports Linux workers."
  }
}

variable "fleet_min_workers" {
  description = "Minimum worker count for the service-managed fleet."
  type        = number
  default     = 0
}

variable "fleet_max_workers" {
  description = "Maximum worker count for the service-managed fleet."
  type        = number
  default     = 2
}

variable "fleet_market_type" {
  description = "EC2 market type for fleet workers: \"spot\" or \"on-demand\". Spot avoids the small OnDemand vCPU quota."
  type        = string
  default     = "spot"

  validation {
    condition     = contains(["spot", "on-demand"], var.fleet_market_type)
    error_message = "fleet_market_type must be spot or on-demand."
  }
}

variable "fleet_vcpu_min" {
  description = "Minimum vCPUs per fleet worker instance."
  type        = number
  default     = 2
}

variable "fleet_vcpu_max" {
  description = "Maximum vCPUs per fleet worker instance."
  type        = number
  default     = 8
}

variable "nfs_mount_path" {
  description = "Absolute path on workers where the KNFSD-cached NFS share is mounted."
  type        = string
  default     = "/mnt/knfsd"
}

variable "fsx_export_path" {
  description = <<-EOT
    The NFS export path KNFSD re-exports (verbatim from the FSx origin). FSx for
    OpenZFS exports its root volume at /fsx, so workers mount <endpoint>:/fsx —
    NOT ":/". Mounting the wrong path returns "access denied by server".
  EOT
  type        = string
  default     = "/fsx"
}

variable "tags" {
  description = "Additional tags applied to resources created directly by this example."
  type        = map(string)
  default     = {}
}
