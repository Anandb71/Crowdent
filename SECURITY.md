# Security policy

Crowdent is an offline research tool. It is not deployment-certified.

## Supported versions

Only the `main` branch of this repository is eligible for security fixes
during 0.1.x.

## What to report

- Authentication or authorisation bypass in field mode
- SSRF or recorded-path confinement bypass
- Advice or countdown leaking when readiness is not `READY`
- Introduction of an actuation, PLC, or signage control path
- Secret exposure in git, logs, or replay bundles

## What not to report as a vulnerability

- Missing venue certification
- Inaccurate untrained density fixtures
- Demo actor headers in `DEMO_DETERMINISTIC` (intentional)

## How to report

Email the repository owner through GitHub's private vulnerability reporting
on https://github.com/Anandb71/Crowdent/security, or open a private advisory.
Do not attach real camera streams, credentials, or personal data.

We aim to acknowledge reports within 7 days.
