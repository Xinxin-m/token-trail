# Security and privacy

Token Trail is a single-user local application, not a network service. It binds to 127.0.0.1, validates Host, requires same-origin JSON for mutations, serves only bundled static assets, and sends no telemetry or provider API requests. Do not expose it to a LAN or public internet without a separate authenticated isolation layer.

The ledger omits raw message and tool-result bodies, but derived titles, file labels, IDs and hashes are still private. Database and configuration files are excluded from Git. The share export has a narrow allowlist. Never attach a real database or transcript to a public issue; reproduce adapter bugs with synthetic records.

The optional launcher executes a user-specified argument list without a shell or model override. Hooks record only session/parent IDs and timestamps. The installer preserves existing hooks and writes backups. It does not modify CLI credentials or read credential stores.

Report vulnerabilities privately to the repository maintainer once a public repository contact is established. This source preview has no public reporting inbox yet.
