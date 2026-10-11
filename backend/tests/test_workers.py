from app.workers.celery_app import QUEUES, celery_app, ping


def test_all_pipeline_queues_are_declared() -> None:
    declared = {queue.name for queue in celery_app.conf.task_queues}

    assert declared == set(QUEUES)
    assert celery_app.conf.task_default_queue in declared


def test_ping_runs_locally() -> None:
    assert ping.apply().get() == "pong"
