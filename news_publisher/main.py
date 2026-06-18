#!/usr/bin/env python3
"""
News Marathi Social Publisher

Usage:
    python main.py                     # run on scheduler
    python main.py --run-once          # fetch, translate and publish once then exit
    python main.py --dry-run           # fetch and translate but do NOT publish
    python main.py --config alt.json   # use a different config file
"""

import sys
import argparse
import logging

from src.config_loader import load_config
from src.logger import setup_logging
from src.pipeline import NewsPipeline
from src.scheduler import NewsScheduler


def parse_args():
    p = argparse.ArgumentParser(
        description="Fetch news, translate to Marathi, publish to WhatsApp and Facebook."
    )
    p.add_argument("--config", default="config.json", help="Path to JSON config file (default: config.json)")
    p.add_argument("--run-once", action="store_true", help="Execute one pipeline run and exit")
    p.add_argument("--dry-run", action="store_true", help="Fetch and translate but skip publishing")
    return p.parse_args()


def main():
    args = parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] Config problem: {exc}", file=sys.stderr)
        sys.exit(1)

    setup_logging(config["logging"])
    log = logging.getLogger(__name__)
    log.info("News Marathi Social Publisher starting...")

    pipeline = NewsPipeline(config, dry_run=args.dry_run)

    if args.run_once or not config["scheduler"]["enabled"]:
        pipeline.run()
    else:
        scheduler = NewsScheduler(config, pipeline)
        scheduler.start()


if __name__ == "__main__":
    main()
