from datetime import datetime, timezone, timedelta
import pytest
from app.extensions import db
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary
from app.models.stock import StockMovement
from app.models.transaction import DistributionTransaction
from app.models.alert import FraudAlert
from app.fraud.detector import FraudDetectionService
from app.fraud.isolation_forest import PDSIsolationForest, get_isolation_forest_model


# --------------------------------------------------------------------------
# 1. STOCK RECONCILIATION & DISCREPANCY TESTS
# --------------------------------------------------------------------------
def test_stock_reconciliation_exact_formula(app):
    """
    Verify exact reconciliation formula:
    Opening Stock + Received Stock - Distributed Stock = Expected Closing Stock
    """
    with app.app_context():
        shop = RationShop(
            shop_no='FPS-RECON-01',
            name='Recon Depot',
            district='Mysuru',
            taluk='East'
        )
        db.session.add(shop)
        db.session.flush()

        # Received Stock: 1000 kg + 500 kg = 1500 kg
        m1 = StockMovement(shop_id=shop.id, commodity='Rice', movement_type='RECEIVED', quantity=1000.0)
        m2 = StockMovement(shop_id=shop.id, commodity='Rice', movement_type='ALLOCATION', quantity=500.0)

        # Beneficiary for transactions
        ben = Beneficiary(
            ration_card_no='RC-RECON-01',
            head_of_family='Test Family',
            aadhaar_hash='hash_recon_01',
            monthly_rice_quota=30.0
        )
        db.session.add_all([m1, m2, ben])
        db.session.flush()

        # Distributed Stock: 300 kg + 200 kg = 500 kg (completed) + 100 kg (rejected - should not count)
        t1 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Rice', quantity=300.0, status='COMPLETED')
        t2 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Rice', quantity=200.0, status='COMPLETED')
        t3 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Rice', quantity=100.0, status='REJECTED')
        db.session.add_all([t1, t2, t3])
        db.session.commit()

        # Opening = 200.0, Received = 1500.0, Distributed = 500.0
        # Expected Closing = 200.0 + 1500.0 - 500.0 = 1200.0 kg
        res = FraudDetectionService.reconcile_stock(
            shop_id=shop.id,
            commodity='Rice',
            opening_stock=200.0,
            reported_physical_stock=1200.0
        )

        assert res['opening_stock'] == 200.0
        assert res['received_stock'] == 1500.0
        assert res['distributed_stock'] == 500.0
        assert res['expected_closing_stock'] == 1200.0
        assert res['discrepancy'] == 0.0
        assert res['is_discrepancy'] is False
        assert res['discrepancy_type'] == 'BALANCED'


def test_stock_discrepancy_alert_on_shortage(app):
    """
    Verify discrepancy detection when reported physical stock is less than expected closing stock (shortage/diversion).
    """
    with app.app_context():
        shop = RationShop(shop_no='FPS-RECON-02', name='Deficit Depot', district='Mandya', taluk='Maddur')
        db.session.add(shop)
        db.session.flush()

        m1 = StockMovement(shop_id=shop.id, commodity='Wheat', movement_type='RECEIVED', quantity=1000.0)
        db.session.add(m1)
        db.session.commit()

        # Expected closing: 0 + 1000 - 0 = 1000.0 kg
        # Reported physical: 700.0 kg -> Shortage of 300.0 kg
        res = FraudDetectionService.reconcile_stock(
            shop_id=shop.id,
            commodity='Wheat',
            opening_stock=0.0,
            reported_physical_stock=700.0
        )

        assert res['expected_closing_stock'] == 1000.0
        assert res['discrepancy'] == -300.0
        assert res['is_discrepancy'] is True
        assert res['discrepancy_type'] == 'SHORTAGE'


