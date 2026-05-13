"""
Unit tests for the scoring function.

Scoring is the highest-leverage piece of code in the system. A regression here
silently routes the wrong accounts to the wrong AEs. Tests cover:

- Gate behavior (industry intersection + state footprint requirement)
- Adjacency scoring (insurance <-> financial_services <-> healthcare)
- Engagement weighting
- Urgency floor enforcement (via match_and_score, not score_pair)
- Edge cases: empty classification, unknown vertical, missing engagement
"""
import pytest

from run_pipeline import (
    ENGAGEMENT_SCORES,
    score_pair,
    match_and_score,
)


@pytest.fixture
def cfg():
    return {
        "verticals": {
            "insurance": {
                "weights": {
                    "industry_match": 0.40,
                    "urgency": 0.25,
                    "state_footprint_overlap": 0.20,
                    "engagement": 0.15,
                },
                "urgency_floor": 3,
            },
            "financial_services": {
                "weights": {
                    "industry_match": 0.35,
                    "urgency": 0.30,
                    "state_footprint_overlap": 0.20,
                    "engagement": 0.15,
                },
                "urgency_floor": 3,
            },
        }
    }


@pytest.fixture
def bill_insurance_ca_urgency4():
    return {
        "id": "ocd-bill/test-1",
        "state": "ca",
        "identifier": "AB 100",
        "title": "Insurance rate regulation",
        "latest_action": "Reported from committee",
        "latest_action_date": "2026-05-10",
        "subjects": [],
        "url": "https://example.com/ab100",
        "classification": {
            "industries": ["insurance"],
            "urgency": 4,
            "topic_summary": "Insurance rate regulation reform.",
            "affected_entities": ["P&C carriers"],
        },
    }


@pytest.fixture
def account_insurance_ca():
    return {
        "id": "acc_test_001",
        "name": "Test Insurance Co",
        "industry": "insurance",
        "state_footprint": ["ca", "tx"],
        "tier": 1,
        "engagement_status": "prospect-warm",
        "owner_ae": "ae_test",
        "vertical_config": "insurance",
    }


def test_direct_industry_match(cfg, bill_insurance_ca_urgency4, account_insurance_ca):
    """Direct industry match scores higher than adjacency."""
    m = score_pair(bill_insurance_ca_urgency4, account_insurance_ca, cfg)
    assert m is not None
    # industry_match weight is 0.40, full credit
    assert m.breakdown["industry_match"] == pytest.approx(0.40)


def test_adjacency_industry_match(cfg, bill_insurance_ca_urgency4):
    """A financial_services account scores partial credit on an insurance bill."""
    fs_account = {
        "id": "acc_test_fs",
        "name": "Test Bank",
        "industry": "financial_services",
        "state_footprint": ["ca"],
        "tier": 1,
        "engagement_status": "prospect-warm",
        "owner_ae": "ae_test",
        "vertical_config": "financial_services",
    }
    m = score_pair(bill_insurance_ca_urgency4, fs_account, cfg)
    assert m is not None
    # adjacency = 0.4 multiplier, weight 0.35 -> 0.14
    assert m.breakdown["industry_match"] == pytest.approx(0.4 * 0.35)


def test_state_gate_blocks_out_of_footprint(cfg, bill_insurance_ca_urgency4):
    """Account without bill's state in footprint is filtered out."""
    out_of_footprint = {
        "id": "acc_test_oof",
        "name": "Florida Only Co",
        "industry": "insurance",
        "state_footprint": ["fl"],
        "tier": 1,
        "engagement_status": "prospect-warm",
        "owner_ae": "ae_test",
        "vertical_config": "insurance",
    }
    assert score_pair(bill_insurance_ca_urgency4, out_of_footprint, cfg) is None


def test_industry_gate_blocks_unrelated(cfg, bill_insurance_ca_urgency4):
    """Retail account on an insurance bill is filtered out (no adjacency path)."""
    retail_account = {
        "id": "acc_test_retail",
        "name": "Test Retail",
        "industry": "retail",
        "state_footprint": ["ca"],
        "tier": 1,
        "engagement_status": "prospect-warm",
        "owner_ae": "ae_test",
        "vertical_config": "insurance",  # mismatched config but no industry overlap
    }
    assert score_pair(bill_insurance_ca_urgency4, retail_account, cfg) is None


