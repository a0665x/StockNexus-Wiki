#!/usr/bin/env python3
"""Export downloaded daily prices as CSV without network access or DB writes."""
import argparse
import csv
import datetime as dt
import os
from pathlib import Path
import sqlite3
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker', help='Exact downloaded symbol, e.g. NVDA')
    parser.add_argument('--start', type=dt.date.fromisoformat, default=dt.date.min)
    parser.add_argument('--end', type=dt.date.fromisoformat, default=dt.date.max,
                        help='Inclusive end date')
    parser.add_argument('--db', type=Path, default=Path(os.environ.get(
        'NEWS_ATLAS_DB', Path(__file__).resolve().parents[1] / 'data/news-atlas.sqlite3')))
    args = parser.parse_args()
    if args.start > args.end:
        parser.error('start must be on or before end')
    if not args.db.exists():
        graph=args.db.parent/'graph'
        candidates=[graph/args.ticker.upper()/'news-atlas.sqlite3',graph/'_unassigned'/'news-atlas.sqlite3']
        for candidate in candidates:
            if candidate.exists():
                with sqlite3.connect(candidate.resolve().as_uri()+'?mode=ro',uri=True) as probe:
                    if probe.execute("SELECT 1 FROM sqlite_master WHERE name='daily_prices'").fetchone():
                        args.db=candidate;break
    try:
        db = sqlite3.connect(args.db.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            cursor = db.execute('''SELECT ticker,day,open,high,low,close,adjusted_close,
                volume,currency,exchange,provider,fetched_at FROM daily_prices
                WHERE ticker=? AND day>=? AND day<=? ORDER BY day,provider''',
                (args.ticker.upper(), args.start.isoformat(), args.end.isoformat()))
            rows = cursor.fetchall()
            if not rows:
                parser.exit(1, 'No downloaded prices for this symbol/date range. No API was called.\n')
            writer = csv.writer(sys.stdout)
            writer.writerow([column[0] for column in cursor.description])
            writer.writerows(rows)
        finally:
            db.close()
    except sqlite3.Error as exc:
        parser.exit(1, f'Cannot read downloaded prices: {exc}\n')


if __name__ == '__main__':
    main()
