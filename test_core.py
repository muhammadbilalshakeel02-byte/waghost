import base64

from waghost import core


def test_b64_is_urlsafe_and_unpadded():
    out = core._b64(b"\xff\xfe\xfd")
    assert "=" not in out and "+" not in out and "/" not in out


def test_load_state_persists_identity(tmp_path):
    path = str(tmp_path / "s.json")
    first = core.load_state(path)
    second = core.load_state(path)
    assert first["id"] == second["id"]
    assert first["authkey"] == second["authkey"]
    assert len(first["id"]) == 16


def test_reset_state_changes_identity(tmp_path):
    path = str(tmp_path / "s.json")
    first = core.load_state(path)
    assert core.reset_state(path)["id"] != first["id"]


def test_base_fields_shape():
    state = core._new_state()
    fields = core.base_fields(state, "1", "5551234567")
    assert fields["cc"] == "1" and fields["in"] == "5551234567"
    assert fields["e_keytype"] == "BQ"
    assert len(base64.urlsafe_b64decode(fields["authkey"] + "=")) == 32


def test_raise_for_failure_maps_reasons():
    import pytest
    with pytest.raises(core.RateLimited) as exc:
        core._raise_for_failure({"status": "fail", "reason": "too_many",
                                 "retry_after": 42})
    assert exc.value.retry_after == 42

    with pytest.raises(core.BadToken):
        core._raise_for_failure({"status": "fail", "reason": "bad_token"})


def test_register_strips_code_separator(monkeypatch):
    captured = {}

    def fake_post(endpoint, payload, recaptcha=None, timeout=30):
        captured.update(payload)
        return {"status": "ok"}

    monkeypatch.setattr(core, "_post", fake_post)
    core.register("1", "5551234567", core._new_state(), "123-456")
    assert captured["code"] == "123456"