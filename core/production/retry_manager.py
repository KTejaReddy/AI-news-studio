"""RetryManager for the AI Production Orchestrator.

Handles configurable retry logic for failed pipeline stages, including
exponential back-off and per-stage retry budgets.
"""

import time
import logging
from typing import Callable, Optional, TypeVar

from core.production.production_state import PipelineStage

T = TypeVar("T")


class RetryManager:
    """Executes a callable with automatic retry logic on failure.

    Supports exponential back-off, configurable max attempts, and per-stage
    retry budgets. Stage failures are logged at each attempt.
    """

    def __init__(
        self,
        max_retries: int = 2,
        base_delay: float = 2.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
    ) -> None:
        """Initialize RetryManager.

        Args:
            max_retries: Maximum number of retry attempts after the initial failure.
            base_delay: Initial delay in seconds before the first retry.
            backoff_factor: Multiplier applied to delay on each consecutive attempt.
            max_delay: Maximum delay cap in seconds.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self._logger = logging.getLogger(self.__class__.__name__)

    def execute(
        self,
        fn: Callable[[], T],
        stage: PipelineStage,
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> T:
        """Execute ``fn`` with retry on exception.

        Args:
            fn: Callable that executes the stage logic and returns a result.
            stage: The pipeline stage being executed (for logging context).
            cancellation_check: Optional callable returning True if the job has
                been requested to cancel. Retry loop will abort immediately.

        Returns:
            The return value of ``fn`` on success.

        Raises:
            Exception: Re-raises the last exception if all retries are exhausted.
        """
        stage_label = stage.value
        last_exc: Optional[Exception] = None
        delay = self.base_delay

        for attempt in range(self.max_retries + 1):
            # Check cancellation before each attempt
            if cancellation_check and cancellation_check():
                raise RuntimeError(f"Stage '{stage_label}' cancelled before attempt {attempt + 1}.")

            try:
                if attempt > 0:
                    self._logger.warning(
                        f"[{stage_label}] Retry attempt {attempt}/{self.max_retries} "
                        f"after {delay:.1f}s delay..."
                    )
                result = fn()
                if attempt > 0:
                    self._logger.info(f"[{stage_label}] Succeeded on retry attempt {attempt}.")
                return result

            except Exception as exc:
                last_exc = exc
                self._logger.error(
                    f"[{stage_label}] Attempt {attempt + 1} failed: {exc}"
                )

                if attempt < self.max_retries:
                    # Check cancellation during wait
                    if cancellation_check and cancellation_check():
                        raise RuntimeError(f"Stage '{stage_label}' cancelled during retry wait.")
                    time.sleep(min(delay, self.max_delay))
                    delay *= self.backoff_factor

        self._logger.error(
            f"[{stage_label}] All {self.max_retries + 1} attempts exhausted."
        )
        raise last_exc  # type: ignore[misc]
