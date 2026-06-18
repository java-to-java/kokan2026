import logging
import signal

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.pipeline import NewsPipeline

log = logging.getLogger(__name__)


class NewsScheduler:
    """Wraps APScheduler to run NewsPipeline on a configurable schedule."""

    def __init__(self, config: dict, pipeline: NewsPipeline):
        self.sched_cfg = config["scheduler"]
        self.pipeline = pipeline
        self._failures = 0
        tz = pytz.timezone(self.sched_cfg.get("timezone", "Asia/Kolkata"))
        self._scheduler = BlockingScheduler(timezone=tz)
        self._register_job(tz)

    # ------------------------------------------------------------------ public

    def start(self) -> None:
        if self.sched_cfg.get("run_on_start", True):
            log.info("Running pipeline immediately on start-up...")
            self._run()

        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

        log.info("Scheduler started. Press Ctrl+C to stop.")
        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            log.info("Scheduler shut down cleanly.")

    # ----------------------------------------------------------------- private

    def _register_job(self, tz) -> None:
        stype = self.sched_cfg.get("schedule_type", "interval")

        if stype == "cron":
            trigger = CronTrigger.from_crontab(
                self.sched_cfg.get("cron_expression", "0 */2 * * *"),
                timezone=tz,
            )
        else:
            trigger = IntervalTrigger(
                minutes=self.sched_cfg.get("interval_minutes", 120),
                timezone=tz,
            )

        self._scheduler.add_job(
            self._run, trigger, id="news_pipeline", max_instances=1
        )
        log.info(
            "Scheduler: type=%s  interval=%dmin  cron=%s",
            stype,
            self.sched_cfg.get("interval_minutes", 120),
            self.sched_cfg.get("cron_expression", ""),
        )

    def _run(self) -> None:
        max_fail = self.sched_cfg.get("max_consecutive_failures", 5)
        if self._failures >= max_fail:
            log.warning(
                "Skipping run: %d consecutive failures reached the limit of %d",
                self._failures, max_fail,
            )
            return
        try:
            self.pipeline.run()
            self._failures = 0
        except Exception as exc:
            self._failures += 1
            log.error(
                "Pipeline run raised an exception (failure #%d): %s",
                self._failures, exc,
            )

    def _handle_stop(self, signum, frame) -> None:
        log.info("Received signal %s — stopping scheduler...", signum)
        self._scheduler.shutdown(wait=False)
