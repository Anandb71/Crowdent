# Governance

Crowdent 0.1.x is maintained by the repository owner and invited
collaborators.

## Decision making

- Safety invariants (no actuation, fail-degraded advice, loopback default,
  no device identifiers) are not majority-vote items. Changing them requires
  an explicit, documented justification in the pull request.
- Feature work proceeds by pull request against `main`.
- Releases are git tags. No release may be labelled deployment-ready.

## Roles

- **Maintainer**: merge rights, security intake, GitHub settings.
- **Contributor**: patches via pull request.
- **Operator** (runtime): a local user of a research profile, not a project
  governance role.

## Research-gated claims

Documentation and UI copy must keep `RESEARCH ONLY — NOT DEPLOYMENT
CERTIFIED` visible. Removing that banner is a governance violation, not a
style tweak.
