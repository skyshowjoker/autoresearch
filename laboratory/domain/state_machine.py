from __future__ import annotations

from dataclasses import replace

from .models import Experiment, ExperimentStatus


class InvalidTransition(ValueError):
    pass


ALLOWED = {
    ExperimentStatus.QUEUED: {ExperimentStatus.RUNNING, ExperimentStatus.CANCELLED},
    ExperimentStatus.RUNNING: {
        ExperimentStatus.SUCCESS, ExperimentStatus.INVALID, ExperimentStatus.CRASH,
        ExperimentStatus.TIMEOUT, ExperimentStatus.CANCELLED,
    },
    ExperimentStatus.SUCCESS: set(),
    ExperimentStatus.INVALID: set(),
    ExperimentStatus.CRASH: set(),
    ExperimentStatus.TIMEOUT: set(),
    ExperimentStatus.CANCELLED: set(),
}


def transition(experiment: Experiment, target: ExperimentStatus, **changes) -> Experiment:
    target = ExperimentStatus(target)
    if target not in ALLOWED[ExperimentStatus(experiment.status)]:
        raise InvalidTransition(f"{experiment.status} -> {target.value} is not allowed")
    return replace(experiment, status=target, **changes)
