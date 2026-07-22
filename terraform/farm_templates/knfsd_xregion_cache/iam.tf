# IAM roles for the Deadline Cloud fleet workers and the queue.

data "aws_partition" "current" {}
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ---- Fleet worker role ---------------------------------------------------
# Assumed by the Deadline Cloud service on behalf of workers.

data "aws_iam_policy_document" "fleet_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["credentials.deadline.amazonaws.com"]
    }
    # Confused-deputy scoping, per the canonical starter-farm fleet role.
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [awscc_deadline_farm.this.arn]
    }
  }
}

resource "aws_iam_role" "fleet" {
  name               = "${var.name_prefix}-fleet-role"
  assume_role_policy = data.aws_iam_policy_document.fleet_assume.json
  tags               = var.tags
}

# Baseline worker permissions. AWSDeadlineCloud-FleetWorker grants the Deadline
# API actions (UpdateWorker, AssumeQueueRoleForWorker, etc.) but NOT CloudWatch
# Logs access — that must be granted separately (see below).
resource "aws_iam_role_policy_attachment" "fleet_worker" {
  role       = aws_iam_role.fleet.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AWSDeadlineCloud-FleetWorker"
}

# FleetWorkerLogs: the worker agent's first action after registering is to
# create its CloudWatch log stream. Without logs:CreateLogStream the agent's
# initialization fails and the worker never leaves CREATED — this is the
# missing piece. Mirrors the fleetRole in the Deadline Cloud starter-farm
# reference template.
data "aws_iam_policy_document" "fleet_worker_logs" {
  statement {
    sid       = "CreateLogStream"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream"]
    resources = ["arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:*:/aws/deadline/${awscc_deadline_farm.this.farm_id}/*"]
    condition {
      test     = "ForAnyValue:StringEquals"
      variable = "aws:CalledVia"
      values   = ["deadline.amazonaws.com"]
    }
  }
  statement {
    sid       = "WorkerAndSessionLogs"
    effect    = "Allow"
    actions   = ["logs:PutLogEvents", "logs:GetLogEvents"]
    resources = ["arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:*:/aws/deadline/${awscc_deadline_farm.this.farm_id}/*"]
  }
}

resource "aws_iam_role_policy" "fleet_worker_logs" {
  name   = "${var.name_prefix}-fleet-worker-logs"
  role   = aws_iam_role.fleet.id
  policy = data.aws_iam_policy_document.fleet_worker_logs.json
}

# ---- Queue role ----------------------------------------------------------
# Session role handed to jobs. This example grants only CloudWatch Logs, which
# is all the bundled seed/benchmark jobs need (they run embedded scripts and
# read/write the NFS mount; the queue has no job attachments). If you enable job
# attachments or read other data, add the S3 permissions your jobs require.

data "aws_iam_policy_document" "queue_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["credentials.deadline.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [awscc_deadline_farm.this.arn]
    }
  }
}

resource "aws_iam_role" "queue" {
  name               = "${var.name_prefix}-queue-role"
  assume_role_policy = data.aws_iam_policy_document.queue_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "queue" {
  statement {
    sid    = "Logs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:GetLogEvents",
    ]
    resources = [
      "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/deadline/*"
    ]
  }
}

resource "aws_iam_role_policy" "queue" {
  name   = "${var.name_prefix}-queue-policy"
  role   = aws_iam_role.queue.id
  policy = data.aws_iam_policy_document.queue.json
}
