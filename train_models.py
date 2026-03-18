"""Utility script to warm the adaptive prediction models."""

from core.ml import get_prediction_models

if __name__ == "__main__":
    models = get_prediction_models(force_retrain=True)
    if not models:
        print("?? Failed to train models")
    else:
        free_meta = models.get("free", {})
        premium_meta = models.get("premium", {})
        print("? Adaptive models ready")
        print(
            f"  Free  ? features={len(free_meta.get('features', []))}, rmse={free_meta.get('rmse', 0):.3f}"
        )
        print(
            f"  Premium ? features={len(premium_meta.get('features', []))}, rmse={premium_meta.get('rmse', 0):.3f}"
        )
