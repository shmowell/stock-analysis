"""
Quick verification script to check price data collection.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from sqlalchemy import select, func
from database import get_db_session
from database.models import Stock, PriceData

def verify_price_data():
    """Verify price data was collected correctly."""

    with get_db_session() as session:
        # Count total records
        total_records = session.query(func.count(PriceData.id)).scalar()
        print(f"Total price records: {total_records}")

        # Count records per stock
        print("\nRecords per stock:")
        print("-" * 50)

        stmt = (
            select(
                PriceData.ticker,
                func.count(PriceData.id).label('record_count'),
                func.min(PriceData.date).label('earliest_date'),
                func.max(PriceData.date).label('latest_date')
            )
            .group_by(PriceData.ticker)
            .order_by(PriceData.ticker)
        )

        result = session.execute(stmt)

        for row in result:
            ticker, count, earliest, latest = row
            date_range = (latest - earliest).days
            print(f"{ticker:6} | {count:3} records | {earliest} to {latest} ({date_range} days)")

        print("-" * 50)

        # Sample a few records
        print("\nSample records (first 3 for AAPL):")
        sample = session.query(PriceData).filter(
            PriceData.ticker == 'AAPL'
        ).order_by(PriceData.date).limit(3).all()

        for record in sample:
            print(f"  {record.date} | Close: ${record.close:.2f} | Volume: {record.volume:,}")

        print("\n✅ Price data verification complete!")

if __name__ == "__main__":
    verify_price_data()
