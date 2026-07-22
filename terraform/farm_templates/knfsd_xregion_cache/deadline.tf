# Layer 3b — Deadline Cloud: farm, queue, service-managed fleet.
#
# Deadline Cloud is not in the hashicorp/aws provider; it is exposed through the
# AWSCC (Cloud Control) provider, which is generated from the CloudFormation
# registry (AWS::Deadline::*). The AWSCC schema carries the resource-endpoints
# field this example depends on:
#   - service_managed_ec_2.vpc_configuration.resource_configuration_arns
#     (resource endpoints -> reach the KNFSD NLB in your VPC)

# ---- Farm ----------------------------------------------------------------

resource "awscc_deadline_farm" "this" {
  display_name = "${var.name_prefix}-farm"
  description  = "Farm for the KNFSD + FSx for OpenZFS resource-endpoint example"
}

# ---- Queue ---------------------------------------------------------------

resource "awscc_deadline_queue" "this" {
  farm_id      = awscc_deadline_farm.this.farm_id
  display_name = "${var.name_prefix}-queue"
  description  = "Queue that runs jobs reading from the KNFSD-cached NFS share"

  # Job run-as: use the worker agent's own OS user for simplicity in this example.
  job_run_as_user = {
    run_as = "WORKER_AGENT_USER"
  }

  role_arn = aws_iam_role.queue.arn
}

# ---- Service-managed fleet ----------------------------------------------

resource "awscc_deadline_fleet" "this" {
  farm_id          = awscc_deadline_farm.this.farm_id
  display_name     = "${var.name_prefix}-smf"
  description      = "Service-managed fleet reaching the KNFSD cache via a resource endpoint"
  role_arn         = aws_iam_role.fleet.arn
  min_worker_count = var.fleet_min_workers
  max_worker_count = var.fleet_max_workers

  # The fleet's vpc_configuration references the resource configuration, which
  # the Deadline service can only see once the RAM share to
  # fleets.deadline.amazonaws.com exists. Order fleet creation after the share.
  depends_on = [awscc_ram_resource_share.deadline]

  configuration = {
    service_managed_ec_2 = {
      instance_capabilities = {
        cpu_architecture_type = "x86_64"
        os_family             = var.deadline_worker_os
        v_cpu_count = {
          min = var.fleet_vcpu_min
          max = var.fleet_vcpu_max
        }
        memory_mi_b = {
          min = 8192
          max = 32768
        }
      }

      # Spot by default: the Deadline "OnDemand vCPUs per region" quota is small
      # (50 by default) and easily exhausted on shared accounts, whereas the Spot
      # vCPU quota is effectively unlimited. Spot is also the norm for render
      # fleets. Override with fleet_market_type = "on-demand" if needed.
      instance_market_options = {
        type = var.fleet_market_type
      }

      # NEW (2025-07): resource endpoints. Attaching the VPC Lattice resource
      # configuration ARN lets these AWS-managed SMF workers reach the KNFSD NLB
      # in the customer VPC via VPC Lattice. The RAM share in lattice.tf must
      # grant the fleets.deadline.amazonaws.com principal access to this ARN,
      # or attachment fails.
      vpc_configuration = {
        resource_configuration_arns = [
          aws_vpclattice_resource_configuration.knfsd_nfs.arn
        ]
      }
    }
  }

  # Runs on every worker at startup: mount the KNFSD-cached NFS share.
  #
  # Workers reach the resource configuration through Deadline's managed private
  # domain, NOT the KNFSD/FSx DNS name:
  #   <resource_config_id>.resource-endpoints.deadline.<region>.amazonaws.com
  host_configuration = {
    script_timeout_seconds = 300
    script_body = templatefile("${path.module}/templates/host-configuration.sh.tftpl", {
      resource_config_id = aws_vpclattice_resource_configuration.knfsd_nfs.id
      region             = var.compute_region
      nfs_mount_path     = var.nfs_mount_path
      # KNFSD re-exports the FSx OpenZFS export path verbatim; mount that path.
      nfs_export_path = var.fsx_export_path
    })
  }
}

# ---- Associate the queue with the fleet ----------------------------------

resource "awscc_deadline_queue_fleet_association" "this" {
  farm_id  = awscc_deadline_farm.this.farm_id
  queue_id = awscc_deadline_queue.this.queue_id
  fleet_id = awscc_deadline_fleet.this.fleet_id
}
