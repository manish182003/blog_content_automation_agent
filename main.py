import sys
import io
import argparse
import logging
import time
from apscheduler.schedulers.blocking import BlockingScheduler

import config
from orchestrator import BlogOrchestratorDAG
from logger_metrics import MetricsLogger

# Ensure stdout handles UTF-8 characters cleanly on Windows
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.BASE_DIR / "app.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

def run_job(dry_run: bool):
    """Callback wrapper for scheduler and immediate CLI execution."""
    try:
        dag = BlogOrchestratorDAG(dry_run=dry_run)
        dag.run_pipeline()
    except Exception as e:
        logger.error(f"Scheduled job execution failed: {e}", exc_info=True)

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Lightweight HTTP Handler for Render Free Web Service health checks and manual triggers."""
    dry_run_mode = False

    def do_GET(self):
        if self.path == "/trigger":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "triggered", "message": "Executing immediate blog automation run..."}')
            threading.Thread(target=run_job, args=(HealthCheckHandler.dry_run_mode,), daemon=True).start()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "daily-blog-automation"}')

    def log_message(self, format, *args):
        pass

def start_health_server(port: int):
    """Start HTTP server for Render free web service health checks."""
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Health check HTTP server listening on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.warning(f"Health check server error: {e}")

def start_daily_scheduler(dry_run: bool, hour: int, minute: int):
    """Start APScheduler and optional health check web server for Render Free Web Service."""
    HealthCheckHandler.dry_run_mode = dry_run

    # If running on Render (PORT env set), start HTTP health server in background thread
    port_env = os.getenv("PORT")
    if port_env:
        try:
            port = int(port_env)
            t = threading.Thread(target=start_health_server, args=(port,), daemon=True)
            t.start()
            logger.info(f"Started Render Free Web Service health server thread on port {port}.")
        except ValueError:
            pass

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_job,
        trigger="cron",
        hour=hour,
        minute=minute,
        args=[dry_run],
        id="daily_blog_job",
        name="Daily Autonomous Tech Blog Generator"
    )
    
    logger.info(f"Scheduler started! Configured to run daily at {hour:02d}:{minute:02d} UTC/Local (Mode: {'DRY_RUN' if dry_run else 'LIVE'}).")
    logger.info("Press Ctrl+C to exit.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped cleanly.")

def print_metrics():
    """Print reliability metrics summary from SQLite run_logs database."""
    metrics_logger = MetricsLogger()
    summary = metrics_logger.get_reliability_summary()
    print("\n=== BLOG AUTOMATION RELIABILITY METRICS ===")
    print(f"Total Runs Recorded: {summary['total_runs']}")
    print(f"Success Rate: {summary['success_rate']:.1f}%")
    print(f"Status Counts: {summary['status_counts']}")
    print(f"Average Duration: {summary['avg_duration_sec']}s")
    print(f"Average SEO Score: {summary['avg_seo_score']}/100")
    print(f"Average Groundedness Score: {summary['avg_groundedness_score']}/100")
    print(f"Average Rewrite Attempts: {summary['avg_rewrite_attempts']}")
    print("===========================================\n")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Daily Tech Blog Generator (AI & Mobile App Dev)")
    parser.add_argument("--dry-run", action="store_true", default=config.DRY_RUN_DEFAULT, help="Run without publishing to live Notion (default: True)")
    parser.add_argument("--live", action="store_true", help="Enable live Notion database publishing (disables dry-run)")
    parser.add_argument("--run-now", action="store_true", help="Execute the pipeline immediately once")
    parser.add_argument("--schedule", action="store_true", help="Start daily scheduler daemon")
    parser.add_argument("--metrics", action="store_true", help="Display historical reliability metrics report")

    args = parser.parse_args()

    # Determine dry-run mode
    dry_run_mode = not args.live if args.live else args.dry_run

    if args.metrics:
        print_metrics()
        return

    if args.run_now or not args.schedule:
        logger.info(f"Executing immediate run (Mode: {'DRY_RUN' if dry_run_mode else 'LIVE'})...")
        run_job(dry_run=dry_run_mode)

    if args.schedule:
        start_daily_scheduler(
            dry_run=dry_run_mode,
            hour=config.RUN_HOUR,
            minute=config.RUN_MINUTE
        )

if __name__ == "__main__":
    main()
