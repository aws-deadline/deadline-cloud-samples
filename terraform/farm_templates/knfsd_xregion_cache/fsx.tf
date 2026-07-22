# Layer 1 — Origin filer: Amazon FSx for OpenZFS, in the ORIGIN REGION (region B).
#
# FSx for OpenZFS is the distant origin that KNFSD caches. It natively serves
# NFSv3 (KNFSD's primary re-export path) and behaves like a bounded-throughput
# "filer" — exactly the workload a caching proxy is designed to offload. Here it
# stands in for an on-premises or otherwise-distant filer: the KNFSD cache in
# region A reaches it across the VPC peering link, so cache misses pay
# cross-region latency and data-transfer cost while cache hits are served locally.
#
# NFS export options mirror the upstream knfsd-file-cache "examples/fsx-zfs" so
# KNFSD's showmount-based export auto-discovery works.

resource "aws_fsx_openzfs_file_system" "origin" {
  provider                        = aws.origin
  deployment_type                 = "SINGLE_AZ_1"
  storage_capacity                = var.fsx_storage_capacity_gib
  subnet_ids                      = [aws_subnet.origin.id]
  throughput_capacity             = var.fsx_throughput_capacity_mbps
  automatic_backup_retention_days = 0
  copy_tags_to_volumes            = true
  delete_options                  = ["DELETE_CHILD_VOLUMES_AND_SNAPSHOTS"]
  security_group_ids              = [aws_security_group.fsx.id]
  skip_final_backup               = true
  storage_type                    = "SSD"

  root_volume_configuration {
    # "crossmnt" lets clients traverse into child volumes over a single mount.
    # "no_root_squash" keeps this example simple; tighten for production.
    nfs_exports {
      client_configurations {
        clients = "*"
        options = ["rw", "crossmnt", "async", "no_root_squash"]
      }
    }
    copy_tags_to_snapshots = true
    data_compression_type  = "NONE"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-fsx-origin" })

  # FSx validates at creation time that its security group already permits
  # inbound NFS on 2049. The ingress rules are separate resources that only
  # depend on the SG, not on this file system, so without an explicit ordering
  # Terraform may create FSx before the rules exist and fail nondeterministically.
  depends_on = [aws_vpc_security_group_ingress_rule.fsx_from_compute]
}

# SINGLE_AZ_1 FSx for OpenZFS does not populate `endpoint_ip_address` (that
# attribute is only set for Multi-AZ, which has a floating management IP). The
# file system's private IP is the primary network interface's IP, which we look
# up here. KNFSD (in the compute region) reaches this IP over the peering link.
data "aws_network_interface" "fsx" {
  provider = aws.origin
  id       = aws_fsx_openzfs_file_system.origin.network_interface_ids[0]
}

# Security group for the FSx origin (region B). Ingress allows NFS from the
# COMPUTE VPC's CIDR, reached across the peering link — that is where the KNFSD
# proxies live. FSx validates at creation time that the SG already permits NFS
# on 2049, and the KNFSD SG is in another region/VPC, so we scope to the compute
# CIDR rather than a referenced SG (also matches the upstream fsx-zfs example).
resource "aws_security_group" "fsx" {
  provider    = aws.origin
  name_prefix = "${var.name_prefix}-fsx-origin-"
  description = "FSx for OpenZFS origin - NFS from the compute VPC (KNFSD)"
  vpc_id      = aws_vpc.origin.id

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-fsx-origin-sg" })
}

# NFS + rpcbind + OpenZFS management ports, from the compute VPC CIDR.
# Port set matches the upstream fsx-zfs example.
locals {
  fsx_ingress_ports = {
    nfs_tcp        = { from = 2049, to = 2049, proto = "tcp" }
    nfs_udp        = { from = 2049, to = 2049, proto = "udp" }
    rpcbind_tcp    = { from = 111, to = 111, proto = "tcp" }
    rpcbind_udp    = { from = 111, to = 111, proto = "udp" }
    openzfs_mgmt_t = { from = 20001, to = 20003, proto = "tcp" }
    openzfs_mgmt_u = { from = 20001, to = 20003, proto = "udp" }
  }
}

resource "aws_vpc_security_group_ingress_rule" "fsx_from_compute" {
  provider = aws.origin
  for_each = local.fsx_ingress_ports

  security_group_id = aws_security_group.fsx.id
  cidr_ipv4         = var.compute_vpc_cidr
  from_port         = each.value.from
  to_port           = each.value.to
  ip_protocol       = each.value.proto
  description       = "NFS/rpcbind/openzfs-mgmt from compute VPC (${each.key})"
}
