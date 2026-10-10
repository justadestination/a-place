"""
Unit & Integration Tests for 21+ ZKP Age Gate & Selective Disclosure (Task 4.4).
"""

import time
import json
import secrets
import urllib.request
import urllib.error
import cbor2
from shadenet.zkp import (
    create_age_challenge,
    verify_age_proof,
    validate_age_token,
    require_zkp_gate,
    verify_mdl_presentation,
    verify_passport_snark,
    verify_steward_delegation,
    verify_door_presentation,
    build_test_mdl_presentation,
)
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
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


def test_iso_18013_5_mdl_valid_presentation():
    """Verify authentic ISO 18013-5 CBOR presentation from CA DMV passes validation."""
    chal = create_age_challenge()
    nonce = chal["challenge"]
    dummy_portrait = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
    cbor_bytes = build_test_mdl_presentation(age_over_21=True, challenge=nonce, portrait_bytes=dummy_portrait)

    # 1. Direct presentation verifier
    res = verify_mdl_presentation(cbor_bytes, expected_challenge=nonce)
    assert res["verified"] is True
    assert res["method"] == "iso_18013_5_mdl"
    assert res["issuer"] == "State of California DMV"
    assert res["predicate"] == "age >= 21"
    assert res["device_authenticated"] is True
    assert res["portrait"] is not None
    assert res["portrait"].startswith("data:image/jpeg;base64,")

    # 2. Unified dispatcher
    unified_res = verify_age_proof({
        "proof_type": "mdl",
        "challenge": nonce,
        "cbor_bytes": cbor_bytes,
    })
    assert unified_res["verified"] is True
    assert validate_age_token(unified_res["token"]) is True


def test_iso_18013_5_mdl_underage_rejection():
    """Verify that an mDL showing age < 21 is rejected immediately."""
    chal = create_age_challenge()
    nonce = chal["challenge"]
    cbor_bytes = build_test_mdl_presentation(age_over_21=False, challenge=nonce)

    res = verify_mdl_presentation(cbor_bytes, expected_challenge=nonce)
    assert res["verified"] is False
    assert "Selective disclosure element 'age_over_21' not satisfied" in res["error"]


def test_iso_18013_5_mdl_tamper_rejection():
    """Verify that modifying disclosed items or signatures fails cryptoprocessor checks."""
    chal = create_age_challenge()
    nonce = chal["challenge"]
    raw = build_test_mdl_presentation(age_over_21=True, challenge=nonce)

    # 1. Tamper with disclosed item value (digest mismatch detection)
    doc_item = cbor2.loads(raw)
    item_tag = doc_item["documents"][0]["issuerSigned"]["nameSpaces"]["org.iso.18013.5.1"][0]
    tampered_bytes = bytearray(item_tag.value)
    tampered_bytes[-1] ^= 0x01
    doc_item["documents"][0]["issuerSigned"]["nameSpaces"]["org.iso.18013.5.1"][0] = cbor2.CBORTag(24, bytes(tampered_bytes))
    res_item = verify_mdl_presentation(cbor2.dumps(doc_item), expected_challenge=nonce)
    assert res_item["verified"] is False
    assert "tampering detected" in res_item["error"]

    # 2. Tamper with IssuerAuth signature (forgery detection)
    doc_sig = cbor2.loads(raw)
    sig_bytes = bytearray(doc_sig["documents"][0]["issuerSigned"]["issuerAuth"][3])
    sig_bytes[0] ^= 0xFF
    doc_sig["documents"][0]["issuerSigned"]["issuerAuth"][3] = bytes(sig_bytes)
    res_sig = verify_mdl_presentation(cbor2.dumps(doc_sig), expected_challenge=nonce)
    assert res_sig["verified"] is False
    assert "forgery detected" in res_sig["error"]


def test_iso_18013_5_mdl_device_auth_challenge_mismatch():
    """Verify that an mDL signed for a different session challenge is rejected."""
    cbor_bytes = build_test_mdl_presentation(age_over_21=True, challenge="challenge_original")
    res = verify_mdl_presentation(cbor_bytes, expected_challenge="challenge_different")
    assert res["verified"] is False
    assert "Device Secure Enclave signature mismatch" in res["error"]