def test_engagement_status_affects_score(cfg, bill_insurance_ca_urgency4, account_insurance_ca):
    """Engagement is a real factor: hot prospects score higher than cold."""
    m_warm = score_pair(bill_insurance_ca_urgency4, account_insurance_ca, cfg)

    cold = dict(account_insurance_ca, engagement_status="prospect-cold")
    m_cold = score_pair(bill_insurance_ca_urgency4, cold, cfg)

    assert m_warm.score > m_cold.score
    assert m_warm.breakdown["engagement"] == pytest.approx(ENGAGEMENT_SCORES["prospect-warm"] * 0.15)
    assert m_cold.breakdown["engagement"] == pytest.approx(ENGAGEMENT_SCORES["prospect-cold"] * 0.15)


def test_urgency_normalization(cfg, bill_insurance_ca_urgency4, account_insurance_ca):
    """Urgency 4 yields 4/5 of the urgency weight."""
    m = score_pair(bill_insurance_ca_urgency4, account_insurance_ca, cfg)
    assert m.breakdown["urgency"] == pytest.approx(4 / 5 * 0.25)


def test_no_classification_returns_none(cfg, account_insurance_ca):
    """A bill without classification cannot be scored."""
    bill = {"id": "x", "state": "ca", "identifier": "AB 1", "title": "", "classification": None}
    assert score_pair(bill, account_insurance_ca, cfg) is None


def test_unknown_vertical_returns_none(cfg, bill_insurance_ca_urgency4, account_insurance_ca):
    """Account pointing at a vertical not in config is dropped, not scored."""
    bad_acct = dict(account_insurance_ca, vertical_config="not_a_real_vertical")
    assert score_pair(bill_insurance_ca_urgency4, bad_acct, cfg) is None


def test_match_and_score_enforces_urgency_floor(cfg, account_insurance_ca):
    """A bill with urgency below the vertical's floor is filtered out at the match stage."""
    low_urgency_bill = {
        "id": "ocd-bill/low",
        "state": "ca",
        "identifier": "AB 999",
        "title": "Low urgency bill",
        "latest_action": "Referred to committee",
        "latest_action_date": "2026-01-01",
        "subjects": [],
        "url": "https://example.com",
        "classification": {
            "industries": ["insurance"],
            "urgency": 2,  # below insurance floor of 3
            "topic_summary": "Background administrative bill.",
            "affected_entities": [],
        },
    }
    matches = match_and_score([low_urgency_bill], [account_insurance_ca], cfg)
    assert matches == []


def test_match_and_score_filters_below_06(cfg, account_insurance_ca):
    """Even with urgency >= floor, a pair scoring < 0.6 is dropped."""
    low_score_bill = {
        "id": "ocd-bill/low2",
        "state": "ca",
        "identifier": "AB 998",
        "title": "Adjacent industry bill",
        "latest_action": "In committee",
        "latest_action_date": "2026-05-01",
        "subjects": [],
        "url": "https://example.com",
        "classification": {
            "industries": ["financial_services"],  # adjacent only
            "urgency": 3,
            "topic_summary": "Adjacent industry signal.",
            "affected_entities": [],
        },
    }
    cold = dict(account_insurance_ca, engagement_status="churned-recent")
    matches = match_and_score([low_score_bill], [cold], cfg)
    # adjacency 0.4 * 0.4 = 0.16, urgency 0.6 * 0.25 = 0.15, state 1.0 * 0.20 = 0.20, engagement 0.2 * 0.15 = 0.03
    # total = 0.54, below 0.6
    assert matches == []


def test_score_breakdown_sums_to_total(cfg, bill_insurance_ca_urgency4, account_insurance_ca):
    """Breakdown components must sum to the reported score (no hidden math)."""
    m = score_pair(bill_insurance_ca_urgency4, account_insurance_ca, cfg)
    assert sum(m.breakdown.values()) == pytest.approx(m.score)
