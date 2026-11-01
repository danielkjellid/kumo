import json
from pathlib import Path

import pulumi_hcloud as hcloud

from firewall import firewall
from settings import config, location

# Every key that may log in as deploy: your laptop and the CI deploy key.
authorized_keys: list[str] = config.require_object("authorizedKeys")

keys = [
    hcloud.SshKey(f"kumo-{i}", name=f"kumo-{i}", public_key=key)
    for i, key in enumerate(authorized_keys)
]

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
    server_type=config.get("serverType") or "cpx12",
    location=location,
    ssh_keys=[key.id for key in keys],
    firewall_ids=[firewall.id.apply(int)],
    user_data=user_data,
    # Data lives on this disk. Litestream can rebuild it, but not by accident.
    delete_protection=True,
    rebuild_protection=True,
)
