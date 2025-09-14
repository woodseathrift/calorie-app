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
    
    # Rule 1: reject overly long / with parentheses
    if len(unit) > 20 or "(" in unit or ")" in unit or ":" in unit:
        return None
    
    # Rule 2: reject junk
    if len(unit) < 2:
        return None
    if not any(c.isalpha() for c in unit):  # must contain letters
        return None
    if not any(v in unit for v in "aeiou"):  # no vowels → suspicious
        return None
    
    # Rule 3: normalize plurals
    if unit.endswith("s") and not unit.endswith("ss"):
        unit = unit[:-1]
    
    # Rule 4: synonyms
    synonyms = {
        "tablespoon": "tbsp",
        "teaspoon": "tsp",
        "ounce": "oz",
        "gram": "g"
    }
    unit = synonyms.get(unit, unit)
    
    return unit


def search_usda(food_name, max_results=20):
    """Search USDA for matching foods and deduplicate by description"""
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
    """Get calories per 100g for a selected USDA food entry"""
    description = food["description"].title()
    nutrients = {n["nutrientName"].lower(): n["value"] for n in food["foodNutrients"]}
    
    if "energy" not in nutrients:
        return None, f"No calorie info for {description}"
    
    cal_per_100g = nutrients["energy"]
    cal_per_g = cal_per_100g / 100
    grams_needed = target_cal / cal_per_g
    
    return {"food": description, "grams": grams_needed}, None


def get_nutritionix_equivalents(food_name, grams_needed):
    """Ask Nutritionix for serving sizes and convert to equivalents."""
    headers = {
        "x-app-id": NUTRITIONIX_APP_ID,
        "x-app-key": NUTRITIONIX_APP_KEY,
        "Content-Type": "application/json"
    }
    body = {"query": f"{food_name}"}
    
    r = requests.post(NUTRITIONIX_URL, headers=headers, json=body)
    data = r.json()
    
    if "foods" not in data or not data["foods"]:
        return {}
    
    food_data = data["foods"][0]
    
    # Start with g and oz (always available)
    results = {
        "g": grams_needed,
        "oz": grams_needed / 28.35
    }
    
    # Loop over Nutritionix measures
    for m in food_data.get("alt_measures", []):
        unit = clean_unit_name(m.get("measure", ""))
        if not unit:
            continue
        qty = m.get("qty")
        grams = m.get("serving_weight")
        if not grams or grams == 0:
            continue
        
        # convert grams_needed into this unit
        amount = grams_needed / (grams / qty)
        
        # Store if not already covered
        if unit not in results:
            results[unit] = amount
    
    return results


def get_food_info(food_name, target_cal=100):
    # Step 1: search USDA
    matches = search_usda(food_name)
    if not matches:
        return f"⚠️ No USDA results for '{food_name}'"
    
    # Step 2: let user choose if multiple
    if len(matches) > 1:
        print("\nMultiple matches found:")
        for i, f in enumerate(matches, start=1):
            print(f"{i}. {f['description'].title()}")
        
        while True:
            choice = input("Choose the number of the correct item (or type 'search' to try again): ")
            if choice.lower() == "search":
                return None  # user wants to search again
            try:
                choice = int(choice)
                if 1 <= choice <= len(matches):
                    food = matches[choice - 1]
                    break
            except ValueError:
                pass
            print("Invalid choice.")
    else:
        food = matches[0]
    
    # Step 3: compute grams
    usda_result, error = get_usda_calories(food, target_cal)
    if error:
        return f"⚠️ {error}"
    
    grams_needed = usda_result["grams"]
    
    # Step 4: Nutritionix equivalents
    equivalents = get_nutritionix_equivalents(food_name, grams_needed)
    
    return usda_result["food"], equivalents


# ---------------- Main Program ---------------- #

def main():
    print("=== Calorie Converter (USDA + Nutritionix) ===")
    print("Type a food name, or 'quit' to exit.\n")
    
    while True:
        food_name = input("Enter food: ").strip()
        if food_name.lower() in ["quit", "exit", "q"]:
            break
        
        try:
            target_cal = float(input("Enter target calories (default 100): ") or "100")
        except ValueError:
            target_cal = 100
        
        result = get_food_info(food_name, target_cal)
        if result is None:
            continue
        if isinstance(result, str):  # error
            print(result, "\n")
        else:
            food, equivalents = result
            print(f"\n🍽️ {food} equivalents for {target_cal:.0f} cal:")
            
            # Sort for clean display
            order = ["g", "oz", "cup", "tbsp", "tsp"]
            shown = set()
            
            # First show g, oz, and common measures
            for unit in order:
                if unit in equivalents:
                    print(f" - {equivalents[unit]:.2f} {unit}")
                    shown.add(unit)
            
            # Then show all other valid units
            for unit, amt in equivalents.items():
                if unit not in shown:
                    print(f" - {amt:.2f} {unit}")
            print("")


if __name__ == "__main__":
    main()
