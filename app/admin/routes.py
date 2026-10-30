from datetime import datetime, timezone
from collections import defaultdict
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.auth.utils import admin_required
from app.models.user import User
from app.models.shop import RationShop
from app.models.beneficiary import Beneficiary
from app.models.stock import StockMovement
from app.models.transaction import DistributionTransaction
from app.models.alert import FraudAlert
from app.fraud.detector import FraudDetectionService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """
    Responsive Admin Dashboard connected to real database data.
    Provides:
    - 4 KPI summary cards (shops, beneficiaries, transactions, pending alerts)
    - Monthly distribution chart dataset
    - Stock discrepancy chart dataset
    - Shop-wise risk summaries
    - Searchable and filterable fraud alerts table
    """
    # 1. Real Summary KPI Metrics
    total_shops = RationShop.query.count()
    total_beneficiaries = Beneficiary.query.count()
    total_transactions = DistributionTransaction.query.count()
    flagged_transactions = DistributionTransaction.query.filter_by(
        status=DistributionTransaction.STATUS_FLAGGED
    ).count()

    total_alerts = FraudAlert.query.count()
    critical_alerts = FraudAlert.query.filter_by(severity=FraudAlert.SEVERITY_CRITICAL).count()
    high_alerts = FraudAlert.query.filter_by(severity=FraudAlert.SEVERITY_HIGH).count()
    pending_alerts = FraudAlert.query.filter(
        FraudAlert.status.in_([FraudAlert.STATUS_DETECTED, FraudAlert.STATUS_INVESTIGATING])
    ).count()

    # 2. Real Monthly Distribution Data (grouped by month and commodity)
    monthly_rows = db.session.query(
        func.strftime('%Y-%m', DistributionTransaction.created_at).label('month_label'),
        DistributionTransaction.commodity,
        func.coalesce(func.sum(DistributionTransaction.quantity), 0.0).label('total_kg')
    ).filter(
        DistributionTransaction.status != DistributionTransaction.STATUS_REJECTED
    ).group_by(
        'month_label',
        DistributionTransaction.commodity
    ).order_by('month_label').all()

    # Process monthly distribution for Chart.js
    month_set = sorted(list({r[0] for r in monthly_rows})) if monthly_rows else [datetime.now(timezone.utc).strftime('%Y-%m')]
    month_labels = [datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in month_set]

    # Organize commodity totals per month
    monthly_series = {'Rice': [0.0] * len(month_set), 'Wheat': [0.0] * len(month_set), 'Sugar': [0.0] * len(month_set)}
    for row in monthly_rows:
        m_idx = month_set.index(row[0])
        comm = row[1]
        if comm in monthly_series:
            monthly_series[comm][m_idx] = round(float(row[2]), 1)

    monthly_chart_data = {
        'labels': month_labels,
        'rice': monthly_series['Rice'],
        'wheat': monthly_series['Wheat'],
        'sugar': monthly_series['Sugar']
    }

    # 3. Real Stock Discrepancy Data across Fair Price Shops
    # Formula: Expected Closing = Opening + Received - Distributed
    shops = RationShop.query.order_by(RationShop.shop_no).all()
    discrepancy_labels = []
    discrepancy_received = []
    discrepancy_distributed = []
    discrepancy_closing = []
    discrepancy_deficits = []

    for shop in shops:
        discrepancy_labels.append(shop.shop_no)
        # Calculate totals across all commodities for this shop
        shop_recv = float(db.session.query(
            func.coalesce(func.sum(StockMovement.quantity), 0.0)
        ).filter(
            StockMovement.shop_id == shop.id,
            StockMovement.movement_type.in_([StockMovement.TYPE_RECEIVED, StockMovement.TYPE_ALLOCATION])
        ).scalar() or 0.0)

        shop_dist = float(db.session.query(
            func.coalesce(func.sum(DistributionTransaction.quantity), 0.0)
        ).filter(
            DistributionTransaction.shop_id == shop.id,
            DistributionTransaction.status != DistributionTransaction.STATUS_REJECTED
        ).scalar() or 0.0)

        expected_closing = round(shop_recv - shop_dist, 1)
        discrepancy_received.append(round(shop_recv, 1))
        discrepancy_distributed.append(round(shop_dist, 1))
        discrepancy_closing.append(max(expected_closing, 0.0))
        # Deficit indicator if expected closing is negative (ghost transactions)
        discrepancy_deficits.append(abs(expected_closing) if expected_closing < 0 else 0.0)

    stock_discrepancy_chart_data = {
        'labels': discrepancy_labels,
        'received': discrepancy_received,
        'distributed': discrepancy_distributed,
        'closing': discrepancy_closing,
        'deficits': discrepancy_deficits
    }

    # 4. Real Shop-Wise Risk Summaries
    shop_risk_summaries = []
    for shop in shops:
        alerts_for_shop = FraudAlert.query.filter_by(shop_id=shop.id).all()
        crit_count = sum(1 for a in alerts_for_shop if a.severity == FraudAlert.SEVERITY_CRITICAL)
        high_cnt = sum(1 for a in alerts_for_shop if a.severity == FraudAlert.SEVERITY_HIGH)
        pend_cnt = sum(1 for a in alerts_for_shop if a.status in [FraudAlert.STATUS_DETECTED, FraudAlert.STATUS_INVESTIGATING])
        resolved_cnt = sum(1 for a in alerts_for_shop if a.status == FraudAlert.STATUS_RESOLVED)

        dist_kg = float(db.session.query(
            func.coalesce(func.sum(DistributionTransaction.quantity), 0.0)
        ).filter_by(shop_id=shop.id).scalar() or 0.0)

        # Risk level assessment
        if crit_count > 0:
            risk_tier = 'CRITICAL'
            risk_badge = 'danger'
        elif high_cnt > 0 or len(alerts_for_shop) >= 2:
            risk_tier = 'HIGH'
            risk_badge = 'warning'
        elif len(alerts_for_shop) > 0:
            risk_tier = 'MEDIUM'
            risk_badge = 'info'
        else:
            risk_tier = 'NORMAL'
            risk_badge = 'success'

        shop_risk_summaries.append({
            'shop': shop,
            'total_alerts': len(alerts_for_shop),
            'critical_count': crit_count,
            'high_count': high_cnt,
            'pending_count': pend_cnt,
            'resolved_count': resolved_cnt,
            'total_distributed_kg': round(dist_kg, 1),
            'risk_tier': risk_tier,
            'risk_badge': risk_badge
        })

    # 5. Searchable & Filterable Fraud Alerts
    search_q = request.args.get('q', '').strip()
    severity_filter = request.args.get('severity', '').strip()
    status_filter = request.args.get('status', '').strip()
    shop_filter = request.args.get('shop_id', type=int)

    alert_query = FraudAlert.query

    if search_q:
        search_term = f"%{search_q}%"
        alert_query = alert_query.join(RationShop, FraudAlert.shop_id == RationShop.id, isouter=True).filter(
            (FraudAlert.alert_code.ilike(search_term)) |
            (FraudAlert.description.ilike(search_term)) |
            (FraudAlert.alert_type.ilike(search_term)) |
            (RationShop.shop_no.ilike(search_term)) |
            (RationShop.name.ilike(search_term))
        )
    if severity_filter:
        alert_query = alert_query.filter(FraudAlert.severity == severity_filter)
    if status_filter:
        alert_query = alert_query.filter(FraudAlert.status == status_filter)
    if shop_filter:
        alert_query = alert_query.filter(FraudAlert.shop_id == shop_filter)

    alerts_list = alert_query.order_by(FraudAlert.detected_at.desc()).all()

    # Severity counts for donut chart
    severity_counts = {
        'CRITICAL': critical_alerts,
        'HIGH': high_alerts,
        'MEDIUM': FraudAlert.query.filter_by(severity=FraudAlert.SEVERITY_MEDIUM).count(),
        'LOW': FraudAlert.query.filter_by(severity=FraudAlert.SEVERITY_LOW).count()
    }

    return render_template(
        'admin/dashboard.html',
        total_shops=total_shops,
        total_beneficiaries=total_beneficiaries,
        total_transactions=total_transactions,
        flagged_transactions=flagged_transactions,
        total_alerts=total_alerts,
        critical_alerts=critical_alerts,
        pending_alerts=pending_alerts,
        recent_alerts=alerts_list,
        shops=shops,
        search_q=search_q,
        selected_severity=severity_filter,
        selected_status=status_filter,
        selected_shop_id=shop_filter,
        severity_counts=severity_counts,
        monthly_chart_data=monthly_chart_data,
        stock_discrepancy_chart_data=stock_discrepancy_chart_data,
        shop_risk_summaries=shop_risk_summaries
    )


