"""Tests for the bridge JSON protocol (encoding / decoding)."""
from __future__ import annotations

import json

from tests.conftest import make_bridge_response


class TestBridgeResponseProtocol:
    def test_success_response_structure(self):
        raw = make_bridge_response(ok=True, result={"foo": "bar"})
        assert raw.endswith("\n"), "Bridge messages must be newline-terminated"
        payload = json.loads(raw.strip())
        assert payload["ok"] is True
        assert payload["result"] == {"foo": "bar"}
        assert "id" in payload

    def test_error_response_structure(self):
        raw = make_bridge_response(ok=False, error="something went wrong")
        payload = json.loads(raw.strip())
        assert payload["ok"] is False
        assert payload["error"] == "something went wrong"
        assert "id" in payload

    def test_success_has_no_error_key(self):
        raw = make_bridge_response(ok=True)
        payload = json.loads(raw.strip())
        assert "error" not in payload

    def test_error_has_no_result_key(self):
        raw = make_bridge_response(ok=False, error="oops")
        payload = json.loads(raw.strip())
        assert "result" not in payload

    def test_is_valid_json(self):
        for ok in (True, False):
            raw = make_bridge_response(ok=ok, result={"x": 1}, error="err")
            # Should not raise
            json.loads(raw.strip())

    def test_unicode_roundtrip(self):
        payload_in = {"message": "こんにちは 🌏"}
        raw = make_bridge_response(ok=True, result=payload_in)
        payload_out = json.loads(raw.strip())
        assert payload_out["result"] == payload_in


class TestBridgeRequestProtocol:
    """Verify that the request shape the bridge client would send is correct."""

    def _make_request(self, op: str, params: dict) -> dict:
        import uuid
        return {"op": op, "params": params, "id": str(uuid.uuid4())}

    def test_request_has_required_keys(self):
        req = self._make_request("create_cube", {"size": 2.0})
        assert "op" in req
        assert "params" in req
        assert "id" in req

    def test_request_id_is_string(self):
        req = self._make_request("create_cube", {})
        assert isinstance(req["id"], str)

    def test_request_serialises_cleanly(self):
        req = self._make_request("build_interior", {"style": "modern_villa", "rooms": 3})
        encoded = json.dumps(req) + "\n"
        decoded = json.loads(encoded.strip())
        assert decoded["op"] == "build_interior"
        assert decoded["params"]["style"] == "modern_villa"
