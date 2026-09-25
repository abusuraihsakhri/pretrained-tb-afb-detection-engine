# Security Policy

## Supported versions

Security fixes are applied to the current `main` branch. The historical v1.0.0
checkpoint is on scientific validation hold and should be used only for local,
non-clinical research reproduction.

## Reporting a vulnerability

Please use GitHub’s private vulnerability-reporting interface for this
repository. Do not include patient information, credentials, private slide
identifiers, or exploitable details in a public issue.

Include:

- Affected commit or release
- Reproduction steps using synthetic or de-identified data
- Expected impact and affected deployment mode
- Suggested mitigation, if known

No response-time or remediation-time guarantee is currently offered.

## Deployment boundary

The application is designed for trusted, local research environments. It is not
a hardened medical device or a public multitenant service.

- Docker Compose binds the API to `127.0.0.1` by default.
- Data-changing endpoints remain disabled until `TB_AFB_API_TOKEN` is set.
- Remote training additionally requires `TB_AFB_ALLOW_REMOTE_TRAINING=1`.
- Only the pinned checkpoint under `03_MODELS/` is loaded, with SHA-256
  verification when a checksum is supplied.
- Raw clinical data, review queues, logs, and environment files are ignored by Git.

Deployments exposed beyond localhost require an authenticated reverse proxy,
TLS, network access control, monitoring, backups, data-retention policy, and an
independent security review.

## Sensitive data

Do not upload identifiable clinical material to a third-party service or commit
it to this repository. Use de-identified research identifiers and keep the
mapping key in a separately controlled system.

## Third-party dependencies

Dependency vulnerabilities are in scope when they affect this project’s use of
the dependency. Reports may be redirected upstream, but the project must still
assess exposure, mitigations, and upgrade compatibility.

## Model files

PyTorch checkpoint formats may execute deserialization logic. Load only trusted,
locally controlled checkpoints whose SHA-256 value has been verified. Do not
offer arbitrary checkpoint upload or loading through the API.

## Compliance statement

The local research log is not a 21 CFR Part 11 audit trail. The repository does
not claim FDA, CE-IVD, HIPAA, GDPR, ISO 13485, IEC 62304, or other regulatory
compliance.
