"""
AI Dietician Page — Personalized Diet Plan Generator
======================================================
"""
import streamlit as st
from utils.ai_dietician import generate_diet_plan, get_recent_plans

st.set_page_config("AI Dietician", layout="wide")


def show():
    st.title("🥗 AI Dietician — Personalized Diet Plans")

    tab1, tab2 = st.tabs(["🍽️ Generate Plan", "📋 Recent Plans"])

    with tab1:
        st.subheader("Generate Diet Plan")
        st.caption("Condition-specific meal plans with calorie targets")

        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Patient Name*")
            age = st.number_input("Age", min_value=1, max_value=120, value=35)
        with col2:
            weight = st.number_input("Weight (kg)", min_value=20.0, max_value=250.0, value=70.0)
            height = st.number_input("Height (cm)", min_value=50.0, max_value=250.0, value=170.0)

        diagnosis = st.text_area("Diagnosis / Condition", placeholder="e.g. Type 2 Diabetes, Hypertension, Cardiac issue...",
                                 help="AI will auto-detect condition from this text")

        if st.button("🥗 Generate Diet Plan", type="primary"):
            if not name:
                st.error("Patient name is required.")
            else:
                result = generate_diet_plan(name, int(age), weight, height, diagnosis)
                plan = result.get("plan", {})

                st.success(f"✅ Diet plan generated for **{name}**")

                with st.container(border=True):
                    st.markdown(f"### 📋 {plan.get('plan_name','')}")
                    st.caption(plan.get('description', ''))
                    st.metric("🔥 Daily Calorie Target", f"{plan.get('daily_calories',0)} kcal")

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**✅ Recommended Foods**")
                        for item in plan.get("recommend", []):
                            st.markdown(f"- ✅ {item}")
                    with col_b:
                        st.markdown("**❌ Avoid / Limit**")
                        for item in plan.get("avoid", []):
                            st.markdown(f"- ❌ {item}")

                    st.divider()
                    for meal_time in ["breakfast", "lunch", "dinner", "snacks"]:
                        st.markdown(f"**{'☀️ Breakfast' if meal_time=='breakfast' else '🌤️ Lunch' if meal_time=='lunch' else '🌙 Dinner' if meal_time=='dinner' else '🥜 Snacks'}**")
                        for item in plan.get("meals", {}).get(meal_time, []):
                            st.markdown(f"- {item}")

    with tab2:
        st.subheader("Recently Generated Plans")
        plans = get_recent_plans()
        if not plans:
            st.info("No diet plans generated yet.")
        else:
            for p in plans:
                pd = p.get("plan_data", {})
                with st.expander(f"{pd.get('patient_name','')} — {pd.get('plan_name','')}"):
                    st.write(f"**Age:** {pd.get('age','')} | **Weight:** {pd.get('weight_kg','')}kg | **Height:** {pd.get('height_cm','')}cm")
                    st.write(f"**Condition:** {pd.get('condition','general')}")
                    st.write(f"**Calories:** {pd.get('daily_calories',0)} kcal/day")
                    if pd.get("meals"):
                        for mt, items in pd["meals"].items():
                            st.write(f"**{mt.title()}:** {', '.join(items)}")