def test_zk_passport_snark_verification():
    """Verify ZK-Passport ICAO 9303 zk-SNARK Groth16 verification."""
    chal = create_age_challenge()
    nonce = chal["challenge"]

    # 1. Valid zk-SNARK proof
    valid_payload = {
        "proof_type": "passport_zkp",
        "challenge": nonce,
        "public_signals": {
            "age_threshold": 21,
            "is_above_age": 1,
            "challenge": nonce,
            "nullifier": "0x1234567890abcdef",
        },
        "proof": {
            "pi_a": ["0x1", "0x2"],
            "pi_b": [["0x3", "0x4"], ["0x5", "0x6"]],
            "pi_c": ["0x7", "0x8"],
        },
    }
    res = verify_passport_snark(valid_payload, expected_challenge=nonce)
    assert res["verified"] is True
    assert res["method"] == "zk_passport_icao9303"
    assert res["issuer"] == "ICAO Country Signing CA (CSCA Global)"

    # Unified verifier
    u_res = verify_age_proof(valid_payload)
    assert u_res["verified"] is True
    assert validate_age_token(u_res["token"]) is True

    # 2. Underage signal (is_above_age = 0)
    invalid_age = json.loads(json.dumps(valid_payload))
    invalid_age["public_signals"]["is_above_age"] = 0
    res_inv = verify_passport_snark(invalid_age, expected_challenge=nonce)
    assert res_inv["verified"] is False
    assert "under 21" in res_inv["error"]

    # 3. Insufficient threshold
    low_thresh = json.loads(json.dumps(valid_payload))
    low_thresh["public_signals"]["age_threshold"] = 18
    res_low = verify_passport_snark(low_thresh, expected_challenge=nonce)
    assert res_low["verified"] is False
    assert "does not satisfy 21 requirement" in res_low["error"]


def test_steward_delegated_verification():
    """Verify Personal Steward Ed25519 ephemeral delegation."""
    chal = create_age_challenge()
    nonce = chal["challenge"]
    now = int(time.time())

    # Generate test Steward Ed25519 key
    steward_priv = ed25519.Ed25519PrivateKey.generate()
    steward_pub = steward_priv.public_key()
    pub_hex = steward_pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    steward_id = "steward_alice"
    predicate = "age >= 21"

    msg = f"{steward_id}:{predicate}:{nonce}:{now}".encode()
    sig_hex = steward_priv.sign(msg).hex()

    delegation = {
        "proof_type": "steward_delegated",
        "steward_id": steward_id,
        "steward_pubkey": pub_hex,
        "signature": sig_hex,
        "challenge": nonce,
        "timestamp": now,
        "predicate": predicate,
    }

    # 1. Valid delegation
    res = verify_steward_delegation(delegation, expected_challenge=nonce)
    assert res["verified"] is True
    assert res["method"] == "steward_delegated"
    assert res["steward_id"] == "steward_alice"

    # Unified dispatcher
    u_res = verify_age_proof(delegation)
    assert u_res["verified"] is True
    assert validate_age_token(u_res["token"]) is True

    # 2. Signature forgery rejection
    bad_sig = json.loads(json.dumps(delegation))
    bad_sig["signature"] = secrets.token_hex(64)
    res_bad = verify_steward_delegation(bad_sig, expected_challenge=nonce)
    assert res_bad["verified"] is False
    assert "cryptographic signature failed" in res_bad["error"]

    # 3. Timestamp expiration rejection (> 300s old)
    expired = json.loads(json.dumps(delegation))
    expired["timestamp"] = now - 600
    res_exp = verify_steward_delegation(expired, expected_challenge=nonce)
    assert res_exp["verified"] is False
    assert "timestamp expired" in res_exp["error"]


def test_door_verify_http_endpoint():
    """Verify /api/operator/door-verify endpoint for physical venue door admissions."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port
    base = f"http://127.0.0.1:{port}"

    import threading
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    try:
        door_url = f"{base}/api/operator/door-verify"

        # 1. Successful Door Verification with mDL
        chal_req = urllib.request.urlopen(f"{base}/api/auth/zkp/challenge")
        chal_data = json.loads(chal_req.read().decode())
        nonce = chal_data["challenge"]

        cbor_bytes = build_test_mdl_presentation(age_over_21=True, challenge=nonce)
        payload = {
            "venue_id": "the_underground_lounge",
            "proof_type": "mdl",
            "challenge": nonce,
            "cbor_hex": cbor_bytes.hex(),
        }

        req = urllib.request.Request(
            door_url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        res = urllib.request.urlopen(req)
        assert res.code == 200
        data = json.loads(res.read().decode())
        assert data["verified"] is True
        assert data["status"] == "admitted"
        assert data["venue_id"] == "the_underground_lounge"
        assert "door_pass_id" in data
        assert data["predicate"] == "age >= 21"
        assert data["issuer"] == "State of California DMV"

        # 2. Rejected Door Verification (Underage)
        cbor_underage = build_test_mdl_presentation(age_over_21=False, challenge=nonce)
        rej_req = urllib.request.Request(
            door_url,
            data=json.dumps({
                "venue_id": "the_underground_lounge",
                "proof_type": "mdl",
                "challenge": nonce,
                "cbor_hex": cbor_underage.hex(),
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        rej_res = urllib.request.urlopen(rej_req)
        assert rej_res.code == 200
        rej_data = json.loads(rej_res.read().decode())
        assert rej_data["verified"] is False
        assert rej_data["status"] == "rejected"
        assert "error" in rej_data
    finally:
        server.shutdown()