def test_negative_stock_balance_triggers_critical_alert(app):
    """
    Verify that distributing more stock than received triggers a critical alert.
    """
    with app.app_context():
        shop = RationShop(shop_no='FPS-RECON-03', name='Ghost Depot', district='Hassan', taluk='Arsikere')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-GHOST-01', head_of_family='Ghost Recipient', aadhaar_hash='h_ghost')
        db.session.add(ben)
        db.session.flush()

        # Received: 100 kg, Distributed: 500 kg -> Deficit of -400 kg
        m1 = StockMovement(shop_id=shop.id, commodity='Sugar', movement_type='RECEIVED', quantity=100.0)
        t1 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Sugar', quantity=500.0, status='COMPLETED')
        db.session.add_all([m1, t1])
        db.session.commit()

        alerts = FraudDetectionService.check_stock_discrepancies()
        shop_alerts = [a for a in alerts if a['shop_id'] == shop.id and 'Sugar' in a['description']]

        assert len(shop_alerts) >= 1
        assert shop_alerts[0]['severity'] == FraudAlert.SEVERITY_CRITICAL
        assert "negative closing balance" in shop_alerts[0]['description']


# --------------------------------------------------------------------------
# 2. DUPLICATE RATION CARD DETECTION TESTS
# --------------------------------------------------------------------------
def test_normal_transactions_no_duplicate_alert(app):
    """
    Verify normal transactions at single shop spaced across days do NOT trigger duplicate alerts.
    """
    with app.app_context():
        shop = RationShop(shop_no='FPS-NORM-01', name='Normal Shop', district='Udupi', taluk='Karkala')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-NORM-01', head_of_family='Normal Head', aadhaar_hash='norm_hash_1', monthly_rice_quota=20.0)
        db.session.add(ben)
        db.session.flush()

        now = datetime.now(timezone.utc)
        t1 = DistributionTransaction(
            shop_id=shop.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=20.0,
            created_at=now - timedelta(days=35)
        )
        t2 = DistributionTransaction(
            shop_id=shop.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=20.0,
            created_at=now - timedelta(days=2)
        )
        db.session.add_all([t1, t2])
        db.session.commit()

        alerts = FraudDetectionService.detect_duplicate_ration_cards()
        assert len(alerts) == 0


def test_cross_shop_duplicate_card_detection(app):
    """
    Verify detection when the same ration card is used at different shops within 24 hours.
    """
    with app.app_context():
        shop1 = RationShop(shop_no='FPS-DUP-01', name='Shop North', district='Bengaluru', taluk='North')
        shop2 = RationShop(shop_no='FPS-DUP-02', name='Shop South', district='Bengaluru', taluk='South')
        db.session.add_all([shop1, shop2])
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-DUP-001', head_of_family='Suresh Patil', aadhaar_hash='dup_aadhaar_01')
        db.session.add(ben)
        db.session.flush()

        now = datetime.now(timezone.utc)
        # Transaction at Shop 1 at 10:00 AM
        t1 = DistributionTransaction(
            shop_id=shop1.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=20.0,
            created_at=now - timedelta(hours=3)
        )
        # Transaction at Shop 2 at 11:30 AM (1.5 hours later)
        t2 = DistributionTransaction(
            shop_id=shop2.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=20.0,
            created_at=now - timedelta(hours=1, minutes=30)
        )
        db.session.add_all([t1, t2])
        db.session.commit()

        alerts = FraudDetectionService.detect_duplicate_ration_cards()
        cross_shop_alerts = [a for a in alerts if 'Cross-Shop Duplicate Transaction' in a['description']]

        assert len(cross_shop_alerts) >= 1
        assert cross_shop_alerts[0]['severity'] in [FraudAlert.SEVERITY_HIGH, FraudAlert.SEVERITY_CRITICAL]
        assert 'RC-DUP-001' in cross_shop_alerts[0]['description']


def test_duplicate_synthetic_identity_hash(app):
    """
    Verify collision detection when multiple beneficiaries have identical synthetic identity hash.
    """
    with app.app_context():
        shared_hash = 'SYNTHETIC_COLLISION_HASH_7788'
        ben1 = Beneficiary(ration_card_no='RC-HASH-01', head_of_family='Member One', aadhaar_hash=shared_hash)
        ben2 = Beneficiary(ration_card_no='RC-HASH-02', head_of_family='Member Two', aadhaar_hash=shared_hash)
        db.session.add_all([ben1, ben2])
        db.session.commit()

        alerts = FraudDetectionService.detect_duplicate_ration_cards()
        identity_alerts = [a for a in alerts if 'Duplicate Identity Record' in a['description']]

        assert len(identity_alerts) >= 1
        assert identity_alerts[0]['severity'] == FraudAlert.SEVERITY_CRITICAL


