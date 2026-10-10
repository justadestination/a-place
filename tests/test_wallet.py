"""
Unit and Integration Tests for Steward Agent Wallet & ZK ID Vault.
"""

import json
import secrets
from pathlib import Path

from shadenet.wallet import StewardWallet, MoneroSubaddress
from shadenet.steward.personal_agent import PersonalAgent
from shadenet.operator_steward import OperatorSteward
from shadenet.zkp import create_age_challenge, verify_age_proof, validate_age_token


def test_monero_subaddresses_and_payments(tmp_path):
    wallet = StewardWallet(wallet_id="test_agent_wallet_1", agent_id="agent_alice")

    # 1. Monero primary subaddress check
    assert wallet.primary_address.startswith("8")
    assert len(wallet.primary_address) >= 95
    assert len(wallet.subaddresses) == 1
    assert wallet.balance_xmr == 0.0

    # 2. Stealth subaddress generation
    sub2 = wallet.create_subaddress(label="Bar Tip / Entry")
    assert sub2.address.startswith("8")
    assert sub2.address != wallet.primary_address
    assert len(wallet.subaddresses) == 2

    # 3. Monero payment URI format
    uri = wallet.get_payment_uri(amount_xmr=0.05, label="Entry Admission")
    assert uri.startswith("monero:8")
    assert "tx_amount=0.050000" in uri
    assert "Entry Admission" in uri

    # 4. Receiving private settlement
    rcv = wallet.receive_payment_simulated(amount_xmr=1.25, note="Settlement payout")
    assert rcv["status"] == "confirmed"
    assert wallet.balance_xmr == 1.25
    assert wallet.unlocked_balance_xmr == 1.25


def test_zk_id_vault_verify_id_without_id():
    """Verify that an agent can prove age >= 21 to an entrance with ZERO PII disclosed."""
    wallet = StewardWallet(wallet_id="test_patron_wallet", agent_id="patron_bob")

    # Initially has Steward delegation by default
    assert wallet.has_age_credential() is False

    # Store California DMV mDL
    wallet.store_mdl_credential()
    assert wallet.has_age_credential() is True

    # Challenge received from venue door / service gate
    chal_info = create_age_challenge()
    challenge = chal_info["challenge"]

    # 1. Present age proof with mDL (Zero PII)
    proof_mdl = wallet.present_age_proof(challenge, preferred_method="mdl", venue_id="underground_bar")
    assert proof_mdl["proof_type"] == "mdl"
    assert proof_mdl["challenge"] == challenge
    assert proof_mdl["claim"] == "age_over_21"
    # Ensure no PII in payload
    assert "name" not in proof_mdl
    assert "address" not in proof_mdl
    assert "birthdate" not in proof_mdl

    # Verify through central zkp engine
    res_mdl = verify_age_proof(proof_mdl)
    assert res_mdl["verified"] is True
    assert validate_age_token(res_mdl["token"]) is True

    # 2. Present age proof with ZK-Passport
    wallet.store_passport_zkp(
        proof_signals={"age_threshold": 21, "is_above_age": 1},
        proof_points={"pi_a": ["0x1", "0x2"], "pi_b": [["0x3", "0x4"], ["0x5", "0x6"]], "pi_c": ["0x7", "0x8"]},
    )
    proof_pass = wallet.present_age_proof(challenge, preferred_method="passport")
    assert proof_pass["proof_type"] == "passport_zkp"
    res_pass = verify_age_proof(proof_pass)
    assert res_pass["verified"] is True

    # 3. Present age proof with Steward delegation
    proof_steward = wallet.present_age_proof(challenge, preferred_method="steward")
    assert proof_steward["proof_type"] == "steward_delegated"
    res_stew = verify_age_proof(proof_steward)
    assert res_stew["verified"] is True


def test_wallet_encrypted_persistence(tmp_path, monkeypatch):
    import shadenet.wallet as sw
    monkeypatch.setattr(sw, "WALLETS_DIR", tmp_path)

    seed = secrets.token_bytes(32)
    wallet = StewardWallet(wallet_id="persist_wallet_007", agent_id="agent_james", master_seed=seed)
    wallet.create_subaddress("Test Sub")
    wallet.receive_payment_simulated(2.5, note="Secret fund")
    wallet.store_mdl_credential()

    # Save encrypted
    saved_path = wallet.save()
    assert saved_path.exists()

    # Load from disk
    loaded = StewardWallet.load("persist_wallet_007", master_seed=seed)
    assert loaded.wallet_id == "persist_wallet_007"
    assert loaded.agent_id == "agent_james"
    assert loaded.balance_xmr == 2.5
    assert len(loaded.subaddresses) == 2
    assert "mdl" in loaded.credentials
    assert loaded.has_age_credential() is True


def test_agent_integration_with_standard_wallet():
    # 1. PersonalAgent comes standard with wallet
    agent = PersonalAgent(agent_id="patron_charlie")
    assert hasattr(agent, "wallet")
    assert agent.get_payment_address().startswith("8")
    pay_uri = agent.create_payment_request(0.1, "Drink Settlement")
    assert "tx_amount=0.100000" in pay_uri

    # Agent verifies ID without ID
    chal = create_age_challenge()["challenge"]
    proof = agent.present_age_proof(chal)
    res = verify_age_proof(proof)
    assert res["verified"] is True

    # 2. OperatorSteward !wallet command
    op_steward = OperatorSteward(steward_id="ops_guardian")
    res_cmd = op_steward.process_command("!wallet")
    assert res_cmd["status"] == "success"
    assert "Monero Stealth Address:" in res_cmd["message"]
    assert "ZK ID Vault:" in res_cmd["message"]
    assert "Privacy Guarantee:" in res_cmd["message"]
