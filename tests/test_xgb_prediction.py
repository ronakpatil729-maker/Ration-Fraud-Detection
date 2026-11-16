# -*- coding: utf-8 -*-
"""Unit tests for XGBoost fraud model loading and prediction route."""

import pytest
from app.fraud.model_loader import load_xgb_model, get_feature_order
from app.fraud.xgb_predictor import predict_fraud


def test_xgb_model_loading_and_features():
    """Verify that XGBoost model loads properly and exposes expected features."""
    model = load_xgb_model()
    assert model is not None

    features = get_feature_order()
    assert len(features) == 9
    assert "Card_Type" in features
    assert "Family_Size" in features
    assert "Monthly_Income" in features
    assert "Allocated_Wheat_kg" in features
    assert "Availed_Wheat_kg" in features
    assert "Allocated_Rice_kg" in features
    assert "Availed_Rice_kg" in features
    assert "Biometric_Failures" in features
    assert "Monthly_Transactions" in features


def test_xgb_predict_fraud_normal():
    """Verify prediction for a typical legitimate ration beneficiary."""
    normal_payload = {
        "Card_Type": "BPL",
        "Family_Size": 4,
        "Monthly_Income": 6000,
        "Allocated_Wheat_kg": 15,
        "Availed_Wheat_kg": 15,
        "Allocated_Rice_kg": 20,
        "Availed_Rice_kg": 20,
        "Biometric_Failures": 0,
        "Monthly_Transactions": 1,
    }
    result = predict_fraud(normal_payload)
    assert "probability" in result
    assert "prediction" in result
    assert result["prediction"] == 0
    assert result["probability"] < 0.5


def test_xgb_predict_fraud_suspicious():
    """Verify prediction for a high-risk anomalous record."""
    fraud_payload = {
        "Card_Type": "BPL",
        "Family_Size": 1,
        "Monthly_Income": 95000,
        "Allocated_Wheat_kg": 5,
        "Availed_Wheat_kg": 50,
        "Allocated_Rice_kg": 5,
        "Availed_Rice_kg": 50,
        "Biometric_Failures": 15,
        "Monthly_Transactions": 25,
    }
    result = predict_fraud(fraud_payload)
    assert "probability" in result
    assert "prediction" in result
    assert result["prediction"] == 1
    assert result["probability"] >= 0.5


def test_xgb_card_type_encodings():
    """Verify string card types AAY, APL, BPL are correctly mapped."""
    for card_type in ["AAY", "APL", "BPL", "apl", "bpl", "aay"]:
        payload = {
            "Card_Type": card_type,
            "Family_Size": 3,
            "Monthly_Income": 5000,
            "Allocated_Wheat_kg": 10,
            "Availed_Wheat_kg": 10,
            "Allocated_Rice_kg": 15,
            "Availed_Rice_kg": 15,
            "Biometric_Failures": 0,
            "Monthly_Transactions": 1,
        }
        res = predict_fraud(payload)
        assert res["prediction"] in (0, 1)


def test_xgb_missing_feature_raises():
    """Verify that omitting a required feature raises a KeyError."""
    incomplete_payload = {
        "Card_Type": "BPL",
        "Family_Size": 4,
        # Monthly_Income omitted
        "Allocated_Wheat_kg": 15,
        "Availed_Wheat_kg": 15,
        "Allocated_Rice_kg": 20,
        "Availed_Rice_kg": 20,
        "Biometric_Failures": 0,
        "Monthly_Transactions": 1,
    }
    with pytest.raises(KeyError) as exc_info:
        predict_fraud(incomplete_payload)
    assert "Monthly_Income" in str(exc_info.value)


