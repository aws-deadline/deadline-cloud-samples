# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""AWS Deadline Cloud service limits relevant to the sample assets.

These values come from the AWS Deadline Cloud API model (the ``deadline``
botocore service definition, API version ``2023-10-12``). They are the hard
limits the service enforces on request inputs; a sample that exceeds one of them
will be rejected by the corresponding API call. Keeping the checks pinned to the
documented service limits is what lets CI catch the problem before a customer
does.
"""

# Maximum length, in characters, of a fleet host configuration script.
# Model shape: HostConfigurationScript (string, max=15000).
# Used by UpdateFleet's hostConfiguration.scriptBody. A script longer than this
# is rejected by the service -- this is the limit that previously slipped
# through to a customer.
HOST_CONFIGURATION_SCRIPT_MAX_CHARS = 15000

# Bounds, in seconds, on HostConfiguration.scriptTimeoutSeconds.
# Model shape: HostConfigurationScriptTimeoutSeconds (integer, min=300, max=3600).
HOST_CONFIGURATION_SCRIPT_TIMEOUT_MIN_SECONDS = 300
HOST_CONFIGURATION_SCRIPT_TIMEOUT_MAX_SECONDS = 3600

# Maximum length, in characters, of a serialized queue environment template
# passed to the service. Model shape: EnvironmentTemplate (string, max=15000).
ENVIRONMENT_TEMPLATE_MAX_CHARS = 15000

# Maximum length, in characters, of a serialized job template passed to
# CreateJob. Model shape: JobTemplate (string, max=1000000).
JOB_TEMPLATE_MAX_CHARS = 1000000