@admin_bp.route('/alerts')
@login_required
@admin_required
def alerts():
    """Comprehensive Alert Register with filtering & search."""
    search_q = request.args.get('q', '').strip()
    severity_filter = request.args.get('severity', '')
    status_filter = request.args.get('status', '')
    shop_id_filter = request.args.get('shop_id', type=int)

    query = FraudAlert.query

    if search_q:
        search_term = f"%{search_q}%"
        query = query.join(RationShop, FraudAlert.shop_id == RationShop.id, isouter=True).filter(
            (FraudAlert.alert_code.ilike(search_term)) |
            (FraudAlert.description.ilike(search_term)) |
            (FraudAlert.alert_type.ilike(search_term)) |
            (RationShop.shop_no.ilike(search_term)) |
            (RationShop.name.ilike(search_term))
        )
    if severity_filter:
        query = query.filter(FraudAlert.severity == severity_filter)
    if status_filter:
        query = query.filter(FraudAlert.status == status_filter)
    if shop_id_filter:
        query = query.filter(FraudAlert.shop_id == shop_id_filter)

    alerts_list = query.order_by(FraudAlert.detected_at.desc()).all()
    shops = RationShop.query.order_by(RationShop.shop_no).all()

    return render_template(
        'admin/alerts.html',
        alerts=alerts_list,
        shops=shops,
        search_q=search_q,
        selected_severity=severity_filter,
        selected_status=status_filter,
        selected_shop_id=shop_id_filter,
        severities=FraudAlert.SEVERITIES,
        statuses=FraudAlert.STATUSES
    )


