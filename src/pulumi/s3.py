import json

import pulumi
import pulumi_aws as aws
import pulumi_command as command

from settings import config, location

LOCK_DAYS = 7

# Hetzner Object Storage speaks S3 and hcloud has no bucket resource, so the
# AWS provider manages the Litestream bucket. The key is made in the console.
endpoint = f"https://{location}.your-objectstorage.com"
access_key = config.require_secret("s3AccessKey")
secret_key = config.require_secret("s3SecretKey")

provider = aws.Provider(
    "hetzner-s3",
    region=location,
    access_key=access_key,
    secret_key=secret_key,
    endpoints=[aws.ProviderEndpointArgs(s3=endpoint)],
    s3_use_path_style=True,
    skip_credentials_validation=True,
    skip_metadata_api_check=True,
    skip_region_validation=True,
    skip_requesting_account_id=True,
)

bucket = aws.s3.Bucket(
    "backups",
    bucket=config.require("bucket"),
    # Object lock can only be turned on when the bucket is created.
    object_lock_enabled=True,
    # Hetzner reports every bucket as us-east-1, and a region change would
    # replace the bucket.
    opts=pulumi.ResourceOptions(provider=provider, ignore_changes=["region"]),
)

# A stolen key on the box can hide backups but not destroy them for a week.
aws.s3.BucketObjectLockConfiguration(
    "backups",
    bucket=bucket.bucket,
    rule=aws.s3.BucketObjectLockConfigurationRuleArgs(
        default_retention=aws.s3.BucketObjectLockConfigurationRuleDefaultRetentionArgs(
            mode="COMPLIANCE",
            days=LOCK_DAYS,
        ),
    ),
    opts=pulumi.ResourceOptions(provider=provider),
)

# Litestream deletes compacted files all the time. Clear the old versions once
# their lock has run out.
# shortcut: aws.s3.BucketLifecycleConfiguration never finishes against Hetzner
# because it waits for an AWS-only header, so this needs the aws CLI where
# pulumi runs. Switch back once hashicorp/terraform-provider-aws#49902 ships.
command.local.Command(
    "backups-lifecycle",
    create=bucket.bucket.apply(
        lambda name: f"aws s3api put-bucket-lifecycle-configuration --endpoint-url {endpoint}"
        f" --bucket {name} --lifecycle-configuration file:///dev/stdin"
    ),
    stdin=json.dumps(
        {
            "Rules": [
                {
                    "ID": "expire-old-versions",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "NoncurrentVersionExpiration": {"NoncurrentDays": LOCK_DAYS},
                }
            ]
        }
    ),
    environment={
        "AWS_ACCESS_KEY_ID": access_key,
        "AWS_SECRET_ACCESS_KEY": secret_key,
        "AWS_DEFAULT_REGION": location,
    },
)
