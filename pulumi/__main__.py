import json
from pathlib import Path

import pulumi
import pulumi_aws as aws
import pulumi_command as command
import pulumi_hcloud as hcloud

LOCK_DAYS = 7
# Same names as the services in compose.yml. Each gets env/<name>.env.
APPS = ["cadence", "gatekeeper"]

config = pulumi.Config()

# Every key that may log in as deploy: your laptop and the CI deploy key.
authorized_keys: list[str] = config.require_object("authorizedKeys")
server_type = config.get("serverType") or "cpx12"
# Helsinki. Closest Hetzner location to Norway.
location = config.get("location") or "hel1"

keys = [
    hcloud.SshKey(f"kumo-{i}", name=f"kumo-{i}", public_key=key)
    for i, key in enumerate(authorized_keys)
]

firewall = hcloud.Firewall(
    "web",
    name="web",
    rules=[
        hcloud.FirewallRuleArgs(
            direction="in",
            protocol=protocol,
            port=port,
            source_ips=["0.0.0.0/0", "::/0"],
        )
        for protocol, port in [("tcp", "22"), ("tcp", "80"), ("tcp", "443"), ("udp", "443")]
    ],
)

# JSON is valid YAML, so the key list drops straight into cloud-init.
user_data = (
    (Path(__file__).parent / "cloud-init.yaml")
    .read_text()
    .replace("AUTHORIZED_KEYS", json.dumps(authorized_keys))
)

server = hcloud.Server(
    "kumo",
    name="kumo",
    image="debian-12",
    server_type=server_type,
    location=location,
    ssh_keys=[key.id for key in keys],
    firewall_ids=[firewall.id.apply(int)],
    user_data=user_data,
    # Data lives on this disk. Litestream can rebuild it, but not by accident.
    delete_protection=True,
    rebuild_protection=True,
)

pulumi.export("ipv4", server.ipv4_address)

# Hetzner Object Storage speaks S3 and hcloud has no bucket resource, so the
# AWS provider manages the Litestream bucket. The key is made in the console.
endpoint = f"https://{location}.your-objectstorage.com"
s3 = aws.Provider(
    "hetzner-s3",
    region=location,
    access_key=config.require_secret("s3AccessKey"),
    secret_key=config.require_secret("s3SecretKey"),
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
    opts=pulumi.ResourceOptions(provider=s3, ignore_changes=["region"]),
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
    opts=pulumi.ResourceOptions(provider=s3),
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
        "AWS_ACCESS_KEY_ID": config.require_secret("s3AccessKey"),
        "AWS_SECRET_ACCESS_KEY": config.require_secret("s3SecretKey"),
        "AWS_DEFAULT_REGION": location,
    },
)

# Everything below is written to the box over SSH as deploy, through your SSH
# agent. Editing these files on the box is undone by the next `pulumi up`.
connection = command.remote.ConnectionArgs(host=server.ipv4_address, user="deploy")

# Docker and /srv/infra come from cloud-init, so wait for first boot to finish.
first_boot = command.remote.Command(
    "first-boot",
    connection=connection,
    create="sudo cloud-init status --wait >/dev/null",
)


def env_file(name: str, path: str, content: pulumi.Input[str]) -> None:
    command.remote.Command(
        name,
        connection=connection,
        create=f"umask 077 && mkdir -p $(dirname {path}) && cat > {path}",
        stdin=content,
        opts=pulumi.ResourceOptions(depends_on=[first_boot]),
    )


def render(values: dict[str, str]) -> str:
    return "".join(f"{key}={value}\n" for key, value in values.items())


env_file("env-root", "/srv/infra/.env", f"DOMAIN={config.require('domain')}\n")

app_env = config.require_secret_object("env")
for app in APPS:
    env_file(f"env-{app}", f"/srv/infra/env/{app}.env", app_env.apply(lambda env, app=app: render(env[app])))

env_file(
    "env-litestream",
    "/srv/infra/env/litestream.env",
    pulumi.Output.all(
        config.require_secret("s3AccessKey"), config.require_secret("s3SecretKey")
    ).apply(
        lambda keys: render(
            {
                "LITESTREAM_BUCKET": config.require("bucket"),
                "LITESTREAM_ENDPOINT": endpoint,
                "LITESTREAM_REGION": location,
                "LITESTREAM_ACCESS_KEY_ID": keys[0],
                "LITESTREAM_SECRET_ACCESS_KEY": keys[1],
            }
        )
    ),
)

# Lets deploy.sh pull the private app images.
command.remote.Command(
    "ghcr-login",
    connection=connection,
    create=f"docker login ghcr.io -u {config.require('ghcrUser')} --password-stdin",
    stdin=config.require_secret("ghcrToken"),
    opts=pulumi.ResourceOptions(depends_on=[first_boot]),
)
