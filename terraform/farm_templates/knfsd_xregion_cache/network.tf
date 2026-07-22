# Cross-region networking.
#
# Two purpose-built VPCs with non-overlapping CIDRs (default VPCs can't be used
# here — every region's default VPC is 172.31.0.0/16, and you cannot peer
# overlapping CIDRs), joined by a cross-region VPC peering connection:
#
#   Compute VPC (region A, ${var.compute_vpc_cidr})  <-- peering -->  Origin VPC (region B, ${var.origin_vpc_cidr})
#     KNFSD + Lattice + fleet                                            FSx for OpenZFS
#
# The peering link is the "long, expensive" path that a read cache is meant to
# absorb. KNFSD mounts FSx over this link; workers then read from KNFSD locally.

# ---- Compute VPC (region A) ----------------------------------------------

resource "aws_vpc" "compute" {
  cidr_block           = var.compute_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-compute-vpc" })
}

resource "aws_subnet" "compute" {
  vpc_id                  = aws_vpc.compute.id
  cidr_block              = cidrsubnet(var.compute_vpc_cidr, 8, 1)
  availability_zone       = "${var.compute_region}${var.compute_az_suffix}"
  map_public_ip_on_launch = false
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-compute-subnet" })
}

resource "aws_internet_gateway" "compute" {
  vpc_id = aws_vpc.compute.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-compute-igw" })
}

# NAT so the KNFSD instances (private subnet) can reach the internet for the
# worker agent bootstrap, package installs, etc.
resource "aws_eip" "compute_nat" {
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name_prefix}-compute-nat-eip" })
}

resource "aws_subnet" "compute_public" {
  vpc_id                  = aws_vpc.compute.id
  cidr_block              = cidrsubnet(var.compute_vpc_cidr, 8, 0)
  availability_zone       = "${var.compute_region}${var.compute_az_suffix}"
  map_public_ip_on_launch = true
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-compute-public" })
}

resource "aws_nat_gateway" "compute" {
  allocation_id = aws_eip.compute_nat.id
  subnet_id     = aws_subnet.compute_public.id
  tags          = merge(var.tags, { Name = "${var.name_prefix}-compute-nat" })
  depends_on    = [aws_internet_gateway.compute]
}

resource "aws_route_table" "compute_public" {
  vpc_id = aws_vpc.compute.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.compute.id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-compute-public-rt" })
}

resource "aws_route_table_association" "compute_public" {
  subnet_id      = aws_subnet.compute_public.id
  route_table_id = aws_route_table.compute_public.id
}

resource "aws_route_table" "compute_private" {
  vpc_id = aws_vpc.compute.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.compute.id
  }
  # Reach the origin VPC over the peering connection.
  route {
    cidr_block                = var.origin_vpc_cidr
    vpc_peering_connection_id = aws_vpc_peering_connection.xregion.id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-compute-private-rt" })
}

resource "aws_route_table_association" "compute_private" {
  subnet_id      = aws_subnet.compute.id
  route_table_id = aws_route_table.compute_private.id
}

# ---- Origin VPC (region B) -----------------------------------------------

resource "aws_vpc" "origin" {
  provider             = aws.origin
  cidr_block           = var.origin_vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-origin-vpc" })
}

resource "aws_subnet" "origin" {
  provider          = aws.origin
  vpc_id            = aws_vpc.origin.id
  cidr_block        = cidrsubnet(var.origin_vpc_cidr, 8, 1)
  availability_zone = "${var.origin_region}${var.origin_az_suffix}"
  tags              = merge(var.tags, { Name = "${var.name_prefix}-origin-subnet" })
}

resource "aws_route_table" "origin" {
  provider = aws.origin
  vpc_id   = aws_vpc.origin.id
  # Return path to the compute VPC over the peering connection.
  route {
    cidr_block                = var.compute_vpc_cidr
    vpc_peering_connection_id = aws_vpc_peering_connection.xregion.id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-origin-rt" })
}

resource "aws_route_table_association" "origin" {
  provider       = aws.origin
  subnet_id      = aws_subnet.origin.id
  route_table_id = aws_route_table.origin.id
}

# ---- Cross-region VPC peering --------------------------------------------

# Requester lives in the compute region; peer is the origin VPC in region B.
resource "aws_vpc_peering_connection" "xregion" {
  vpc_id      = aws_vpc.compute.id
  peer_vpc_id = aws_vpc.origin.id
  peer_region = var.origin_region
  auto_accept = false # cross-region peering cannot auto-accept in one call
  tags        = merge(var.tags, { Name = "${var.name_prefix}-xregion-peering" })
}

# Accepter runs in the origin region.
resource "aws_vpc_peering_connection_accepter" "xregion" {
  provider                  = aws.origin
  vpc_peering_connection_id = aws_vpc_peering_connection.xregion.id
  auto_accept               = true
  tags                      = merge(var.tags, { Name = "${var.name_prefix}-xregion-peering-accepter" })
}
