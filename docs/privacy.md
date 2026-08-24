# Privacy

Crowdent is designed for **existing venue sensors** and anonymous
aggregates. It is not a lawful-intercept or identity system.

## Allowed

- Zone-level anonymous counts with a time window
- Optical flow and density maps without person identity
- Schedules and turnstile-style counters without device IDs
- Local audit of human advisory decisions

## Forbidden in ingest

Passive aggregate payloads that contain any of these keys are rejected:

`device_id`, `raw_device_id`, `stable_id`, `mac`, `mac_address`, `imei`,
`imsi`, `advertising_id`, `bssid`

Do not reintroduce stable identifiers under another name.

## Video

Raw video retention is off by default. Enabling it requires
`raw_video_enabled: true` and an explicit retention window. Recorded files
must stay inside a configured directory. Do not commit videos to git.

## Credentials

RTSP URLs must not embed usernames or passwords. Supply secrets through a
local secret store or environment variables that never enter the repository.

## People data

Do not store student IDs, personal emails, or other identifiers from
competition submissions in this repository. The SIH idea PDF is not part of
the git tree for that reason.
