"""Stock universe management routes."""

from flask import Blueprint, render_template, request, redirect, url_for, flash

bp = Blueprint('universe', __name__)


@bp.route('/')
def universe_list():
    """Display current stock universe grouped by sector."""
    from database import get_db_session
    from database.models import Stock

    sectors = {}
    inactive = []

    try:
        with get_db_session() as session:
            active = (
                session.query(Stock)
                .filter_by(is_active=True)
                .order_by(Stock.sector, Stock.ticker)
                .all()
            )
            inactive = (
                session.query(Stock)
                .filter_by(is_active=False)
                .order_by(Stock.ticker)
                .all()
            )

            for s in active:
                sector = s.sector or 'Unknown'
                sectors.setdefault(sector, []).append({
                    'ticker': s.ticker,
                    'name': s.company_name or '',
                    'market_cap': float(s.market_cap) if s.market_cap else None,
                    'industry': s.industry or '',
                })

            inactive = [{
                'ticker': s.ticker,
                'name': s.company_name or '',
            } for s in inactive]

    except Exception as e:
        flash(f'Error loading universe: {e}', 'error')

    return render_template(
        'universe/list.html',
        sectors=sectors,
        inactive=inactive,
        total_active=sum(len(v) for v in sectors.values()),
    )


@bp.route('/add', methods=['GET', 'POST'])
def add():
    """Add stocks to the universe."""
    if request.method == 'GET':
        return render_template('universe/add.html')

    tickers_raw = request.form.get('tickers', '')
    tickers = [t.strip().upper() for t in tickers_raw.replace(',', ' ').split() if t.strip()]

    if not tickers:
        flash('No tickers provided', 'error')
        return redirect(url_for('universe.add'))

    from database import get_db_session
    from database.models import Stock
    from data_collection import YahooFinanceCollector

    collector = YahooFinanceCollector()
    added = []
    errors = []

    try:
        with get_db_session() as session:
            for ticker in tickers:
                existing = session.query(Stock).filter_by(ticker=ticker).first()

                if existing and existing.is_active:
                    flash(f'{ticker}: already in universe', 'warning')
                    continue
                elif existing and not existing.is_active:
                    existing.is_active = True
                    added.append(ticker)
                    flash(f'{ticker}: reactivated', 'success')
                    continue

                try:
                    data = collector.get_stock_data(ticker)
                    info = data['company_info']
                    fund = data['fundamental']

                    stock = Stock(
                        ticker=ticker,
                        company_name=info.get('name'),
                        sector=info.get('sector'),
                        industry=info.get('industry'),
                        market_cap=fund.get('market_cap'),
                        is_active=True,
                    )
                    session.add(stock)
                    added.append(ticker)
                    flash(f'{ticker}: added ({info.get("name", "")})', 'success')
                except Exception as e:
                    errors.append(ticker)
                    flash(f'{ticker}: failed - {e}', 'error')
    except Exception as e:
        flash(f'Database error: {e}', 'error')

    if added:
        flash(f'Run data collection to populate data for new stocks.', 'info')

    return redirect(url_for('universe.universe_list'))


@bp.route('/remove', methods=['POST'])
def remove():
    """Soft-delete a stock from the universe."""
    ticker = request.form.get('ticker', '').upper()
    if not ticker:
        flash('No ticker provided', 'error')
        return redirect(url_for('universe.universe_list'))

    from database import get_db_session
    from database.models import Stock

    try:
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                flash(f'{ticker}: not found', 'error')
            elif not stock.is_active:
                flash(f'{ticker}: already inactive', 'warning')
            else:
                stock.is_active = False
                flash(f'{ticker}: deactivated', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')

    return redirect(url_for('universe.universe_list'))


@bp.route('/reactivate', methods=['POST'])
def reactivate():
    """Reactivate a previously removed stock."""
    ticker = request.form.get('ticker', '').upper()
    if not ticker:
        flash('No ticker provided', 'error')
        return redirect(url_for('universe.universe_list'))

    from database import get_db_session
    from database.models import Stock

    try:
        with get_db_session() as session:
            stock = session.query(Stock).filter_by(ticker=ticker).first()
            if not stock:
                flash(f'{ticker}: not found', 'error')
            elif stock.is_active:
                flash(f'{ticker}: already active', 'warning')
            else:
                stock.is_active = True
                flash(f'{ticker}: reactivated', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')

    return redirect(url_for('universe.universe_list'))
