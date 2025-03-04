from apscheduler.schedulers.background import BackgroundScheduler


def scheduled_get_changes(google_drive):
    changes = google_drive.get_changes()
    print(changes[len(changes)-1])
    print("SCHEDULED JOB: Changes fetched")

def check_changes(google_drive):
    scheduler = BackgroundScheduler()
    scheduler.add_job(scheduled_get_changes,google_drive, 'interval', seconds=15)
    scheduler.start()