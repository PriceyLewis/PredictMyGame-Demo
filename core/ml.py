from datetime import timedelta
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple

import numpy as np
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg
from django.utils import timezone

from .models import Module, PredictionSnapshot, UpcomingDeadline, PlannedModule, StudyPlan

FREE_FEATURES = [
    "avg_so_far",
    "credits_done",
    "module_count",
    "trend",
    "grade_std",
    "credits_remaining_ratio",
    "avg_vs_actual",
]

PREMIUM_FEATURES = [
    "avg_so_far",
    "credits_done",
    "module_count",
    "trend",
    "grade_std",
    "weighted_variance",
    "grade_min",
    "grade_max",
    "grade_range",
    "credits_remaining_ratio",
    "snapshot_frequency",
    "plan_density",
    "deadline_load",
    "raw_deadline_count",
    "avg_vs_actual",
    "difficulty_index",
    "performance_variance",
    "engagement_manual",
]

CACHE_KEY = "core:prediction_models_v2"
MAX_TRAINING_ROWS = 6000
DEFAULT_TOTAL_CREDITS = 120


def _weighted_average(modules: Iterable[Module]) -> float:
    total_score = 0.0
    total_weight = 0.0
    for m in modules:
        if m.grade_percent is None:
            continue
        weight = m.credits or 0
        total_score += (m.grade_percent or 0) * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return total_score / total_weight


def _build_user_context(user) -> Dict[str, float]:
    today = timezone.now().date()
    snapshots_30 = PredictionSnapshot.objects.filter(
        user=user, created_at__date__gte=today - timedelta(days=30)
    ).count()
    study_slots_7 = StudyPlan.objects.filter(
        user=user, date__range=[today, today + timedelta(days=6)]
    ).count()
    deadlines = list(UpcomingDeadline.objects.filter(user=user, completed=False))
    deadlines_14 = sum(
        1
        for d in deadlines
        if d.due_date and 0 <= (d.due_date - today).days <= 14
    )
    completed_credits = sum(
        m.credits or 0
        for m in Module.objects.filter(user=user, level="UNI", grade_percent__isnull=False)
    )
    planned_credits = sum(pm.credits or 0 for pm in PlannedModule.objects.filter(user=user))
    credit_goal = max(DEFAULT_TOTAL_CREDITS, completed_credits + planned_credits)
    return {
        "snapshots_30": snapshots_30,
        "study_slots_7": study_slots_7,
        "deadline_all": deadlines,
        "deadline_14": deadlines_14,
        "credit_goal": credit_goal,
    }


def compute_feature_dict(
    user,
    modules_subset: Iterable[Module],
    avg_input: float,
    credits_input: float,
    context: Dict[str, float],
    extra: Dict[str, float] = None,
) -> Dict[str, float]:
    modules_subset = [m for m in modules_subset if m.grade_percent is not None]
    grades = [m.grade_percent for m in modules_subset]
    credits_list = [m.credits or 0 for m in modules_subset]
    module_count = len(grades)

    avg_actual = _weighted_average(modules_subset)
    avg_so_far = avg_input if avg_input else avg_actual
    credits_done = credits_input if credits_input else sum(credits_list)

    grade_std = float(np.std(grades)) if len(grades) > 1 else 0.0
    grade_min = min(grades) if grades else 0.0
    grade_max = max(grades) if grades else 0.0
    grade_range = grade_max - grade_min

    if len(grades) > 1 and sum(credits_list) > 0:
        mean = avg_actual
        weighted_variance = sum(
            weight * ((grade - mean) ** 2)
            for grade, weight in zip(grades, credits_list)
        ) / sum(credits_list)
    else:
        weighted_variance = 0.0

    trend = 0.0
    if len(grades) >= 3:
        y = np.array(grades[-5:])
        x = np.arange(len(y))
        slope, _ = np.polyfit(x, y, 1)
        trend = float(slope)
    elif len(grades) >= 2:
        trend = grades[-1] - grades[-2]

    credit_goal = context.get("credit_goal") or DEFAULT_TOTAL_CREDITS
    credits_remaining = max(0.0, credit_goal - credits_done)
    credits_remaining_ratio = credits_remaining / credit_goal if credit_goal else 0.0

    snapshot_frequency = context.get("snapshots_30", 0) / 30.0
    plan_density = context.get("study_slots_7", 0) / 7.0
    deadline_count = len(context.get("deadline_all", []))
    deadline_load = (
        context.get("deadline_14", 0) / deadline_count if deadline_count else 0.0
    )

    extra = extra or {}

    return {
        "avg_so_far": avg_so_far,
        "avg_actual": avg_actual,
        "avg_vs_actual": avg_so_far - avg_actual,
        "credits_done": credits_done,
        "module_count": float(module_count),
        "grade_std": grade_std,
        "grade_min": grade_min,
        "grade_max": grade_max,
        "grade_range": grade_range,
        "weighted_variance": float(weighted_variance),
        "trend": trend,
        "credits_remaining_ratio": credits_remaining_ratio,
        "credits_remaining": credits_remaining,
        "snapshot_frequency": snapshot_frequency,
        "plan_density": plan_density,
        "deadline_load": deadline_load,
        "raw_deadline_count": float(deadline_count),
        "difficulty_index": float(extra.get("difficulty_index", 0.0)),
        "performance_variance": float(extra.get("performance_variance", 0.0)),
        "engagement_manual": float(extra.get("engagement_score", 0.0)),
    }


