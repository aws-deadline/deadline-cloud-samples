# Layer 3a — The bridge: VPC Lattice resource gateway + resource configuration
#                        + AWS RAM share to the Deadline Cloud service.
#
# Deadline Cloud service-managed fleet (SMF) workers run in an AWS-managed VPC,
# not yours. The "resource endpoints" feature (launched 2025-07, powered by AWS
# PrivateLink/VPC Lattice) lets those workers reach resources in YOUR VPC.
#
# This wiring follows the official reference template:
#   github.com/aws-deadline/deadline-cloud-samples
#     -> cloudformation/farm_templates/smf_vpc_fsx
#
# Three objects are required:
#   1. A VPC Lattice *resource gateway* (ingress point in your VPC).
#   2. A VPC Lattice *resource configuration* targeting the KNFSD NLB.
#   3. An AWS RAM *resource share* granting the Deadline service principal
#      (fleets.deadline.amazonaws.com) access to the resource configuration.
# The fleet then references the resource configuration ARN (see deadline.tf).
#
# IMPORTANT — how workers reach it: workers do NOT use the KNFSD/FSx DNS name.
# Deadline exposes a managed private domain per resource configuration:
#   <resource_config_id>.resource-endpoints.deadline.<region>.amazonaws.com
# That is the hostname the fleet host-configuration script mounts (deadline.tf).

# The resource gateway is the in-VPC ingress point Lattice uses to reach targets.
# The reference template spans multiple subnets/AZs; this single-subnet example
# keeps the gateway, KNFSD, and FSx in one AZ. For production, give the gateway
# subnets in every AZ your resource might live in.
resource "aws_vpclattice_resource_gateway" "knfsd" {
  name               = "${var.name_prefix}-rgw"
  vpc_id             = aws_vpc.compute.id
  subnet_ids         = [aws_subnet.compute.id]
  security_group_ids = [aws_security_group.resource_gateway.id]
  ip_address_type    = "IPV4"

  tags = merge(var.tags, { Name = "${var.name_prefix}-rgw" })
}

# The gateway ENIs must be allowed to reach the KNFSD NLB across the NFS RPC
# port set that KNFSD's load balancer exposes.
resource "aws_security_group" "resource_gateway" {
  name        = "${var.name_prefix}-rgw-sg"
  description = "VPC Lattice resource gateway to KNFSD NLB (NFS RPC ports)"
  vpc_id      = aws_vpc.compute.id

  tags = merge(var.tags, { Name = "${var.name_prefix}-rgw-sg" })
}

# KNFSD's NLB listens on the full NFSv3 RPC port set (TCP+UDP):
#   111 (rpcbind), 2049 (nfsd), 20048 (mountd), 20050-20055 (lockd/statd/cb).
# We open the contiguous span 111 + 2049 + 20048-20055 for simplicity.
locals {
  knfsd_nfs_port_ranges = ["111", "2049", "20048-20055"]
}

resource "aws_vpc_security_group_egress_rule" "rgw_to_knfsd_tcp" {
  for_each                     = toset(local.knfsd_nfs_port_ranges)
  security_group_id            = aws_security_group.resource_gateway.id
  referenced_security_group_id = module.knfsd.knfsd_security_group_id
  from_port                    = tonumber(split("-", each.value)[0])
  to_port                      = tonumber(element(split("-", each.value), length(split("-", each.value)) - 1))
  ip_protocol                  = "tcp"
  description                  = "NFS RPC (tcp ${each.value}) to KNFSD NLB"
}

# Allow the resource gateway to reach the KNFSD NLB. In loadbalancer mode the
# module's knfsd_security_group_id is the NLB's SG.
resource "aws_vpc_security_group_ingress_rule" "knfsd_from_rgw_tcp" {
  for_each                     = toset(local.knfsd_nfs_port_ranges)
  security_group_id            = module.knfsd.knfsd_security_group_id
  referenced_security_group_id = aws_security_group.resource_gateway.id
  from_port                    = tonumber(split("-", each.value)[0])
  to_port                      = tonumber(element(split("-", each.value), length(split("-", each.value)) - 1))
  ip_protocol                  = "tcp"
  description                  = "NFS RPC (tcp ${each.value}) from VPC Lattice resource gateway"
}

# The resource configuration exposes the KNFSD NLB by its private IP over the
# NFS RPC port set. Its ARN is what the Deadline Cloud fleet references. The
# reference template targets an IpResource (not DNS), which is simpler and
# avoids in-VPC DNS-resolution setup.
resource "aws_vpclattice_resource_configuration" "knfsd_nfs" {
  name                        = "${var.name_prefix}-knfsd-nfs"
  resource_gateway_identifier = aws_vpclattice_resource_gateway.knfsd.id

  port_ranges = local.knfsd_nfs_port_ranges
  protocol    = "TCP"

  resource_configuration_definition {
    ip_resource {
      ip_address = module.knfsd.loadbalancer_ipaddress
    }
  }

  # Required so the configuration can be shared (via RAM) into the Deadline
  # service network.
  allow_association_to_shareable_service_network = true

  tags = merge(var.tags, { Name = "${var.name_prefix}-knfsd-nfs" })
}

# AWS RAM share granting the Deadline Cloud service principal access to the
# resource configuration. Without this, the fleet cannot attach the endpoint.
#
# This uses the AWSCC provider (not hashicorp/aws) because sharing to a SERVICE
# principal (fleets.deadline.amazonaws.com) requires both the `principals` and
# `sources` arguments together — exactly as the reference CloudFormation
# template does. The hashicorp/aws ram_principal_association resource models
# only account/org principals and has no `sources` field.
resource "awscc_ram_resource_share" "deadline" {
  name = "${var.name_prefix}-deadline-share"
  # Must allow "external" principals: a service principal
  # (fleets.deadline.amazonaws.com) is not an in-organization principal, so a
  # share restricted to the org is rejected with "can only be shared within
  # your AWS Organization". The reference CloudFormation template leaves this at
  # its permissive default for the same reason.
  allow_external_principals = true
  resource_arns             = [aws_vpclattice_resource_configuration.knfsd_nfs.arn]
  principals                = ["fleets.deadline.amazonaws.com"]
  sources                   = [data.aws_caller_identity.current.account_id]
}
