"""
Verify fundamental data collection and display summary.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from database import get_db_session
from database.models import FundamentalData
from sqlalchemy import select, func

def main():
    with get_db_session() as session:
        # Get total count
        count = session.execute(
            select(func.count()).select_from(FundamentalData)
        ).scalar()
        print(f"Total fundamental data records: {count}\n")

        # Get sample data
        stmt = select(
            FundamentalData.ticker,
            FundamentalData.pe_ratio,
            FundamentalData.roe,
            FundamentalData.revenue_growth_yoy,
            FundamentalData.beta
        ).order_by(FundamentalData.ticker)

        results = session.execute(stmt).all()

        print("Sample fundamental data:")
        print(f"{'Ticker':<8} {'P/E':>8} {'ROE':>8} {'Rev Grow':>10} {'Beta':>8}")
        print("-" * 50)

        for row in results:
            ticker, pe, roe, rev_growth, beta = row
            print(
                f"{ticker:<8} "
                f"{f'{pe:.2f}' if pe else 'N/A':>8} "
                f"{f'{roe:.4f}' if roe else 'N/A':>8} "
                f"{f'{rev_growth:.4f}' if rev_growth else 'N/A':>10} "
                f"{f'{beta:.4f}' if beta else 'N/A':>8}"
            )

        print("\n✓ Fundamental data verification complete!")

if __name__ == '__main__':
    main()