# --------------------------------------------------------------------------
# 3. SUSPICIOUS QUANTITIES & REPEATED PATTERN TESTS
# --------------------------------------------------------------------------
def test_suspicious_quantity_detection(app):
    """
    Verify that transactions exceeding monthly quota trigger alerts with understandable explanations.
    """
    with app.app_context():
        shop = RationShop(shop_no='FPS-QTY-01', name='Quantity Test Shop', district='Tumakuru', taluk='Tiptur')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(
            ration_card_no='RC-QTY-01',
            head_of_family='Sunil Rao',
            aadhaar_hash='h_qty_01',
            monthly_rice_quota=20.0
        )
        db.session.add(ben)
        db.session.flush()

        # Issuing 100 kg when quota is 20 kg (5x quota!)
        txn = DistributionTransaction(
            shop_id=shop.id,
            beneficiary_id=ben.id,
            commodity='Rice',
            quantity=100.0,
            status='COMPLETED'
        )
        db.session.add(txn)
        db.session.commit()

        alerts = FraudDetectionService.detect_suspicious_quantities()
        qty_alerts = [a for a in alerts if a['transaction_id'] == txn.id]

        assert len(qty_alerts) >= 1
        assert qty_alerts[0]['severity'] == FraudAlert.SEVERITY_CRITICAL
        assert "exceeding authorized monthly quota (20.0kg) by 400%" in qty_alerts[0]['description']


def test_rapid_burst_transaction_pattern(app):
    """
    Verify that multiple transactions for the same card within minutes trigger burst pattern alerts.
    """
    with app.app_context():
        shop = RationShop(shop_no='FPS-BURST-01', name='Burst Shop', district='Kolar', taluk='Bangarapet')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-BURST-01', head_of_family='Fast Swiper', aadhaar_hash='h_burst')
        db.session.add(ben)
        db.session.flush()

        now = datetime.now(timezone.utc)
        t1 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Rice', quantity=15.0, created_at=now - timedelta(minutes=10))
        t2 = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Wheat', quantity=10.0, created_at=now - timedelta(minutes=2))
        db.session.add_all([t1, t2])
        db.session.commit()

        alerts = FraudDetectionService.detect_repeated_patterns()
        burst_alerts = [a for a in alerts if 'Rapid Transaction Burst' in a['description']]

        assert len(burst_alerts) >= 1
        assert burst_alerts[0]['severity'] == FraudAlert.SEVERITY_HIGH


# --------------------------------------------------------------------------
# 4. ISOLATION FOREST ML ANOMALY MODEL TESTS
# --------------------------------------------------------------------------
def test_isolation_forest_normal_and_anomalous_samples():
    """
    Verify Isolation Forest prediction, anomaly score, understandable reasons,
    and non-proof-of-fraud disclaimer.
    """
    model = PDSIsolationForest(n_estimators=50, random_state=42)
    # Fit with baseline synthetic data
    model.fit([])

    # 1. Normal daytime transaction
    # Features: [quantity=15.0, quota_ratio=0.75, hour=11.0, bio_score=0.95, is_manual=0.0]
    normal_vector = [15.0, 0.75, 11.0, 0.95, 0.0]
    pred_norm, score_norm, exp_norm = model.predict(normal_vector)

    assert pred_norm == 1
    assert exp_norm['is_anomaly'] is False
    assert score_norm < 0.60
    assert "within expected distribution" in exp_norm['reason']

    # 2. Extreme anomalous transaction
    # Features: [quantity=280.0, quota_ratio=8.0, hour=2.0 (night), bio_score=0.15, is_manual=1.0]
    anomaly_vector = [280.0, 8.0, 2.0, 0.15, 1.0]
    pred_anom, score_anom, exp_anom = model.predict(anomaly_vector)

    assert pred_anom == -1
    assert exp_anom['is_anomaly'] is True
    assert score_anom >= 0.60
    assert "Statistical Anomaly" in exp_anom['reason']
    # Must contain the disclaimer explaining it's not proof of fraud
    assert "do not constitute conclusive proof of fraud" in exp_anom['disclaimer']


