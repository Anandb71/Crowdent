## Summary

-

## Safety

- [ ] No hardware actuation, cloud telemetry, or deployment-ready claims
- [ ] Countdown and advice remain forbidden unless readiness is `READY`
- [ ] Runtime code does not import `torch`
- [ ] Field profiles do not inherit demo network or docs settings

## Test plan

- [ ] `uv run ruff check src tests training`
- [ ] `uv run mypy src/crowdent`
- [ ] `uv run pytest`
- [ ] `npm run check` in `frontend/`
