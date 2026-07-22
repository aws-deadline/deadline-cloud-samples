output "farm_id" {
  description = "Deadline Cloud farm ID. Use with the deadline CLI (--farm-id)."
  value       = awscc_deadline_farm.this.farm_id
}

output "queue_id" {
  description = "Deadline Cloud queue ID. Submit jobs here (--queue-id)."
  value       = awscc_deadline_queue.this.queue_id
}

output "fleet_id" {
  description = "Service-managed fleet ID."
  value       = awscc_deadline_fleet.this.fleet_id
}

output "fsx_origin_dns_name" {
  description = "FSx for OpenZFS origin DNS name (the filer KNFSD caches)."
  value       = aws_fsx_openzfs_file_system.origin.dns_name
}

output "knfsd_nlb_dns_name" {
  description = "Private DNS name of the KNFSD Network Load Balancer."
  value       = module.knfsd.dns_name
}

output "knfsd_nlb_ip_address" {
  description = "Private IP of the KNFSD NLB (target of the Lattice resource config)."
  value       = module.knfsd.loadbalancer_ipaddress
}

output "resource_configuration_arn" {
  description = "VPC Lattice resource configuration ARN attached to the fleet."
  value       = aws_vpclattice_resource_configuration.knfsd_nfs.arn
}

output "worker_resource_endpoint_dns_name" {
  description = "Deadline-managed private DNS name SMF workers use to reach the KNFSD share."
  value       = "${aws_vpclattice_resource_configuration.knfsd_nfs.id}.resource-endpoints.deadline.${var.compute_region}.amazonaws.com"
}

output "worker_nfs_mount_path" {
  description = "Path where workers mount the KNFSD-cached share."
  value       = var.nfs_mount_path
}
