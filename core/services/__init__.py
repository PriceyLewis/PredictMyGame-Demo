"""
Service layer helpers for external integrations.
"""

from .openai_client import get_openai_client, OpenAIClient  # noqa: F401
from .insights import (  # noqa: F401
    collect_performance_metrics,
    generate_insights_for_user,
    capture_prediction_snapshot,
)
