# The apps behind the sign-in, by their service name in compose.yml. Shared by
# the Pulumi program and the kumo CLI.
APPS = ["cadence"]  # gatekeeper is left out while it is WIP

# Paths that skip the sign-in, for callers that can't sign in, such as
# calendar feeds and links in emails. The app must check its own token there.
PUBLIC = {"gatekeeper": ["/external/*"]}