def test_isolation_forest_missing_values_and_insufficient_data():
    """
    Verify that Isolation Forest handles missing values (None / NaN)
    and insufficient training data gracefully without throwing exceptions.
    """
    # Test insufficient training data handling (e.g. 3 samples < 15 minimum)
    tiny_dataset = [
        [20.0, 1.0, 10.0, 0.9, 0.0],
        [15.0, 0.75, 12.0, 0.88, 0.0],
        [25.0, 1.25, 14.0, 0.92, 0.0]
    ]
    model = PDSIsolationForest(n_estimators=30, random_state=42)
    # Fitting should NOT crash; uses synthetic baseline safeguard
    model.fit(tiny_dataset)
    assert model.is_fitted is True

    # Test missing values imputation (None inputs)
    vector_with_nones = [None, None, 14.0, None, None]
    pred, score, exp = model.predict(vector_with_nones)

    assert pred in [-1, 1]
    assert 0.0 <= score <= 1.0
    assert isinstance(exp['reason'], str)


def test_isolation_forest_model_persistence(tmp_path):
    """
    Verify model saving to and loading from disk.
    """
    filepath = str(tmp_path / 'test_model.pkl')
    model = PDSIsolationForest(n_estimators=20, random_state=42)
    model.fit([])
    model.save(filepath)

    loaded = PDSIsolationForest.load(filepath)
    sample = [20.0, 1.0, 10.0, 0.90, 0.0]

    score_orig = model.score_sample(sample)
    score_loaded = loaded.score_sample(sample)
    assert round(score_orig, 4) == round(score_loaded, 4)


# --------------------------------------------------------------------------
# 5. FULL AUDIT INTEGRATION & ALERT TABLE TESTS
# --------------------------------------------------------------------------
def test_full_fraud_audit_execution_and_table_routes(client, admin_user, app):
    """
    Test end-to-end execution of full audit and alert table rendering.
    """
    # 1. Login as admin
    client.post('/auth/login', data={'identifier': 'admin_test', 'password': 'AdminPass@123'})

    # 2. Trigger automated audit via POST /admin/run-audit
    post_res = client.post('/admin/run-audit', follow_redirects=True)
    assert post_res.status_code == 200
    assert b"Automated Vigilance Audit completed" in post_res.data

    # 3. Verify /admin/alerts renders table columns:
    # Shop, Transaction, Alert Reason, Risk Level, Investigation Status, Timestamp
    res = client.get('/admin/alerts')
    assert res.status_code == 200
    assert b"Shop" in res.data
    assert b"Transaction" in res.data
    assert b"Alert Reason" in res.data
    assert b"Risk Level" in res.data
    assert b"Investigation Status" in res.data
    assert b"Timestamp" in res.data

    # 4. Verify /admin/reconciliation renders
    recon_res = client.get('/admin/reconciliation')
    assert recon_res.status_code == 200
    assert b"Stock Reconciliation" in recon_res.data
    assert b"Expected Closing Stock = Opening Stock + Received Stock - Distributed Stock" in recon_res.data

    # 5. Test updating alert status
    with app.app_context():
        alert = FraudAlert(
            alert_type='TEST_ALERT',
            severity=FraudAlert.SEVERITY_HIGH,
            description='Test alert for status workflow',
            status=FraudAlert.STATUS_DETECTED
        )
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id

    status_update_res = client.post(
        f'/admin/alerts/{alert_id}/status',
        data={'status': 'INVESTIGATING', 'resolution_notes': 'Case opened by inspector.'},
        follow_redirects=True
    )
    assert status_update_res.status_code == 200

    with app.app_context():
        updated_alert = db.session.get(FraudAlert, alert_id)
        assert updated_alert.status == 'INVESTIGATING'
        assert 'Case opened by inspector.' in updated_alert.resolution_notes


