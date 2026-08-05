from p9solver.pipeline import adaptive_forced_drain_layer_budget


def test_budget_reaches_nearest_live_frontier() -> None:
    assert adaptive_forced_drain_layer_budget(1, 4, 7) == 5
    assert adaptive_forced_drain_layer_budget(8, 4, 7) == 8


def test_budget_ignores_exhausted_frontiers() -> None:
    assert adaptive_forced_drain_layer_budget(1, float("inf"), 10) == 11
    assert adaptive_forced_drain_layer_budget(8, float("inf"), float("inf")) == 8


def test_budget_extends_again_when_cost_choice_delays_nearest_side() -> None:
    # Apply the budget to the chosen side, not the nearer unchosen side.
    budget = adaptive_forced_drain_layer_budget(1, 3)
    assert budget == 4
    budget -= 1
    budget = adaptive_forced_drain_layer_budget(budget, 2)
    assert budget == 3
    budget -= 1
    assert adaptive_forced_drain_layer_budget(budget, 1) == 2
