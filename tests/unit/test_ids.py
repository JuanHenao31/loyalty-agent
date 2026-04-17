"""Idempotency key derivation must be deterministic + sensitive to inputs."""

from app.shared.ids import derive_idempotency_key


def test_same_inputs_produce_same_key():
    a = derive_idempotency_key("add_points", "sess-1", "card-1", "5", "corte")
    b = derive_idempotency_key("add_points", "sess-1", "card-1", "5", "corte")
    assert a == b


def test_different_inputs_produce_different_keys():
    a = derive_idempotency_key("add_points", "sess-1", "card-1", "5", "corte")
    b = derive_idempotency_key("add_points", "sess-1", "card-1", "10", "corte")
    c = derive_idempotency_key("add_points", "sess-1", "card-2", "5", "corte")
    d = derive_idempotency_key("redeem_reward", "sess-1", "card-1", "5", "corte")
    assert len({a, b, c, d}) == 4


def test_namespace_prevents_cross_action_collisions():
    add = derive_idempotency_key("add_points", "same", "same")
    red = derive_idempotency_key("redeem_reward", "same", "same")
    assert add != red
