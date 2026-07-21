# Layer 2 — Caching proxy: awslabs/knfsd-file-cache.
#
# The KNFSD module deploys an Auto Scaling Group of NFS re-export proxies fronted
# by a Network Load Balancer (TRAFFIC_MODE = "loadbalancer"). Each proxy mounts
# the FSx origin over NFSv3 and re-exports it, caching in RAM (L1) and on local
# NVMe via FS-Cache (L2). We front it with the NLB because VPC Lattice resource
# configurations target a stable IP/DNS, and the NLB gives us exactly that.
#
# The module is pinned to a released tag. Terraform shallow-clones the whole repo
# for a git source, so `terraform init` needs network + git access to GitHub.

module "knfsd" {
  source = "github.com/awslabs/knfsd-file-cache//deployment/terraform-module-knfsd?ref=v1.1.0-beta.1"

  SUBNET         = aws_subnet.compute.id
  PROXY_AMI      = var.knfsd_proxy_ami
  PROXY_BASENAME = var.name_prefix
  INSTANCE_TYPE  = var.knfsd_instance_type
  KNFSD_NODES    = var.knfsd_node_count

  # NLB front end so Lattice has a stable target. The module creates the NLB,
  # target groups, and a private Route 53 CNAME.
  TRAFFIC_MODE = "loadbalancer"

  # Point the cache at the FSx origin by its private IP, reached across the VPC
  # peering link. We use the IP — not the DNS name — because FSx's private
  # Route 53 name does not resolve from the compute region; the IP is routable
  # over peering. For SINGLE_AZ_1 the IP is the primary ENI's private IP (the
  # endpoint_ip_address attribute is only populated for Multi-AZ deployments).
  # KNFSD auto-detects exports via `showmount -e <ip>` (NFSv3).
  EXPORT_HOST_AUTO_DETECT = data.aws_network_interface.fsx.private_ip
  EXPORT_OPTIONS          = "insecure"
  NFS_MOUNT_VERSION       = "3"
  DISABLED_NFS_VERSIONS   = "4.0,4.1,4.2"

  # FSID assignment. "external" (the module default) provisions an RDS database
  # and a Lambda so a MULTI-node cluster hands out consistent FSIDs. This
  # single-node example uses "local", which needs neither — avoiding the RDS
  # cost and the Lambda's alpine/Docker build. Set to "external" if you scale
  # KNFSD_NODES above 1 and need FSID stability across nodes.
  FSID_MODE = var.knfsd_fsid_mode

  INSTANCE_TAGS = merge(var.tags, { Name = "${var.name_prefix}-knfsd-proxy" })

  # KNFSD runs `showmount` against the origin at launch, so the origin and the
  # full cross-region network path (peering + routes both ways) must exist first.
  depends_on = [
    aws_fsx_openzfs_file_system.origin,
    aws_vpc_peering_connection_accepter.xregion,
    aws_route_table.compute_private,
    aws_route_table.origin,
  ]
}
