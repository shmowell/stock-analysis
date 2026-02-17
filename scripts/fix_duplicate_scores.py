"""
One-time migration: Remove duplicate StockScore rows and add unique constraint.

Run: python scripts/fix_duplicate_scores.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import get_db_session
from sqlalchemy import text


def main():
    with get_db_session() as session:
        # Step 1: Find and remove duplicates, keeping the latest id per (ticker, calculation_date)
        dupes = session.execute(text("""
            DELETE FROM stock_scores
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM stock_scores
                GROUP BY ticker, calculation_date
            )
        """))
        print(f"Removed {dupes.rowcount} duplicate score rows")

        # Step 2: Add unique constraint (ignore if already exists)
        try:
            session.execute(text("""
                ALTER TABLE stock_scores
                ADD CONSTRAINT uq_stock_score_ticker_date
                UNIQUE (ticker, calculation_date)
            """))
            print("Added unique constraint uq_stock_score_ticker_date")
        except Exception as e:
            if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                print("Unique constraint already exists, skipping")
                session.rollback()
            else:
                raise

        session.commit()
        print("Done!")


if __name__ == '__main__':
    main()