def test_admin_dashboard_summary_cards_and_charts(client, admin_user, app):
    """
    Verify summary cards (shops, beneficiaries, transactions, pending alerts),
    charts (monthly distribution, stock discrepancy), and shop-wise risk summaries on dashboard.
    """
    # 1. Login
    client.post('/auth/login', data={'identifier': 'admin_test', 'password': 'AdminPass@123'})

    # 2. Add realistic shop and transactions in DB
    with app.app_context():
        shop = RationShop(shop_no='FPS-DASH-01', name='Dash Shop', district='Bengaluru', taluk='North')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-DASH-01', head_of_family='Dash Family', aadhaar_hash='dash_h_01')
        db.session.add(ben)
        db.session.flush()

        txn = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Rice', quantity=35.0)
        stock = StockMovement(shop_id=shop.id, commodity='Rice', movement_type='RECEIVED', quantity=1000.0)
        alert = FraudAlert(shop_id=shop.id, transaction_id=txn.id, alert_type='BULK_DISPATCH_ANOMALY', severity='HIGH', description='Excessive dispatch')
        db.session.add_all([txn, stock, alert])
        db.session.commit()

    # 3. GET /admin/dashboard
    res = client.get('/admin/dashboard')
    assert res.status_code == 200

    # Summary cards verification
    assert b"Fair Price Shops" in res.data
    assert b"Beneficiaries" in res.data
    assert b"Transactions" in res.data
    assert b"Pending Alerts" in res.data

    # Charts canvas verification
    assert b"monthlyDistributionChart" in res.data
    assert b"stockDiscrepancyChart" in res.data

    # Shop-wise risk summary verification
    assert b"Fair Price Shop Risk Summaries" in res.data
    assert b"FPS-DASH-01" in res.data

    # Search filter testing
    search_res = client.get('/admin/dashboard?q=FPS-DASH-01')
    assert search_res.status_code == 200
    assert b"FPS-DASH-01" in search_res.data


def test_alert_details_page_and_status_buttons(client, admin_user, app):
    """
    Verify alert details page displays deep-dive evidence, shop/transaction context,
    and buttons to mark alert as under review, resolved, or dismissed.
    """
    # 1. Login
    client.post('/auth/login', data={'identifier': 'admin_test', 'password': 'AdminPass@123'})

    with app.app_context():
        shop = RationShop(shop_no='FPS-DET-99', name='Detail Test Shop', district='Bidar', taluk='Aurad')
        db.session.add(shop)
        db.session.flush()

        ben = Beneficiary(ration_card_no='RC-DET-99', head_of_family='Detail Head', aadhaar_hash='h_det_99')
        db.session.add(ben)
        db.session.flush()

        txn = DistributionTransaction(shop_id=shop.id, beneficiary_id=ben.id, commodity='Wheat', quantity=80.0)
        db.session.add(txn)
        db.session.flush()

        alert = FraudAlert(
            shop_id=shop.id,
            transaction_id=txn.id,
            alert_type='EXCESSIVE_QUANTITY',
            severity='CRITICAL',
            description='Quantity 80kg exceeds quota by 300%.',
            status='DETECTED'
        )
        db.session.add(alert)
        db.session.commit()
        alert_id = alert.id

    # 2. View Alert Details Page
    res = client.get(f'/admin/alerts/{alert_id}')
    assert res.status_code == 200
    assert b"Reason for Detection" in res.data
    assert b"Quantity 80kg exceeds quota by 300%." in res.data
    assert b"FPS-DET-99" in res.data
    assert b"RC-DET-99" in res.data
    assert b"Mark as Under Review" in res.data
    assert b"Mark as Resolved" in res.data

    # 3. Test "Mark as Under Review" action
    review_res = client.post(
        f'/admin/alerts/{alert_id}/status',
        data={'status': 'INVESTIGATING', 'resolution_notes': 'Case marked under active review.'},
        follow_redirects=True
    )
    assert review_res.status_code == 200
    assert b"marked as &#39;Under Review&#39;" in review_res.data or b"marked as 'Under Review'" in review_res.data

    with app.app_context():
        a_rev = db.session.get(FraudAlert, alert_id)
        assert a_rev.status == 'INVESTIGATING'

    # 4. Test "Mark as Resolved" action
    resolve_res = client.post(
        f'/admin/alerts/{alert_id}/status',
        data={'status': 'RESOLVED', 'resolution_notes': 'Physical verification cleared by officer.'},
        follow_redirects=True
    )
    assert resolve_res.status_code == 200

    with app.app_context():
        a_res = db.session.get(FraudAlert, alert_id)
        assert a_res.status == 'RESOLVED'
        assert a_res.resolved_at is not None

    # 5. Test 404 for non-existent alert
    not_found_res = client.get('/admin/alerts/999999')
    assert not_found_res.status_code == 404
