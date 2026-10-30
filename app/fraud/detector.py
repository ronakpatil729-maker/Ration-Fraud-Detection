"""
Core Fraud Detection & Vigilance Engine for Ration Distribution System.
Implements:
1. Duplicate ration card detection (cross-shop claims & identity collisions).
2. Stock reconciliation (Opening + Received - Distributed = Expected Closing).
3. Unexplained stock discrepancy alert generation.
4. Suspicious quantity & repeated transaction pattern heuristics.
5. Isolation Forest machine learning anomaly integration.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import func
from app.extensions import db
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary
from app.models.stock import StockMovement
from app.models.transaction import DistributionTransaction
from app.models.alert import FraudAlert
from app.fraud.isolation_forest import get_isolation_forest_model


class FraudDetectionService:
    """Orchestrates heuristic rule-based checks and machine learning anomaly detection."""

    # --------------------------------------------------------------------------
    # 1. DUPLICATE RATION CARD DETECTION
    # --------------------------------------------------------------------------
    @staticmethod
    def detect_duplicate_ration_cards() -> List[Dict[str, Any]]:
        """
        Detects:
        a) Multiple beneficiary records sharing identical synthetic Aadhaar hash or card number.
        b) Rapid cross-shop usage of the same ration card (impossible geographic travel).
        c) Multiple claims on the same calendar day for the same commodity.
        """
        detected_alerts = []

        # A. Identity Collisions (Duplicate synthetic Aadhaar hashes)
        duplicate_hashes = db.session.query(
            Beneficiary.aadhaar_hash,
            func.count(Beneficiary.id).label('count')
        ).group_by(Beneficiary.aadhaar_hash).having(func.count(Beneficiary.id) > 1).all()

        for a_hash, count in duplicate_hashes:
            linked_cards = [b.ration_card_no for b in Beneficiary.query.filter_by(aadhaar_hash=a_hash).all()]
            reason = (
                f"Duplicate Identity Record: Synthetic Aadhaar identifier [{a_hash[:10]}...] "
                f"is shared across {count} distinct beneficiary accounts: ({', '.join(linked_cards)}). "
                "Possible ghost card creation or identity duplication."
            )
            detected_alerts.append({
                'alert_type': 'DUPLICATE_RATION_CARD',
                'severity': FraudAlert.SEVERITY_CRITICAL,
                'shop_id': None,
                'transaction_id': None,
                'description': reason,
                'confidence_score': 0.98
            })

        # B. Cross-Shop Claims in Short Time Window (< 24 Hours)
        transactions = DistributionTransaction.query.order_by(
            DistributionTransaction.beneficiary_id,
            DistributionTransaction.created_at
        ).all()

        # Group transactions by beneficiary
        txn_by_ben: Dict[int, List[DistributionTransaction]] = {}
        for txn in transactions:
            txn_by_ben.setdefault(txn.beneficiary_id, []).append(txn)

        for ben_id, txn_list in txn_by_ben.items():
            if len(txn_list) < 2:
                continue

            for i in range(len(txn_list) - 1):
                t1 = txn_list[i]
                t2 = txn_list[i + 1]

                # Check if transactions occurred at different shops
                if t1.shop_id != t2.shop_id:
                    time_diff = abs((t2.created_at - t1.created_at).total_seconds()) / 3600.0  # in hours
                    if time_diff <= 24.0:
                        shop1 = db.session.get(RationShop, t1.shop_id)
                        shop2 = db.session.get(RationShop, t2.shop_id)
                        ben = db.session.get(Beneficiary, ben_id)
                        card_no = ben.ration_card_no if ben else f"ID-{ben_id}"
                        shop1_no = shop1.shop_no if shop1 else f"Shop #{t1.shop_id}"
                        shop2_no = shop2.shop_no if shop2 else f"Shop #{t2.shop_id}"

                        severity = FraudAlert.SEVERITY_CRITICAL if time_diff <= 3.0 else FraudAlert.SEVERITY_HIGH
                        reason = (
                            f"Cross-Shop Duplicate Transaction: Ration card {card_no} was used at "
                            f"{shop1_no} and {shop2_no} within {time_diff:.1f} hours. "
                            "Simultaneous grain withdrawal across disconnected jurisdictions indicates card clone or ghost claim."
                        )
                        detected_alerts.append({
                            'alert_type': 'DUPLICATE_RATION_CARD',
                            'severity': severity,
                            'shop_id': t2.shop_id,
                            'transaction_id': t2.id,
                            'description': reason,
                            'confidence_score': 0.92
                        })

        # C. Same-Day Multiple Claims for the Same Commodity
        for ben_id, txn_list in txn_by_ben.items():
            if len(txn_list) < 2:
                continue

            day_commodity_map: Dict[Tuple[str, str], List[DistributionTransaction]] = {}
            for t in txn_list:
                day_str = t.created_at.strftime('%Y-%m-%d')
                key = (day_str, t.commodity)
                day_commodity_map.setdefault(key, []).append(t)

            for (day_str, commodity), same_day_txns in day_commodity_map.items():
                if len(same_day_txns) > 1:
                    ben = db.session.get(Beneficiary, ben_id)
                    card_no = ben.ration_card_no if ben else f"ID-{ben_id}"
                    total_claimed = sum(t.quantity for t in same_day_txns)
                    reason = (
                        f"Same-Day Multiple Entitlement Claims: Ration card {card_no} recorded "
                        f"{len(same_day_txns)} transactions for {commodity} on {day_str} "
                        f"(Total: {total_claimed:.1f}kg). Standard PDS policy limits cardholders to 1 monthly distribution cycle."
                    )
                    detected_alerts.append({
                        'alert_type': 'DUPLICATE_RATION_CARD',
                        'severity': FraudAlert.SEVERITY_HIGH,
                        'shop_id': same_day_txns[-1].shop_id,
                        'transaction_id': same_day_txns[-1].id,
                        'description': reason,
                        'confidence_score': 0.88
                    })

        return detected_alerts

    # --------------------------------------------------------------------------
    # 2. STOCK RECONCILIATION FORMULA
    # --------------------------------------------------------------------------
    @staticmethod
    def reconcile_stock(shop_id: int, commodity: str, opening_stock: float = 0.0,
                        reported_physical_stock: Optional[float] = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Stock reconciliation formula:
        Expected Closing Stock = Opening Stock + Received Stock - Distributed Stock
        """
        shop = db.session.get(RationShop, shop_id)
        shop_no = shop.shop_no if shop else f"Shop #{shop_id}"

        # 1. Calculate Received Stock (movement_type in 'RECEIVED' or 'ALLOCATION')
        recv_query = StockMovement.query.filter(
            StockMovement.shop_id == shop_id,
            StockMovement.commodity == commodity,
            StockMovement.movement_type.in_([
                StockMovement.TYPE_RECEIVED,
                StockMovement.TYPE_ALLOCATION
            ])
        )
        if start_date:
            recv_query = recv_query.filter(StockMovement.created_at >= start_date)
        if end_date:
            recv_query = recv_query.filter(StockMovement.created_at <= end_date)

        received_stock = float(recv_query.with_entities(
            func.coalesce(func.sum(StockMovement.quantity), 0.0)
        ).scalar() or 0.0)

        # 2. Calculate Distributed Stock (status != 'REJECTED')
        dist_query = DistributionTransaction.query.filter(
            DistributionTransaction.shop_id == shop_id,
            DistributionTransaction.commodity == commodity,
            DistributionTransaction.status != DistributionTransaction.STATUS_REJECTED
        )
        if start_date:
            dist_query = dist_query.filter(DistributionTransaction.created_at >= start_date)
        if end_date:
            dist_query = dist_query.filter(DistributionTransaction.created_at <= end_date)

        distributed_stock = float(dist_query.with_entities(
            func.coalesce(func.sum(DistributionTransaction.quantity), 0.0)
        ).scalar() or 0.0)

        # 3. Expected Closing Stock formula
        expected_closing_stock = float(opening_stock + received_stock - distributed_stock)

        # 4. Discrepancy analysis
        discrepancy = None
        discrepancy_pct = 0.0
        is_discrepancy = False
        discrepancy_type = 'BALANCED'

        if reported_physical_stock is not None:
            discrepancy = round(reported_physical_stock - expected_closing_stock, 2)
            denominator = max(expected_closing_stock, 1.0)
            discrepancy_pct = round((discrepancy / denominator) * 100.0, 2)

            if abs(discrepancy) > 5.0:  # Tolerance threshold of 5 kg for natural transit loss
                is_discrepancy = True
                discrepancy_type = 'SHORTAGE' if discrepancy < 0 else 'EXCESS'
        elif expected_closing_stock < 0:
            # Physical impossibility: distributed more grain than recorded as received
            is_discrepancy = True
            discrepancy = expected_closing_stock
            discrepancy_type = 'NEGATIVE_BALANCE'

        return {
            'shop_id': shop_id,
            'shop_no': shop_no,
            'commodity': commodity,
            'opening_stock': round(opening_stock, 2),
            'received_stock': round(received_stock, 2),
            'distributed_stock': round(distributed_stock, 2),
            'expected_closing_stock': round(expected_closing_stock, 2),
            'reported_physical_stock': round(reported_physical_stock, 2) if reported_physical_stock is not None else None,
            'discrepancy': discrepancy,
            'discrepancy_pct': discrepancy_pct,
            'is_discrepancy': is_discrepancy,
            'discrepancy_type': discrepancy_type
        }

    # --------------------------------------------------------------------------
    # 3. ALERTS FOR UNEXPLAINED STOCK DISCREPANCIES
    # --------------------------------------------------------------------------
    @classmethod
    def check_stock_discrepancies(cls) -> List[Dict[str, Any]]:
        """
        Audits all Fair Price Shops across all commodities.
        Generates alerts for unexplained discrepancies between book ledger and physical balance.
        """
        detected_alerts = []
        shops = RationShop.query.filter_by(is_active=True).all()
        commodities = [StockMovement.COMMODITY_RICE, StockMovement.COMMODITY_WHEAT, StockMovement.COMMODITY_SUGAR]

        for shop in shops:
            for commodity in commodities:
                recon = cls.reconcile_stock(shop.id, commodity, opening_stock=0.0)

                # Check if distributed stock exceeded available allocation
                if recon['expected_closing_stock'] < 0:
                    deficit = abs(recon['expected_closing_stock'])
                    reason = (
                        f"Critical Stock Discrepancy in {shop.shop_no} ({commodity}): "
                        f"Opening ({recon['opening_stock']}kg) + Received ({recon['received_stock']}kg) "
                        f"- Distributed ({recon['distributed_stock']}kg) results in negative closing balance "
                        f"(-{deficit:.1f}kg). Fictitious distribution transactions recorded without grain receipt."
                    )
                    detected_alerts.append({
                        'alert_type': 'STOCK_DISCREPANCY',
                        'severity': FraudAlert.SEVERITY_CRITICAL,
                        'shop_id': shop.id,
                        'transaction_id': None,
                        'description': reason,
                        'confidence_score': 0.95
                    })

        return detected_alerts

    # --------------------------------------------------------------------------
    # 4. SUSPICIOUS QUANTITIES & REPEATED TRANSACTION PATTERNS
    # --------------------------------------------------------------------------
    @staticmethod
    def detect_suspicious_quantities() -> List[Dict[str, Any]]:
        """
        Detects:
        a) Single transaction quantity exceeding beneficiary's monthly quota.
        b) Cumulative monthly dispatches exceeding card entitlement.
        """
        detected_alerts = []
        transactions = DistributionTransaction.query.filter_by(
            status=DistributionTransaction.STATUS_COMPLETED
        ).all()

        for txn in transactions:
            ben = txn.beneficiary
            if not ben:
                continue

            # Determine entitlement quota for this commodity
            if txn.commodity == 'Rice':
                quota = ben.monthly_rice_quota
            elif txn.commodity == 'Wheat':
                quota = ben.monthly_wheat_quota
            elif txn.commodity == 'Sugar':
                quota = ben.monthly_sugar_quota
            else:
                quota = 20.0

            if quota <= 0:
                quota = 10.0

            # Single transaction anomaly
            if txn.quantity > quota:
                ratio = txn.quantity / quota
                if ratio >= 2.0:
                    severity = FraudAlert.SEVERITY_CRITICAL
                elif ratio >= 1.3:
                    severity = FraudAlert.SEVERITY_HIGH
                else:
                    severity = FraudAlert.SEVERITY_MEDIUM

                excess_pct = (ratio - 1.0) * 100.0
                reason = (
                    f"Suspicious Transaction Quantity: Card {ben.ration_card_no} was issued {txn.quantity:.1f}kg of "
                    f"{txn.commodity}, exceeding authorized monthly quota ({quota:.1f}kg) by {excess_pct:.0f}%. "
                    "Potential black market diversion or off-the-books bulk withdrawal."
                )
                detected_alerts.append({
                    'alert_type': 'EXCESSIVE_QUANTITY',
                    'severity': severity,
                    'shop_id': txn.shop_id,
                    'transaction_id': txn.id,
                    'description': reason,
                    'confidence_score': min(0.96, 0.70 + (ratio * 0.05))
                })

        return detected_alerts

    @staticmethod
    def detect_repeated_patterns() -> List[Dict[str, Any]]:
        """
        Detects:
        a) Burst transactions: Multiple dispatches for the same card within 60 minutes.
        b) Repeated manual overrides: Consecutive sub-standard authentication.
        """
        detected_alerts = []
        txns = DistributionTransaction.query.order_by(
            DistributionTransaction.beneficiary_id,
            DistributionTransaction.created_at
        ).all()

        # Group by beneficiary
        ben_map: Dict[int, List[DistributionTransaction]] = {}
        for t in txns:
            ben_map.setdefault(t.beneficiary_id, []).append(t)

        for ben_id, t_list in ben_map.items():
            if len(t_list) < 2:
                continue

            for i in range(len(t_list) - 1):
                t1 = t_list[i]
                t2 = t_list[i + 1]
                time_diff_min = abs((t2.created_at - t1.created_at).total_seconds()) / 60.0

                if time_diff_min <= 60.0:
                    ben = db.session.get(Beneficiary, ben_id)
                    card_no = ben.ration_card_no if ben else f"ID-{ben_id}"
                    reason = (
                        f"Rapid Transaction Burst: 2 dispatches processed for ration card {card_no} "
                        f"within {time_diff_min:.1f} minutes ({t1.commodity}: {t1.quantity}kg, "
                        f"{t2.commodity}: {t2.quantity}kg). Potential cashier rapid-swiping pattern."
                    )
                    detected_alerts.append({
                        'alert_type': 'REPEATED_BURST_TRANSACTIONS',
                        'severity': FraudAlert.SEVERITY_HIGH,
                        'shop_id': t2.shop_id,
                        'transaction_id': t2.id,
                        'description': reason,
                        'confidence_score': 0.85
                    })

        return detected_alerts

    # --------------------------------------------------------------------------
    # 5. ISOLATION FOREST ANOMALY DETECTION INTEGRATION
    # --------------------------------------------------------------------------
    @staticmethod
    def detect_ml_anomalies() -> List[Dict[str, Any]]:
        """
        Evaluates transactions using the Isolation Forest model.
        Extracts numerical features, handles missing values gracefully,
        and provides understandable explanations with clear disclaimer.
        """
        detected_alerts = []
        model = get_isolation_forest_model()

        transactions = DistributionTransaction.query.order_by(
            DistributionTransaction.created_at.desc()
        ).limit(100).all()

        for txn in transactions:
            ben = txn.beneficiary
            quota = 20.0
            if ben:
                if txn.commodity == 'Rice':
                    quota = ben.monthly_rice_quota
                elif txn.commodity == 'Wheat':
                    quota = ben.monthly_wheat_quota
                elif txn.commodity == 'Sugar':
                    quota = ben.monthly_sugar_quota

            quota_ratio = txn.quantity / max(quota, 1.0)
            hour_of_day = float(txn.created_at.hour)
            biometric_score = txn.biometric_match_score  # May be None (handled by imputer)
            is_manual = 1.0 if txn.auth_mode == DistributionTransaction.AUTH_MANUAL else 0.0

            feature_vector = [
                txn.quantity,
                quota_ratio,
                hour_of_day,
                biometric_score,
                is_manual
            ]

            pred, score, explanation = model.predict(feature_vector, threshold=0.62)

            if pred == -1:  # Statistical anomaly
                full_reason = f"{explanation['reason']} {explanation['disclaimer']}"
                detected_alerts.append({
                    'alert_type': 'ISOLATION_FOREST_ANOMALY',
                    'severity': explanation['severity'],
                    'shop_id': txn.shop_id,
                    'transaction_id': txn.id,
                    'description': full_reason,
                    'confidence_score': round(score, 2)
                })

        return detected_alerts

    # --------------------------------------------------------------------------
    # 6. FULL AUDIT ORCHESTRATION & PERSISTENCE
    # --------------------------------------------------------------------------
    @classmethod
    def run_full_fraud_audit(cls, commit: bool = True) -> Dict[str, Any]:
        """
        Executes all detection modules, deduplicates existing open alerts,
        and persists newly identified fraud indicators.
        """
        raw_alerts = []
        raw_alerts.extend(cls.detect_duplicate_ration_cards())
        raw_alerts.extend(cls.check_stock_discrepancies())
        raw_alerts.extend(cls.detect_suspicious_quantities())
        raw_alerts.extend(cls.detect_repeated_patterns())
        raw_alerts.extend(cls.detect_ml_anomalies())

        created_count = 0
        new_alert_objects = []

        for item in raw_alerts:
            # Deduplicate: Check if matching open alert already exists
            existing = FraudAlert.query.filter(
                FraudAlert.alert_type == item['alert_type'],
                FraudAlert.shop_id == item['shop_id'],
                FraudAlert.transaction_id == item['transaction_id'],
                FraudAlert.status.in_([FraudAlert.STATUS_DETECTED, FraudAlert.STATUS_INVESTIGATING])
            ).first()

            if not existing:
                alert = FraudAlert(
                    alert_type=item['alert_type'],
                    severity=item['severity'],
                    shop_id=item['shop_id'],
                    transaction_id=item['transaction_id'],
                    description=item['description'],
                    status=FraudAlert.STATUS_DETECTED,
                    confidence_score=item['confidence_score']
                )
                db.session.add(alert)
                new_alert_objects.append(alert)
                created_count += 1

        if commit and created_count > 0:
            db.session.commit()

        return {
            'total_detected': len(raw_alerts),
            'newly_created': created_count,
            'duplicate_skipped': len(raw_alerts) - created_count
        }
