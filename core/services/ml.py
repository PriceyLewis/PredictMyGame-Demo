# This is a simple, deterministic stub you can swap for a real model.
# It maps average score → predicted grade + subject breakdowns.
from statistics import mean

def score_to_grade(level: str, score: float) -> str:
    # Adjustable boundaries per level if you like
    if level == "gcse":
        # 9–1 style rough mapping
        if score >= 85: return "9"
        if score >= 78: return "8"
        if score >= 70: return "7"
        if score >= 60: return "6"
        if score >= 50: return "5"
        if score >= 40: return "4"
        if score >= 30: return "3"
        if score >= 20: return "2"
        return "1"
    elif level == "college":
        # UCAS-oriented (but we’ll return letter-like)
        if score >= 85: return "A*"
        if score >= 75: return "A"
        if score >= 65: return "B"
        if score >= 55: return "C"
        if score >= 45: return "D"
        return "E"
    else:
        # university bands
        if score >= 70: return "First"
        if score >= 60: return "2:1"
        if score >= 50: return "2:2"
        if score >= 40: return "Third"
        return "Fail"

def predict(level: str, subjects: list[dict]) -> dict:
    """
    subjects: [{ "name": "Maths", "score": 72 }, ...]
    Returns:
      {
        "predicted_score": float,
        "predicted_grade": str,
        "confidence": float,
        "subjects": [{"name":..., "predicted_score":..., "predicted_grade":...}, ...]
      }
    """
    if not subjects:
        return {
            "predicted_score": 0.0,
            "predicted_grade": score_to_grade(level, 0.0),
            "confidence": 0.5,
            "subjects": [],
        }

    avg = mean([s.get("score", 0) for s in subjects])
    overall_grade = score_to_grade(level, avg)

    subject_rows = []
    for s in subjects:
        sc = float(s.get("score", 0))
        subject_rows.append({
            "name": s.get("name") or "Subject",
            "predicted_score": sc,
            "predicted_grade": score_to_grade(level, sc),
        })

    return {
        "predicted_score": round(avg, 2),
        "predicted_grade": overall_grade,
        "confidence": 0.78,  # static for now; replace with model prob
        "subjects": subject_rows,
    }
