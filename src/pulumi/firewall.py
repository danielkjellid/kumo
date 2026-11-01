import pulumi_hcloud as hcloud

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
