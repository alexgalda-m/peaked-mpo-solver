from p9solver.pipeline import (
    adaptive_forced_drain_layer_budget,
    choose_hybrid_forced_drain_side,
)


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


def test_hybrid_frontier_balances_multiplicative_cost_and_distance() -> None:
    side, _ = choose_hybrid_forced_drain_side(3, 0, 50_000, 200_000)
    assert side == "left"
    side, _ = choose_hybrid_forced_drain_side(8, 0, 50_000, 200_000)
    assert side == "right"


def test_hybrid_frontier_commits_until_work_or_exhaustion() -> None:
    side, _ = choose_hybrid_forced_drain_side(
        4, 0, 400_000, 20_000, committed_side="left"
    )
    assert side == "left"
    side, _ = choose_hybrid_forced_drain_side(
        float("inf"), 2, 400_000, 20_000, committed_side="left"
    )
    assert side == "right"
