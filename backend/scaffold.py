"""Infrastructure scaffolds, declared, feature-flagged, deliberately not built.

These make the north-star architecture explicit and keep the gates honest: each
capability is one flag flip plus an implementation away. Calling any of them
today raises, so nothing silently pretends to work.
"""
from __future__ import annotations

from features import FEATURES


class AWSBatchCompute:
    """Scale-out target for large simulations. Today the same validated engine
    runs locally; this routes jobs to AWS Batch when enabled."""

    enabled = FEATURES.aws_batch_compute

    @staticmethod
    def submit(job: dict):
        raise NotImplementedError("AWS Batch compute is scaffolded (FEATURES.aws_batch_compute).")


class Auth:
    """Login / accounts. Out of scope for the free tier build."""

    enabled = FEATURES.auth

    @staticmethod
    def current_user(_token: str | None = None):
        raise NotImplementedError("Auth is scaffolded (FEATURES.auth).")


class LocalAgentSync:
    """The 'agent lives in the user's files' workflow (Continuous tier): watch
    local files, re-simulate on change, alert. Scaffolded."""

    enabled = FEATURES.local_agent

    @staticmethod
    def watch(_path: str):
        raise NotImplementedError("Local agent sync is scaffolded (FEATURES.local_agent).")


def scaffold_status() -> dict:
    return {
        "aws_batch_compute": AWSBatchCompute.enabled,
        "auth": Auth.enabled,
        "local_agent": LocalAgentSync.enabled,
        "template_authoring": FEATURES.template_authoring,
    }
