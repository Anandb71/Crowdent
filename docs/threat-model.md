# Threat model

Scope: a local research workstation or air-gapped venue laptop running
Crowdent. Attackers include a curious LAN user, a malicious recorded file,
and a compromised operator session.

## Assets

- Advisory forecasts that could be over-trusted
- Hash-chained audit history
- Local credentials, TOTP seeds, and JWT signing keys
- Recorded video and model weights
- Operator attention (false countdown, false advice)

## STRIDE summary

| Threat | Mitigation |
| --- | --- |
| Spoofed sensor or RTSP URL (SSRF) | Scheme allowlist, no embedded credentials, private/loopback hosts denied unless explicitly allowlisted, path character allowlist, recorded files confined to an allowed root |
| Tampered replay | SHA-256 bundle manifest, `research_only` required, hash-chained audit |
| Privilege escalation | Roles operator / supervisor / admin / auditor; field mode requires actor headers; auditors cannot mutate instructions |
| Information disclosure | Loopback default, field docs disabled, CSP and frame denial, no device identifiers in passive aggregates |
| Denial of service | Single-writer lock, CFL-limited numerics, fail-degraded on bad input rather than hanging on advice |
| Elevation via actuation | No actuation API exists; `ACTUATE` tokens are blocked |

## Explicit non-goals

Crowdent does not defend a multi-tenant SaaS, a public reverse proxy, or a
PLC network. If you place it behind one, you own that threat model.

## Residual risk

A local admin can always alter files on disk. The audit chain detects
in-database tampering of historical rows; it does not stop an operator from
confirming a physical action that never happened. Treat
`PHYSICAL ACTION CONFIRMED` as a human attestation, not ground truth.
