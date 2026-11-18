import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.inactivity_reminders import send_inactivity_reminders

scheduler = None


def start_inactivity_scheduler(app):
    global scheduler

    if not app.config.get('INACTIVITY_EMAILS_ENABLED'):
        app.logger.info('Inactive-user email scheduler is disabled.')
        return None

    if scheduler and scheduler.running:
        return scheduler

    scheduler = BackgroundScheduler(timezone='UTC')

    def run_job():
        with app.app_context():
            result = send_inactivity_reminders()
            app.logger.info(
                'Inactive-user reminder job finished: sent=%s failed=%s skipped=%s candidates=%s',
                result['sent'],
                result['failed'],
                result['skipped'],
                result['candidates']
            )

    scheduler.add_job(
        run_job,
        CronTrigger(hour=app.config['INACTIVITY_EMAIL_HOUR_UTC'], minute=0),
        id='inactive_user_email_reminders',
        replace_existing=True
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)
    return scheduler


inbox_scheduler = None


def start_inbox_poller(app):
    """Checks the purchase inbox mailbox every 2 minutes while the server is awake."""
    global inbox_scheduler

    if app.config.get('TESTING') or not (app.config.get('INBOX_EMAIL') and app.config.get('INBOX_IMAP_PASSWORD')):
        return None
    if inbox_scheduler and inbox_scheduler.running:
        return inbox_scheduler

    from apscheduler.triggers.interval import IntervalTrigger
    from app.purchase_inbox import poll_inbox

    def run_job():
        with app.app_context():
            poll_inbox(force=True)

    inbox_scheduler = BackgroundScheduler(timezone='UTC')
    inbox_scheduler.add_job(run_job, IntervalTrigger(minutes=2), id='purchase_inbox_poll', replace_existing=True)
    inbox_scheduler.start()
    atexit.register(lambda: inbox_scheduler.shutdown(wait=False) if inbox_scheduler.running else None)
    return inbox_scheduler