def test_admin_predict_endpoint_success(client, admin_user):
    """Verify /admin/predict route returns expected JSON for authenticated admin."""
    # Login as admin
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    payload = {
        "Card_Type": "BPL",
        "Family_Size": 4,
        "Monthly_Income": 7500,
        "Allocated_Wheat_kg": 15,
        "Availed_Wheat_kg": 15,
        "Allocated_Rice_kg": 20,
        "Availed_Rice_kg": 20,
        "Biometric_Failures": 0,
        "Monthly_Transactions": 1,
    }
    response = client.post('/admin/predict', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert "probability" in data
    assert "prediction" in data
    assert data["prediction"] == 0


def test_admin_predict_endpoint_validation_error(client, admin_user):
    """Verify /admin/predict route validates input properly."""
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    # Missing fields
    response = client.post('/admin/predict', json={"Card_Type": "BPL"})
    assert response.status_code == 400
    assert "error" in response.get_json()

    # Empty payload
    response = client.post('/admin/predict', json={})
    assert response.status_code == 400


def test_admin_predict_endpoint_unauthorized(client, dealer_user):
    """Verify non-admin users cannot access /admin/predict."""
    # Unauthenticated
    res = client.post('/admin/predict', json={})
    assert res.status_code in (302, 401, 403)

    # Dealer user
    client.post('/auth/login', data={
        'identifier': 'dealer_test',
        'password': 'DealerPass@123'
    })
    dealer_res = client.post('/admin/predict', json={})
    assert dealer_res.status_code in (302, 403)


def test_dataset_service_summary_and_samples():
    """Verify DatasetService properly reads the 20,000-record CSV."""
    from app.fraud.dataset_service import DatasetService

    summary = DatasetService.get_dataset_summary()
    assert summary["exists"] is True
    assert summary["total_records"] == 20000
    assert summary["fraud_count"] == 1400
    assert summary["legitimate_count"] == 18600
    assert summary["fraud_percentage"] == 7.0

    # Test sample lookup
    fraud_samples = DatasetService.get_sample_records(limit=2, is_fraud=1)
    assert len(fraud_samples) == 2
    assert fraud_samples[0]["Is_Fraud"] == "1"

    # Test find by card ID
    record = DatasetService.find_by_card_id("RC-100000")
    assert record is not None
    assert record["Card_ID"] == "RC-100000"
    assert record["Is_Fraud"] == "1"


def test_admin_predict_with_dataset_card_id(client, admin_user):
    """Verify /admin/predict route scores records looked up directly from dataset."""
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    # Test fraud record RC-100000
    res = client.post('/admin/predict', json={"card_id": "RC-100000"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "dataset"
    assert "probability" in data
    assert "prediction" in data

    # Test non-existent card ID
    res_404 = client.post('/admin/predict', json={"card_id": "RC-NONEXISTENT"})
    assert res_404.status_code == 404


def test_admin_predict_with_live_db_beneficiary(client, app, admin_user):
    """Verify /admin/predict route scores live database beneficiary."""
    from app.extensions import db
    from app.models.shop import RationShop
    from app.models.beneficiary import Beneficiary
    from app.models.transaction import DistributionTransaction

    ben_id = None
    with app.app_context():
        shop = RationShop(shop_no='FPS-XGB-01', name='Shop XGB', district='District', taluk='Taluk')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(
            ration_card_no='RC-LIVE-XGB-01',
            head_of_family='Live Test Ben',
            aadhaar_hash='hash_live_01',
            card_category='BPL',
            family_members_count=4,
            monthly_wheat_quota=15.0,
            monthly_rice_quota=20.0,
            assigned_shop_id=shop.id
        )
        db.session.add(ben)
        db.session.flush()
        ben_id = ben.id

        # Add normal transaction
        txn = DistributionTransaction(
            shop_id=shop.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=20.0,
            status='COMPLETED',
            biometric_match_score=0.95
        )
        db.session.add(txn)
        db.session.commit()

    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    res = client.post('/admin/predict', json={"beneficiary_id": ben_id})
    assert res.status_code == 200
    data = res.get_json()
    assert data["source"] == "database"
    assert data["beneficiary_id"] == ben_id
    assert "probability" in data
    assert "prediction" in data


def test_admin_dataset_endpoints(client, admin_user):
    """Verify /admin/dataset/summary and /admin/dataset/sample endpoints."""
    client.post('/auth/login', data={
        'identifier': 'admin_test',
        'password': 'AdminPass@123'
    })

    summary_res = client.get('/admin/dataset/summary')
    assert summary_res.status_code == 200
    summary_data = summary_res.get_json()
    assert summary_data["total_records"] == 20000

    sample_res = client.get('/admin/dataset/sample?limit=3')
    assert sample_res.status_code == 200
    sample_data = sample_res.get_json()
    assert len(sample_data) == 3


def test_fraud_audit_includes_xgb_alerts(app):
    """Verify that run_full_fraud_audit executes detect_xgb_fraud and persists alerts."""
    from app.extensions import db
    from app.models.shop import RationShop
    from app.models.beneficiary import Beneficiary
    from app.models.transaction import DistributionTransaction
    from app.fraud.detector import FraudDetectionService

    with app.app_context():
        shop = RationShop(shop_no='FPS-XGB-AUDIT', name='Shop Audit', district='District', taluk='Taluk')
        db.session.add(shop)
        db.session.flush()

        # Create beneficiary with extreme anomalous withdrawals & failures
        ben_fraud = Beneficiary(
            ration_card_no='RC-AUDIT-FRAUD-01',
            head_of_family='Audit Fraud Ben',
            aadhaar_hash='hash_audit_01',
            card_category='BPL',
            family_members_count=1,
            monthly_wheat_quota=5.0,
            monthly_rice_quota=5.0,
            assigned_shop_id=shop.id
        )
        db.session.add(ben_fraud)
        db.session.flush()

        for _ in range(12):
            txn = DistributionTransaction(
                shop_id=shop.id,
                beneficiary_id=ben_fraud.id,
                commodity='Rice',
                quantity=15.0,
                status='COMPLETED',
                biometric_match_score=0.10,
                auth_mode='MANUAL'
            )
            db.session.add(txn)
        db.session.commit()

        # Run full fraud audit
        result = FraudDetectionService.run_full_fraud_audit(commit=True)
        assert result['total_detected'] > 0
        assert result['newly_created'] > 0


