"""
Unit & Integration Tests for 21+ ZKP Age Gate & Selective Disclosure (Task 4.4).
"""

import time
import json
import urllib.request
import urllib.error
from shadenet.zkp import (
    create_age_challenge,
    verify_age_proof,
    validate_age_token,
    require_zkp_gate,
)
from shadenet.nightcal.server import Handler, ThreadingHTTPServer


def test_challenge_issuance():
    c = create_age_challenge()
    assert "challenge" in c
    assert len(c["challenge"]) == 32
    assert c["predicate"] == "age >= 21"
    assert c["expires_at"] > c["issued_at"]


def test_age_proof_verification_valid_and_token():
    challenge = create_age_challenge()
    proof_payload = {
        "challenge": challenge["challenge"],
        "claim": "age_over_21",
        "issuer": "state_dmv_california",
        "status": "valid",
    }
    result = verify_age_proof(proof_payload)
    assert result["verified"] is True
    assert "token" in result
    token = result["token"]

    # Validate token signature and unexpired state
    assert validate_age_token(token) is True


def test_age_proof_verification_invalid():
    challenge = create_age_challenge()
    
    # Underage or invalid proof status
    invalid_proof = {
        "challenge": challenge["challenge"],
        "claim": "age_over_21",
        "issuer": "state_dmv_california",
        "status": "invalid",
    }
    res_inv = verify_age_proof(invalid_proof)
    assert res_inv["verified"] is False
    assert "error" in res_inv

    # Wrong predicate claim
    wrong_claim = {
        "challenge": challenge["challenge"],
        "claim": "age_under_18",
        "status": "valid",
    }
    res_wrong = verify_age_proof(wrong_claim)
    assert res_wrong["verified"] is False


def test_token_tampering_and_forgery():
    challenge = create_age_challenge()
    valid_result = verify_age_proof({
        "challenge": challenge["challenge"],
        "claim": "age_over_21",
        "status": "valid",
    })
    token = valid_result["token"]
    
    # Tampered signature
    tampered_sig = token[:-4] + "ffff"
    assert validate_age_token(tampered_sig) is False

    # Corrupted payload
    assert validate_age_token("bad_payload.signature") is False
    assert validate_age_token("") is False


def test_http_write_gate_enforcement_and_abuse():
    """Verify that write operations without a 21+ ZKP token receive HTTP 403 Forbidden."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    base = f"http://127.0.0.1:{port}"
    
    import threading
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    try:
        # 1. Attempt mutating write action without token -> Must return HTTP 403
        write_url = f"{base}/api/action"
        req = urllib.request.Request(
            write_url,
            data=json.dumps({"name": "venue_edit", "context": {"venueId": "v1"}}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            assert False, "Write request without ZKP token should have failed with HTTP 403"
        except urllib.error.HTTPError as e:
            assert e.code == 403
            err_data = json.loads(e.read().decode())
            assert err_data.get("gate_required") is True
            assert "challenge" in err_data

        # 2. Complete verification via /api/auth/zkp/verify
        verify_url = f"{base}/api/auth/zkp/verify"
        challenge_req = urllib.request.urlopen(f"{base}/api/auth/zkp/challenge")
        chal_data = json.loads(challenge_req.read().decode())

        v_req = urllib.request.Request(
            verify_url,
            data=json.dumps({
                "challenge": chal_data["challenge"],
                "claim": "age_over_21",
                "status": "valid",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        v_res = urllib.request.urlopen(v_req)
        assert v_res.code == 200
        v_data = json.loads(v_res.read().decode())
        assert v_data.get("verified") is True
        token = v_data["token"]

        # 3. Repeat write action WITH valid ZKP token in X-ZKP-Token header
        req_allowed = urllib.request.Request(
            write_url,
            data=json.dumps({"name": "venue_edit", "context": {"venueId": "v1"}}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-ZKP-Token": token,
            },
            method="POST",
        )
        # Should not get 403! (either 200 or processed)
        res_allowed = urllib.request.urlopen(req_allowed)
        assert res_allowed.code == 200
    finally:
        server.shutdown()