def _ridge_fit(X: np.ndarray, y: np.ndarray, alpha: float = 5.0) -> Tuple[np.ndarray, float]:
    if X.size == 0:
        raise ValueError("Empty feature matrix")
    X_aug = np.hstack([X, np.ones((X.shape[0], 1))])
    reg = alpha * np.eye(X_aug.shape[1])
    reg[-1, -1] = 0.0  # do not regularise intercept
    beta = np.linalg.solve(X_aug.T @ X_aug + reg, X_aug.T @ y)
    preds = X_aug @ beta
    rmse = float(np.sqrt(np.mean((preds - y) ** 2)))
    return beta, rmse


def _build_training_rows() -> Tuple[List[Dict[str, float]], List[float]]:
    feature_rows: List[Dict[str, float]] = []
    targets: List[float] = []

    User = get_user_model()
    users = User.objects.all().iterator()

    for user in users:
        modules = list(
            Module.objects.filter(
                user=user, level="UNI", grade_percent__isnull=False
            ).order_by("created_at")
        )
        if len(modules) < 3:
            continue
        final_avg = _weighted_average(modules)
        if not final_avg:
            continue
        context = _build_user_context(user)
        running = []
        accumulated_credits = 0.0
        for module in modules:
            running.append(module)
            if module.grade_percent is None:
                continue
            accumulated_credits += module.credits or 0
            if len(running) < 2:
                continue
            avg_so_far = _weighted_average(running)
            features = compute_feature_dict(
                user=user,
                modules_subset=running,
                avg_input=avg_so_far,
                credits_input=accumulated_credits,
                context=context,
                extra={},
            )
            feature_rows.append(features)
            targets.append(final_avg)

    if len(feature_rows) > MAX_TRAINING_ROWS:
        idx = np.random.choice(len(feature_rows), MAX_TRAINING_ROWS, replace=False)
        feature_rows = [feature_rows[i] for i in idx]
        targets = [targets[i] for i in idx]

    return feature_rows, targets


def _train_models() -> Dict[str, Dict]:
    rows, targets = _build_training_rows()
    if not rows:
        return {}

    models = {}

    def train_for(feature_names: List[str], label: str) -> Dict:
        X = np.array([[row.get(name, 0.0) for name in feature_names] for row in rows], dtype=float)
        y = np.array(targets, dtype=float)
        try:
            beta, rmse = _ridge_fit(X, y, alpha=4.0 if label == "premium" else 6.0)
        except np.linalg.LinAlgError:
            beta, rmse = _ridge_fit(X, y, alpha=12.0)
        return {
            "features": feature_names,
            "coef": beta[:-1].tolist(),
            "intercept": float(beta[-1]),
            "rmse": rmse,
            "n_samples": int(len(y)),
            "model_label": "Premium Ridge v2" if label == "premium" else "Free Ridge v2",
            "version": 2,
        }

    models["free"] = train_for(FREE_FEATURES, "free")
    models["premium"] = train_for(PREMIUM_FEATURES, "premium")
    return models


@lru_cache
def get_prediction_models(force_retrain: bool = False) -> Dict[str, Dict]:
    if force_retrain:
        get_prediction_models.cache_clear()
    cached = cache.get(CACHE_KEY)
    if cached and not force_retrain:
        return cached
    models = _train_models()
    if models:
        cache.set(CACHE_KEY, models, 60 * 60)  # 1 hour
    return models


def _confidence_from_model(pred: float, features: Dict[str, float], model_meta: Dict[str, Dict]) -> float:
    rmse = model_meta.get("rmse") or 8.0
    baseline = 97.0 - rmse * 1.5
    baseline -= abs(pred - features.get("avg_so_far", pred)) * 0.35
    baseline -= features.get("deadline_load", 0.0) * 18.0
    baseline += min(8.0, features.get("snapshot_frequency", 0.0) * 18.0)
    baseline += min(5.0, features.get("plan_density", 0.0) * 6.0)
    baseline = max(35.0, min(97.0, baseline))
    return baseline


def predict_average(user, avg_so_far: float, credits_done: float, premium: bool = False, extra: Dict[str, float] = None):
    models = get_prediction_models()
    key = "premium" if premium else "free"
    model_meta = models.get(key)
    modules = list(
        Module.objects.filter(user=user, level="UNI", grade_percent__isnull=False).order_by("created_at")
    )
    context = _build_user_context(user)
    features = compute_feature_dict(
        user=user,
        modules_subset=modules,
        avg_input=avg_so_far,
        credits_input=credits_done,
        context=context,
        extra=extra or {},
    )

    if not model_meta:
        prediction = avg_so_far or features.get("avg_actual", 0.0)
        confidence = 55.0
        meta = {"model_label": "Heuristic fallback", "features_used": list(features.keys())}
        return prediction, confidence, meta, features

    feature_vector = np.array([features.get(name, 0.0) for name in model_meta["features"]], dtype=float)
    coef = np.array(model_meta["coef"], dtype=float)
    intercept = model_meta["intercept"]
    prediction = float(feature_vector @ coef + intercept)
    prediction = max(0.0, min(100.0, prediction))
    confidence = _confidence_from_model(prediction, features, model_meta)
    meta = {
        "model_label": model_meta.get("model_label"),
        "features_used": model_meta["features"],
        "rmse": model_meta.get("rmse"),
        "n_samples": model_meta.get("n_samples"),
        "version": model_meta.get("version", 2),
    }
    return prediction, confidence, meta, features
