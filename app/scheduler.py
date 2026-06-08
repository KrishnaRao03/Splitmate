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
