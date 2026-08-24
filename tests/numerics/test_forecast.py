from __future__ import annotations

import numpy as np
import pytest

from crowdent.numerics import (
    DEFAULT_LEAD_TIMES_MIN,
    Intervention,
    branch_counterfactuals,
    no_assimilation_baseline,
    persistence_baseline,
    schedule_baseline,
    summarize_forecast,
)


def test_forecast_summary_has_requested_quantiles_and_exceedance_probabilities() -> None:
    samples = {
        5: np.array([[0.5, 1.0], [1.0, 2.0], [1.5, 3.0]]),
        10: np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]]),
    }

    summary = summarize_forecast(
        samples,
        quantiles=(0.1, 0.5, 0.9),
        thresholds={"site_specific_density": 1.25},
    )

    assert tuple(summary) == (5, 10)
    np.testing.assert_allclose(summary[5].quantiles[0.5], np.array([1.0, 2.0]))
    np.testing.assert_allclose(
        summary[5].threshold_exceedance["site_specific_density"],
        np.array([1 / 3, 2 / 3]),
    )


def test_standard_lead_times_and_baselines_are_explicit() -> None:
    assert DEFAULT_LEAD_TIMES_MIN == (5, 10, 15, 30, 45, 60)
    state = np.array([1.0, 2.0])

    persisted = persistence_baseline(state)
    no_assimilation = no_assimilation_baseline({5: state + 1.0})
    scheduled = schedule_baseline(
        state,
        {5: np.array([0.5, -0.5]), 10: np.array([1.0, -1.0])},
    )

    np.testing.assert_array_equal(persisted[60], state)
    np.testing.assert_array_equal(no_assimilation[5], state + 1.0)
    np.testing.assert_array_equal(scheduled[10], np.array([2.0, 1.0]))


def test_counterfactual_branches_share_identical_member_randomness() -> None:
    members = np.array([[1.0], [2.0], [3.0]])
    interventions = {
        "open": Intervention(name="open", gate_open_fraction={"north": 1.0}),
        "closed": Intervention(name="closed", gate_open_fraction={"north": 0.0}),
    }

    def simulator(
        member: np.ndarray,
        intervention: Intervention,
        rng: np.random.Generator,
        lead_times_min: tuple[int, ...],
    ) -> dict[int, np.ndarray]:
        shared_noise = rng.normal()
        effect = intervention.gate_open_fraction["north"]
        return {lead: member + shared_noise + effect for lead in lead_times_min}

    branches = branch_counterfactuals(
        members,
        interventions,
        simulator,
        seed=404,
        lead_times_min=(5, 10),
    )

    np.testing.assert_allclose(branches["open"][5] - branches["closed"][5], 1.0)
    np.testing.assert_allclose(branches["open"][10] - branches["closed"][10], 1.0)


def test_intervention_validates_gate_inflow_and_capacity_constraints() -> None:
    intervention = Intervention(
        name="metering",
        gate_open_fraction={"gate-a": 0.5},
        inflow_multiplier={"entry-a": 0.8},
        adjacent_zone_capacity_people={"zone-b": 200.0},
        projected_adjacent_zone_people={"zone-b": 180.0},
        egress_capacity_people_per_s={"gate-a": 2.0},
        requested_egress_people_per_s={"gate-a": 1.5},
    )
    intervention.validate_constraints()

    with pytest.raises(ValueError, match="adjacent-zone"):
        Intervention(
            name="unsafe-transfer",
            adjacent_zone_capacity_people={"zone-b": 100.0},
            projected_adjacent_zone_people={"zone-b": 120.0},
        ).validate_constraints()

    with pytest.raises(ValueError, match="egress"):
        Intervention(
            name="over-capacity",
            egress_capacity_people_per_s={"gate-a": 1.0},
            requested_egress_people_per_s={"gate-a": 2.0},
        ).validate_constraints()


def test_threshold_names_and_values_are_caller_supplied() -> None:
    with pytest.raises(ValueError):
        summarize_forecast(
            {5: np.ones((2, 1))},
            thresholds={"invalid": -1.0},
        )
