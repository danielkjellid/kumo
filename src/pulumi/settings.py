import pulumi

config = pulumi.Config()

# Helsinki. Closest Hetzner location to Norway.
location = config.get("location") or "hel1"
