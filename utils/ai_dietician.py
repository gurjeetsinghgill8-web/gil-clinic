"""
AI Dietician Module — Personalized Diet Plan Generator
=========================================================
Rule-based meal plan generator with condition-specific suggestions.
"""
import uuid
import json
from datetime import datetime, date
from utils.db import DB_FILE
import sqlite3

# Condition-specific diet recommendations
DIET_PLANS = {
    "diabetes": {
        "name": "Diabetic Diet Plan",
        "description": "Low glycemic index, high fiber, controlled carbohydrates",
        "breakfast": ["Oatmeal with nuts", "Egg whites with whole wheat toast", "Sprouts salad"],
        "lunch": ["Grilled chicken with quinoa", "Mixed vegetable dal with brown rice", "Fish with steamed vegetables"],
        "dinner": ["Paneer with salad", "Light vegetable soup with tofu", "Grilled fish with spinach"],
        "snacks": ["Handful of almonds", "Greek yogurt", "Apple with peanut butter"],
        "avoid": ["Sugar", "White rice", "Deep fried foods", "Sugary drinks", "White bread"],
        "recommend": ["High fiber vegetables", "Lean proteins", "Whole grains", "Nuts and seeds"]
    },
    "hypertension": {
        "name": "Heart-Healthy / Low Sodium Diet",
        "description": "Low sodium, high potassium, DASH diet principles",
        "breakfast": ["Oatmeal with berries", "Banana smoothie (no salt)", "Whole grain cereal with low-fat milk"],
        "lunch": ["Brown rice with dal (low salt)", "Grilled fish with salad", "Quinoa with roasted vegetables"],
        "dinner": ["Vegetable soup", "Grilled chicken with steamed broccoli", "Dal with whole wheat roti"],
        "snacks": ["Fresh fruit", "Yogurt", "Roasted chana"],
        "avoid": ["Salt", "Pickles", "Canned foods", "Processed meat", "Alcohol"],
        "recommend": ["Leafy greens", "Bananas", "Potatoes", "Low-fat dairy", "Garlic"]
    },
    "heart_disease": {
        "name": "Cardiac Diet Plan",
        "description": "Low saturated fat, low cholesterol, heart-healthy fats",
        "breakfast": ["Oatmeal with flaxseeds", "Smoothie with berries and spinach", "Egg white omelette"],
        "lunch": ["Grilled salmon with brown rice", "Lentil soup with salad", "Steamed vegetables with tofu"],
        "dinner": ["Light dal with vegetables", "Baked fish with asparagus", "Vegetable khichdi"],
        "snacks": ["Walnuts", "Dark chocolate (70%+)", "Fresh fruit"],
        "avoid": ["Butter", "Red meat", "Fried foods", "Full-fat dairy", "Egg yolk excess"],
        "recommend": ["Omega-3 rich foods", "Fiber-rich vegetables", "Whole grains", "Olive oil"]
    },
    "general": {
        "name": "Balanced Diet Plan",
        "description": "Well-balanced nutrition for general health maintenance",
        "breakfast": ["Vegetable poha", "Idli with sambar", "Multigrain toast with eggs"],
        "lunch": ["Dal rice with vegetables", "Chapati with paneer curry", "Mixed vegetable biryani"],
        "dinner": ["Roti with dal", "Vegetable pulao with raita", "Soup with grilled sandwich"],
        "snacks": ["Mixed nuts", "Fresh seasonal fruit", "Buttermilk"],
        "avoid": ["Excessive oil", "Junk food", "Sugary beverages"],
        "recommend": ["Seasonal vegetables", "Fresh fruits", "Whole grains", "Adequate water"]
    }
}

CONDITION_MAP = {
    "diabetes": "diabetes", "diabetic": "diabetes", "sugar": "diabetes",
    "high bp": "hypertension", "hypertension": "hypertension", "blood pressure": "hypertension",
    "heart": "heart_disease", "cardiac": "heart_disease", "cardio": "heart_disease",
    "cholesterol": "heart_disease",
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_diet_plans (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                age INTEGER, weight REAL, height REAL, condition TEXT,
                plan_data TEXT NOT NULL, created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def detect_condition(diagnosis: str) -> str:
    """Detect condition from diagnosis text."""
    if not diagnosis:
        return "general"
    d = diagnosis.lower()
    for keyword, condition in CONDITION_MAP.items():
        if keyword in d:
            return condition
    return "general"


def generate_diet_plan(patient_name: str, age: int, weight: float, height: float,
                       diagnosis: str = "", patient_id: str = "") -> dict:
    condition = detect_condition(diagnosis)
    plan_template = DIET_PLANS.get(condition, DIET_PLANS["general"])

    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5  # Simplified for male
    daily_calories = int(bmr * 1.55)  # Moderate activity

    plan = {
        "patient_name": patient_name,
        "age": age,
        "weight_kg": weight,
        "height_cm": height,
        "condition": condition,
        "plan_name": plan_template["name"],
        "description": plan_template["description"],
        "daily_calories": daily_calories,
        "meals": {
            "breakfast": plan_template["breakfast"],
            "lunch": plan_template["lunch"],
            "dinner": plan_template["dinner"],
            "snacks": plan_template["snacks"],
        },
        "avoid": plan_template["avoid"],
        "recommend": plan_template["recommend"],
    }

    plan_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ai_diet_plans (id, patient_id, patient_name, age, weight, height, condition, plan_data, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (plan_id, patient_id, patient_name, age, weight, height, condition,
             json.dumps(plan), datetime.now().isoformat())
        )
        conn.commit()
        return {"success": True, "plan": plan, "plan_id": plan_id}
    except Exception as e:
        return {"success": False, "message": str(e), "plan": plan}
    finally:
        conn.close()


def get_recent_plans(limit: int = 10) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ai_diet_plans ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        plans = []
        for row in rows:
            d = dict(zip(columns, row))
            d["plan_data"] = json.loads(d.get("plan_data", "{}"))
            plans.append(d)
        return plans
    except Exception:
        return []
    finally:
        conn.close()
