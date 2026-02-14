"""Quick data verification script."""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import Stock

with get_db_session() as session:
    stocks = session.query(Stock).all()
    print(f'\nTotal stocks in database: {len(stocks)}')
    print(f'Active stocks: {sum(1 for s in stocks if s.is_active)}')

    sectors = set(s.sector for s in stocks if s.sector)
    print(f'Unique sectors: {len(sectors)}')

    # Check data completeness
    with_market_cap = sum(1 for s in stocks if s.market_cap)
    with_sector = sum(1 for s in stocks if s.sector)

    print(f'\nData Completeness:')
    print(f'  Market Cap: {with_market_cap}/{len(stocks)} ({with_market_cap/len(stocks)*100:.1f}%)')
    print(f'  Sector: {with_sector}/{len(stocks)} ({with_sector/len(stocks)*100:.1f}%)')
    print(f'\nData quality verification complete!')
