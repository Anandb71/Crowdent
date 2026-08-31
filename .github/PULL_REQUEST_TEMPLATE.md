## Summary

-

## Safety

- [ ] No hardware actuation or deployment-ready claims
- [ ] Runtime code does not import `torch`
- [ ] Demo bind stays on loopback
- [ ] Drift numbers include distance, duration, and scenario

## Test plan

- [ ] `uv run ruff check src tests`
- [ ] `uv run mypy src/stilldot`
- [ ] `uv run pytest`
- [ ] `npm run check` in `frontend/`
