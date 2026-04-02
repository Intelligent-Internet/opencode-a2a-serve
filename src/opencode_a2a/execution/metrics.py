from __future__ import annotations

import logging

logger = logging.getLogger("opencode_a2a.execution.executor")


def emit_metric(
    name: str,
    value: float = 1.0,
    **labels: str | int | float | bool,
) -> None:
    if labels:
        labels_text = ",".join(
            f"{key}={str(label).lower() if isinstance(label, bool) else label}"
            for key, label in sorted(labels.items())
        )
        logger.debug("metric=%s value=%s labels=%s", name, value, labels_text)
        return
    logger.debug("metric=%s value=%s", name, value)
