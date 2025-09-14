import streamlit as st
import requests

# Keys (replace with your own)
USDA_KEY = "HvgXfQKOj8xIz3vubw8K87mOrankyf22ld4dHnAS"
NUTRITIONIX_APP_ID = "5107911f"
NUTRITIONIX_APP_KEY = "39b7b779dbafa5fe4ae28af495a3c349"

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
NUTRITIONIX_URL = "https://trackapi.nutritionix.com/v2/natural/nutrients"


# ---------------- Utility Functions ---------------- #

def clean_unit_name(unit: str) -> str | None:
    """Normalize and filter Nutritionix unit names with universal rules."""
    unit = unit.lower().strip()
    if len(unit) > 20 or "(" in unit or ")" in unit or ":" in unit:
        return None
    if len(unit) < 2:
        return None
    if not any(c.isalpha() for c in unit):
        return None
    if not any(v in unit for v in "aeiou"):
        return None
    if unit.endswith("s") and not unit.endswith("ss"):
        unit = unit[:-1]
    synonyms = {
        "tablespoon": "tbsp",
        "teaspoon": "tsp",
        "ounce": "oz",
        "gram": "g"
    }
    unit = synonyms.get(unit, unit)
    return unit


def search_usda(food_name, max_results=20):
    params = {"query": food_name, "pageSize": max_results * 2, "api_key": USDA_KEY}
    r = requests.get(USDA_SEARCH_URL, params=params)
    data = r.json()
    if not data.get("foods"):
        return []
    seen = set()
    unique_matches = []
    for f in data["foods"]:
        desc = f["description"].title()
        if desc not in seen:
            seen.add(desc)
            unique_matches.append(f)
        if len(unique_matches) >= max_results:
            break
    return unique_matches


def get_usda_calories(food, target_cal=100):
    description = food["description"].title()
    nutrients = {n["nutrientName"].lower(): n["value"] for n in food["foodNutrients"]}
    if "energy" not in nutrients:
        return None, f"No calorie info for {description}"
    cal_per_100g = nutrients["energy"]
    cal_per_g = cal_per_100g / 100
    grams_needed = target_cal / cal_per_g
    return {"food": description, "grams": grams_needed}, None


def get_nutritionix_equivalents(food_name, grams_needed):
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_APP_KEY,
        "Content-Type": "application/json"
    }
    body = {"query": food_name}
    r = requests.post(NUTRITIONIX_URL, headers=headers, json=body)
    data = r.json()
    if "foods" not in data or not data["foods"]:
        return {}
    food_data = data["foods"][0]
    results = {
        "g": grams_needed,
        "oz": grams_needed / 28.35
    }
    for m in food_data.get("alt_measures", []):
        unit = clean_unit_name(m.get("measure", ""))
        if not unit:
            continue
        qty = m.get("qty")
        grams = m.get("serving_weight")
        if not grams or grams == 0:
            continue
        amount = grams_needed / (grams / qty)
        if unit not in results:
            results[unit] = amount
    return results


# ---------------- Streamlit App ---------------- #

st.title("🍽️ Calorie Converter (USDA + Nutritionix)")
st.write("Enter a food, pick the best match, and get equivalent weights/units for your target calories.")

food_name = st.text_input("Enter a food name:")
target_cal = st.number_input("Target calories:", min_value=10, max_value=1000, value=100, step=10)

if food_name:
    matches = search_usda(food_name)
    if not matches:
        st.error(f"No USDA results for '{food_name}'")
    else:
        options = [f["description"].title() for f in matches]
        selected_desc = st.selectbox("Choose the correct item:", options)
        food = next(f for f in matches if f["description"].title() == selected_desc)

        if st.button("Convert"):
            usda_result, error = get_usda_calories(food, target_cal)
            if error:
                st.error(error)
            else:
                grams_needed = usda_result["grams"]
                equivalents = get_nutritionix_equivalents(food_name, grams_needed)

                st.subheader(f"{usda_result['food']} equivalents for {target_cal:.0f} cal:")

                order = ["g", "oz", "cup", "tbsp", "tsp"]
                shown = set()
                for unit in order:
                    if unit in equivalents:
                        st.write(f"- {equivalents[unit]:.2f} {unit}")
                        shown.add(unit)
                for unit, amt in equivalents.items():
                    if unit not in shown:
                        st.write(f"- {amt:.2f} {unit}")

