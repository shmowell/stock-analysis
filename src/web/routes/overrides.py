"""Override apply and review routes."""

import json
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app

bp = Blueprint('overrides', __name__)


@bp.route('/')
def override_list():
    """List all override records."""
    from overrides.override_logger import OverrideLogger

    ticker_filter = request.args.get('ticker')
    overrides = []

    try:
        logger = OverrideLogger()
        overrides = logger.load_all_overrides(ticker=ticker_filter)
    except Exception as e:
        flash(f'Error loading overrides: {e}', 'error')

    return render_template(
        'overrides/list.html',
        overrides=overrides,
        ticker_filter=ticker_filter,
    )


@bp.route('/summary')
def summary():
    """Override statistics summary."""
    from overrides.override_logger import OverrideLogger

    stats = {}
    try:
        logger = OverrideLogger()
        all_overrides = logger.load_all_overrides()
        stats = logger.calculate_override_statistics(all_overrides)
    except Exception as e:
        flash(f'Error loading statistics: {e}', 'error')

    return render_template('overrides/summary.html', stats=stats)


@bp.route('/detail/<ticker>')
def detail(ticker):
    """Detailed override history for one ticker."""
    from overrides.override_logger import OverrideLogger

    ticker = ticker.upper()
    overrides = []

    try:
        logger = OverrideLogger()
        overrides = logger.load_all_overrides(ticker=ticker)
    except Exception as e:
        flash(f'Error loading overrides: {e}', 'error')

    return render_template(
        'overrides/detail.html',
        ticker=ticker,
        overrides=overrides,
    )


@bp.route('/apply', methods=['GET'])
def apply_form():
    """Show override application form (Model-First: base scores displayed first)."""
    project_root = current_app.config['PROJECT_ROOT']
    scores_path = project_root / 'data' / 'processed' / 'latest_scores.json'

    scores = []
    selected_ticker = request.args.get('ticker', '').upper()
    selected_score = None

    if scores_path.exists():
        try:
            with open(scores_path) as f:
                data = json.load(f)
            scores = data.get('scores', [])

            if selected_ticker:
                for s in scores:
                    if s['ticker'] == selected_ticker:
                        selected_score = s
                        break
        except Exception as e:
            flash(f'Error loading scores: {e}', 'error')

    return render_template(
        'overrides/apply.html',
        scores=scores,
        selected_ticker=selected_ticker,
        selected_score=selected_score,
    )


@bp.route('/apply', methods=['POST'])
def apply_submit():
    """Process override submission."""
    from models.composite import CompositeScore, Recommendation
    from overrides import (
        ConvictionLevel, OverrideDocumentation, OverrideLogger,
        OverrideManager, OverrideRequest, OverrideType,
        OverrideValidationError, SentimentOverride, WeightOverride,
    )

    project_root = current_app.config['PROJECT_ROOT']
    scores_path = project_root / 'data' / 'processed' / 'latest_scores.json'

    ticker = request.form.get('ticker', '').upper()

    # Load universe
    if not scores_path.exists():
        flash('No scores available. Run scoring first.', 'error')
        return redirect(url_for('overrides.apply_form'))

    with open(scores_path) as f:
        data = json.load(f)

    universe = []
    target = None
    for s in data.get('scores', []):
        cs = CompositeScore(
            ticker=s['ticker'],
            fundamental_score=s['fundamental_score'],
            technical_score=s['technical_score'],
            sentiment_score=s['sentiment_score'],
            composite_score=s['composite_score'],
            composite_percentile=s['composite_percentile'],
            recommendation=Recommendation(s['recommendation']),
        )
        universe.append(cs)
        if s['ticker'] == ticker:
            target = cs

    if not target:
        flash(f'Ticker {ticker} not found in scores', 'error')
        return redirect(url_for('overrides.apply_form'))

    # Parse form fields
    wf = request.form.get('weight_fundamental')
    wt = request.form.get('weight_technical')
    ws = request.form.get('weight_sentiment')
    sa = request.form.get('sentiment_adjustment')

    has_weight = any(v for v in [wf, wt, ws])
    has_sentiment = bool(sa)

    if has_weight and has_sentiment:
        override_type = OverrideType.BOTH
    elif has_weight:
        override_type = OverrideType.WEIGHT_ADJUSTMENT
    elif has_sentiment:
        override_type = OverrideType.SENTIMENT_ADJUSTMENT
    else:
        flash('No override specified. Set weights or sentiment adjustment.', 'warning')
        return redirect(url_for('overrides.apply_form', ticker=ticker))

    weight_override = None
    if has_weight:
        weight_override = WeightOverride(
            float(wf) if wf else 0.45,
            float(wt) if wt else 0.35,
            float(ws) if ws else 0.20,
        )

    sentiment_override = None
    if has_sentiment:
        sentiment_override = SentimentOverride(adjustment=float(sa))

    conviction = ConvictionLevel(request.form.get('conviction', 'Medium'))
    evidence_raw = request.form.get('evidence', '')
    evidence = [e.strip() for e in evidence_raw.split('\n') if e.strip()] or None

    documentation = OverrideDocumentation(
        what_model_misses=request.form.get('what_model_misses', ''),
        why_view_more_accurate=request.form.get('why_accurate', ''),
        what_proves_wrong=request.form.get('what_proves_wrong', ''),
        conviction=conviction,
        evidence_pieces=evidence,
    )

    override_request = OverrideRequest(
        ticker=ticker,
        override_type=override_type,
        weight_override=weight_override,
        sentiment_override=sentiment_override,
        documentation=documentation,
    )

    manager = OverrideManager()
    override_logger = OverrideLogger()

    try:
        result = manager.apply_override(target, override_request, universe)
    except OverrideValidationError as e:
        flash(f'Validation failed: {e}', 'error')
        return redirect(url_for('overrides.apply_form', ticker=ticker))

    log_path = override_logger.log_override(result)
    flash(f'Override applied for {ticker}. Logged to {log_path}', 'success')

    return render_template(
        'overrides/result.html',
        ticker=ticker,
        result=result,
    )
