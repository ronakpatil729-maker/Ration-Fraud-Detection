"""
Synthetic Demonstration Data Seeder for Ration Fraud Detection System.
Generates realistic, completely synthetic data for academic and evaluation purposes.
"""
from datetime import datetime, timezone, timedelta
import hashlib
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary
from app.models.stock import StockMovement
from app.models.transaction import DistributionTransaction
from app.models.alert import FraudAlert


def generate_synthetic_aadhaar_hash(raw_num: str) -> str:
    """Generate pseudonymized synthetic Aadhaar hash."""
    return hashlib.sha256(f"SYNTHETIC_UID_{raw_num}".encode()).hexdigest()[:24]


def seed_database():
    app = create_app('development')
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        # Check if users already seeded
        if User.query.filter_by(username='admin').first():
            print("Database already contains seed data. Skipping seeding.")
            return

        print("Seeding synthetic users (Admin and Dealers)...")
        # 1. Users
        admin = User(
            username='admin',
            email='admin@pds-vigilance.gov.in',
            full_name='Dr. Rajesh Verma (Vigilance Director)',
            phone='+91 98765 43210',
            role=User.ROLE_ADMIN,
            is_active=True
        )
        admin.set_password('Admin@123')

        dealer1 = User(
            username='dealer_fps101',
            email='dealer101@fps-network.gov.in',
            full_name='Suresh Kumar (FPS Owner)',
            phone='+91 98450 11223',
            role=User.ROLE_DEALER,
            is_active=True
        )
        dealer1.set_password('Dealer@123')

        dealer2 = User(
            username='dealer_fps102',
            email='dealer102@fps-network.gov.in',
            full_name='Anand Patil (FPS Owner)',
            phone='+91 94480 33445',
            role=User.ROLE_DEALER,
            is_active=True
        )
        dealer2.set_password('Dealer@123')

        db.session.add_all([admin, dealer1, dealer2])
        db.session.flush()

        print("Seeding synthetic Ration Shops (FPS)...")
        # 2. Fair Price Shops
        shop1 = RationShop(
            shop_no='FPS-KA-101',
            name='Sri Venkateshwara Fair Price Depot',
            district='Bengaluru Urban',
            taluk='Bengaluru North',
            pincode='560003',
            address='No. 42, 8th Main, Malleshwaram',
            dealer_id=dealer1.id,
            is_active=True
        )

        shop2 = RationShop(
            shop_no='FPS-KA-102',
            name='Gramin Seva Samiti Distribution Center',
            district='Mandya',
            taluk='Maddur',
            pincode='571428',
            address='Station Road, Maddur Rural Circle',
            dealer_id=dealer2.id,
            is_active=True
        )

        shop3 = RationShop(
            shop_no='FPS-KA-103',
            name='Coastal PDS Kendra',
            district='Dakshina Kannada',
            taluk='Mangaluru',
            pincode='575001',
            address='Bunder Port Road, Mangaluru',
            dealer_id=None,
            is_active=True
        )

        db.session.add_all([shop1, shop2, shop3])
        db.session.flush()

        print("Seeding synthetic beneficiaries...")
        # 3. Beneficiaries
        beneficiaries = [
            Beneficiary(
                ration_card_no='RC-KA-00101',
                head_of_family='Ramesh Nayak',
                aadhaar_hash=generate_synthetic_aadhaar_hash('9001'),
                card_category=Beneficiary.CATEGORY_AAY,
                family_members_count=5,
                monthly_rice_quota=35.0,
                monthly_wheat_quota=10.0,
                monthly_sugar_quota=3.0,
                assigned_shop_id=shop1.id,
                phone='+91 97410 00101'
            ),
            Beneficiary(
                ration_card_no='RC-KA-00102',
                head_of_family='Fatima Begum',
                aadhaar_hash=generate_synthetic_aadhaar_hash('9002'),
                card_category=Beneficiary.CATEGORY_BPL,
                family_members_count=4,
                monthly_rice_quota=20.0,
                monthly_wheat_quota=10.0,
                monthly_sugar_quota=2.0,
                assigned_shop_id=shop1.id,
                phone='+91 97410 00102'
            ),
            Beneficiary(
                ration_card_no='RC-KA-00103',
                head_of_family='Kavitha Gowda',
                aadhaar_hash=generate_synthetic_aadhaar_hash('9003'),
                card_category=Beneficiary.CATEGORY_BPL,
                family_members_count=3,
                monthly_rice_quota=15.0,
                monthly_wheat_quota=8.0,
                monthly_sugar_quota=1.5,
                assigned_shop_id=shop1.id,
                phone='+91 97410 00103'
            ),
            Beneficiary(
                ration_card_no='RC-KA-00104',
                head_of_family='Manjunath Hegde',
                aadhaar_hash=generate_synthetic_aadhaar_hash('9004'),
                card_category=Beneficiary.CATEGORY_APL,
                family_members_count=4,
                monthly_rice_quota=10.0,
                monthly_wheat_quota=5.0,
                monthly_sugar_quota=1.0,
                assigned_shop_id=shop2.id,
                phone='+91 97410 00104'
            ),
            Beneficiary(
                ration_card_no='RC-KA-00105',
                head_of_family='Devi Prasad',
                aadhaar_hash=generate_synthetic_aadhaar_hash('9005'),
                card_category=Beneficiary.CATEGORY_AAY,
                family_members_count=6,
                monthly_rice_quota=35.0,
                monthly_wheat_quota=10.0,
                monthly_sugar_quota=3.0,
                assigned_shop_id=shop2.id,
                phone='+91 97410 00105'
            )
        ]
        db.session.add_all(beneficiaries)
        db.session.flush()

        print("Seeding stock movements...")
        # 4. Stock Movements
        now = datetime.now(timezone.utc)
        stocks = [
            StockMovement(
                shop_id=shop1.id,
                commodity=StockMovement.COMMODITY_RICE,
                movement_type=StockMovement.TYPE_RECEIVED,
                quantity=4500.0,
                batch_no='BATCH-2026-R1',
                reference_doc='WH-DISPATCH-9812',
                created_at=now - timedelta(days=20)
            ),
            StockMovement(
                shop_id=shop1.id,
                commodity=StockMovement.COMMODITY_WHEAT,
                movement_type=StockMovement.TYPE_RECEIVED,
                quantity=2500.0,
                batch_no='BATCH-2026-W1',
                reference_doc='WH-DISPATCH-9813',
                created_at=now - timedelta(days=20)
            ),
            StockMovement(
                shop_id=shop1.id,
                commodity=StockMovement.COMMODITY_SUGAR,
                movement_type=StockMovement.TYPE_RECEIVED,
                quantity=600.0,
                batch_no='BATCH-2026-S1',
                reference_doc='WH-DISPATCH-9814',
                created_at=now - timedelta(days=20)
            ),
            StockMovement(
                shop_id=shop2.id,
                commodity=StockMovement.COMMODITY_RICE,
                movement_type=StockMovement.TYPE_RECEIVED,
                quantity=3800.0,
                batch_no='BATCH-2026-R2',
                reference_doc='WH-DISPATCH-9820',
                created_at=now - timedelta(days=18)
            )
        ]
        db.session.add_all(stocks)
        db.session.flush()

        print("Seeding distribution transactions...")
        # 5. Transactions
        txn1 = DistributionTransaction(
            transaction_code='TXN-KA-800101',
            shop_id=shop1.id,
            beneficiary_id=beneficiaries[0].id,
            commodity='Rice',
            quantity=35.0,
            auth_mode=DistributionTransaction.AUTH_BIOMETRIC,
            status=DistributionTransaction.STATUS_COMPLETED,
            biometric_match_score=0.96,
            pos_device_id='POS-DEV-101A',
            created_at=now - timedelta(days=12, hours=3)
        )

        txn2 = DistributionTransaction(
            transaction_code='TXN-KA-800102',
            shop_id=shop1.id,
            beneficiary_id=beneficiaries[1].id,
            commodity='Rice',
            quantity=20.0,
            auth_mode=DistributionTransaction.AUTH_BIOMETRIC,
            status=DistributionTransaction.STATUS_COMPLETED,
            biometric_match_score=0.94,
            pos_device_id='POS-DEV-101A',
            created_at=now - timedelta(days=10, hours=2)
        )

        txn3 = DistributionTransaction(
            transaction_code='TXN-KA-800103',
            shop_id=shop1.id,
            beneficiary_id=beneficiaries[2].id,
            commodity='Wheat',
            quantity=8.0,
            auth_mode=DistributionTransaction.AUTH_OTP,
            status=DistributionTransaction.STATUS_COMPLETED,
            biometric_match_score=None,
            pos_device_id='POS-DEV-101A',
            created_at=now - timedelta(days=8, hours=5)
        )

        # Anomalous transaction: Off-hours bulk transaction
        txn_anomalous1 = DistributionTransaction(
            transaction_code='TXN-KA-800199',
            shop_id=shop1.id,
            beneficiary_id=beneficiaries[1].id,
            commodity='Rice',
            quantity=300.0,  # Abnormal bulk quantity!
            auth_mode=DistributionTransaction.AUTH_MANUAL,
            status=DistributionTransaction.STATUS_FLAGGED,
            biometric_match_score=0.18,
            pos_device_id='POS-DEV-101A',
            created_at=now - timedelta(days=2, hours=1, minutes=45)  # 2:00 AM off-hours
        )

        # Anomalous transaction: Duplicate card transaction
        txn_anomalous2 = DistributionTransaction(
            transaction_code='TXN-KA-800200',
            shop_id=shop2.id,
            beneficiary_id=beneficiaries[4].id,
            commodity='Rice',
            quantity=70.0,
            auth_mode=DistributionTransaction.AUTH_MANUAL,
            status=DistributionTransaction.STATUS_FLAGGED,
            biometric_match_score=0.25,
            pos_device_id='POS-DEV-102B',
            created_at=now - timedelta(days=1, hours=4)
        )

        db.session.add_all([txn1, txn2, txn3, txn_anomalous1, txn_anomalous2])
        db.session.flush()

        print("Seeding synthetic fraud alerts...")
        # 6. Fraud Alerts
        alerts = [
            FraudAlert(
                alert_code='ALT-2026-CRIT01',
                alert_type=FraudAlert.ALERT_BULK_DISPATCH,
                severity=FraudAlert.SEVERITY_CRITICAL,
                shop_id=shop1.id,
                transaction_id=txn_anomalous1.id,
                description='Abnormal bulk dispatch of 300.0kg Rice issued to single card during non-operational hours (02:15 AM).',
                status=FraudAlert.STATUS_DETECTED,
                confidence_score=0.96,
                detected_at=now - timedelta(days=2)
            ),
            FraudAlert(
                alert_code='ALT-2026-HIGH02',
                alert_type=FraudAlert.ALERT_BIOMETRIC_BYPASS,
                severity=FraudAlert.SEVERITY_HIGH,
                shop_id=shop1.id,
                transaction_id=txn_anomalous1.id,
                description='Spike in manual authentication overrides with sub-0.20 biometric matching score on POS device POS-DEV-101A.',
                status=FraudAlert.STATUS_INVESTIGATING,
                confidence_score=0.88,
                detected_at=now - timedelta(days=2, hours=3)
            ),
            FraudAlert(
                alert_code='ALT-2026-HIGH03',
                alert_type=FraudAlert.ALERT_GHOST_BENEFICIARY,
                severity=FraudAlert.SEVERITY_HIGH,
                shop_id=shop2.id,
                transaction_id=txn_anomalous2.id,
                description='Potential ghost beneficiary pattern: Dual grain entitlement claimed across disconnected jurisdictions within 3 hours.',
                status=FraudAlert.STATUS_DETECTED,
                confidence_score=0.82,
                detected_at=now - timedelta(days=1)
            ),
            FraudAlert(
                alert_code='ALT-2026-MED04',
                alert_type=FraudAlert.ALERT_OFF_HOURS,
                severity=FraudAlert.SEVERITY_MEDIUM,
                shop_id=shop1.id,
                transaction_id=txn_anomalous1.id,
                description='Distribution transaction attempted outside gazetted Fair Price Shop working hours (08:00 - 20:00).',
                status=FraudAlert.STATUS_INVESTIGATING,
                confidence_score=0.74,
                detected_at=now - timedelta(days=3)
            ),
            FraudAlert(
                alert_code='ALT-2026-CRIT05',
                alert_type=FraudAlert.ALERT_STOCK_DISCREPANCY,
                severity=FraudAlert.SEVERITY_CRITICAL,
                shop_id=shop2.id,
                transaction_id=None,
                description='Physical stock discrepancy detected: Recorded stock exceeds cumulative allocation by 640.0kg.',
                status=FraudAlert.STATUS_DETECTED,
                confidence_score=0.94,
                detected_at=now - timedelta(hours=14)
            )
        ]
        db.session.add_all(alerts)
        db.session.commit()
        print("Synthetic demo data seeding successfully completed!")


if __name__ == '__main__':
    seed_database()