@admin_bp.route('/alerts/<int:alert_id>')
@login_required
@admin_required
def alert_detail(alert_id):
    """
    Dedicated Alert Details page providing deep-dive explanatory analysis,
    transaction context, FPS dealer mapping, and investigation actions.
    """
    alert = db.session.get(FraudAlert, alert_id)
    if not alert:
        abort(404)

    # Contextual metadata breakdown
    shop = alert.shop
    transaction = alert.transaction
    beneficiary = transaction.beneficiary if transaction else None

    # Compute additional diagnostic context
    reconciliation_context = None
    if shop:
        reconciliation_context = FraudDetectionService.reconcile_stock(
            shop.id,
            transaction.commodity if transaction else 'Rice'
        )

    return render_template(
        'admin/alert_detail.html',
        alert=alert,
        shop=shop,
        transaction=transaction,
        beneficiary=beneficiary,
        reconciliation_context=reconciliation_context
    )


@admin_bp.route('/alerts/<int:alert_id>/status', methods=['POST'])
@login_required
@admin_required
def update_alert_status(alert_id):
    """
    Update investigation status and notes.
    Supports quick-action buttons ('Mark as Under Review', 'Mark as Resolved', 'Dismiss').
    """
    alert = db.session.get(FraudAlert, alert_id)
    if not alert:
        abort(404)

    new_status = request.form.get('status')
    notes = request.form.get('resolution_notes', '').strip()

    if new_status in FraudAlert.STATUSES:
        alert.status = new_status
        if notes:
            now_str = datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')
            if alert.resolution_notes:
                alert.resolution_notes += f"\n[{now_str}] {notes}"
            else:
                alert.resolution_notes = f"[{now_str}] {notes}"

        if new_status in [FraudAlert.STATUS_RESOLVED, FraudAlert.STATUS_DISMISSED]:
            alert.resolved_at = datetime.now(timezone.utc)
        else:
            alert.resolved_at = None

        db.session.commit()
        status_display = 'Under Review' if new_status == 'INVESTIGATING' else new_status.title()
        flash(f"Alert {alert.alert_code} marked as '{status_display}'.", 'success')
    else:
        flash("Invalid status selection provided.", 'danger')

    next_page = request.form.get('next') or request.referrer or url_for('admin.alerts')
    return redirect(next_page)


@admin_bp.route('/run-audit', methods=['POST'])
@login_required
@admin_required
def run_audit():
    """Trigger the automated fraud detection & stock reconciliation audit."""
    result = FraudDetectionService.run_full_fraud_audit(commit=True)
    msg = (
        f"Automated Vigilance Audit completed! {result['total_detected']} anomaly patterns analyzed. "
        f"{result['newly_created']} new alert(s) generated ({result['duplicate_skipped']} already recorded)."
    )
    flash(msg, 'info')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/reconciliation')
@login_required
@admin_required
def reconciliation():
    """Stock reconciliation overview: Opening + Received - Distributed = Expected Closing."""
    shops = RationShop.query.order_by(RationShop.shop_no).all()
    commodities = [StockMovement.COMMODITY_RICE, StockMovement.COMMODITY_WHEAT, StockMovement.COMMODITY_SUGAR]
    reconciliation_data = []

    for shop in shops:
        for commodity in commodities:
            data = FraudDetectionService.reconcile_stock(shop.id, commodity, opening_stock=0.0)
            reconciliation_data.append(data)

    return render_template(
        'admin/reconciliation.html',
        reconciliation_data=reconciliation_data
    )
