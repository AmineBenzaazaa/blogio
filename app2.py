# app1.py
# ---------------------------------------------------------
# Food Blog Recipe Generator: PLAIN TEXT recipe synthesis,
# parsing, Tasty Recipe JS card filler, and Recipe JSON-LD.
#
# Notes:
# - No mock values in JSON-LD: include only fields you have.
# - Separate step to generate Schema.org Recipe JSON-LD.
# - "Additional time" supported (rest/chill/inactive).
# ---------------------------------------------------------

import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# ---------- OpenAI client (optional) ----------
# You can set OPENAI_API_KEY in env or in the UI sidebar.
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# =========================================================
# Utility helpers
# =========================================================

def _ensure_openai_client() -> Optional[Any]:
    """Initialize OpenAI client if available and API key present."""
    api_key = os.getenv("OPENAI_API_KEY") or st.session_state.get("OPENAI_API_KEY")
    if OpenAI is None or not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception:
        return None

def _openai_text(prompt: str, model: str, temperature: float) -> str:
    """Simple text generation wrapper. Returns model text or empty string."""
    client = _ensure_openai_client()
    if not client:
        # Fallback: return empty string when no key/client.
        return ""
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": "You are a precise recipe generator that follows formats exactly."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""

def _extract_minutes(line: str) -> Optional[int]:
    """
    Extract minutes from formats like:
      'Prep time: 1 h 30 m'  -> 90
      'Cook time: 45 m'      -> 45
      'Total time: 2 h'      -> 120
      'Additional time: 1 h 10 m' -> 70
    """
    if not line:
        return None
    s = line.lower()
    # Capture "h" and "m"
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*m", s)
    total = 0
    if h:
        total += int(h.group(1)) * 60
    if m:
        total += int(m.group(1))
    # Fallback: plain number means minutes
    if total == 0:
        just_num = re.search(r"(\d+)", s)
        if just_num:
            total = int(just_num.group(1))
    return total or None

def _to_iso8601_minutes(minutes: Optional[int]) -> Optional[str]:
    """Convert minutes integer to ISO 8601 duration e.g., PT1H30M / PT45M."""
    if minutes is None:
        return None
    try:
        m = int(minutes)
    except Exception:
        return None
    h, mm = divmod(m, 60)
    if h and mm:
        return f"PT{h}H{mm}M"
    if h and not mm:
        return f"PT{h}H"
    return f"PT{mm}M"

# =========================================================
# Parsing the PLAIN TEXT format
# =========================================================

def parse_recipe_text_blocks(text: str) -> Dict[str, Any]:
    """
    Parse the strict plain-text format:
      Title
      Optional description
      Prep time: <...>
      Cook time: <...>
      Additional time: <...> (optional)
      Total time: <...>
      Yield: <...>
      Servings: <...>

      Ingredients
      - line
      ...
      Instructions
      1. step
      ...
      Notes
      - line
      ...
      Nutrition
      Calories: <...>
      Carbohydrates: <...>
      Protein: <...>
      Fat: <...>
      Sodium: <...>
    Extended Nutrition keys also supported (Serving Size, Sugar, etc.).
    """
    if not text or not text.strip():
        return {}

    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    lines = [ln for ln in lines if ln is not None]

    # Title and optional description
    title = lines[0].strip() if lines else ""
    description = ""
    idx = 1

    # Detect description vs time details
    def _is_time_line(s: str) -> bool:
        s = s.lower().strip()
        return s.startswith(("prep time:", "cook time:", "total time:", "additional time:", "rest time:", "inactive time:", "chill time:", "rise time:"))

    if idx < len(lines) and lines[idx].strip() and not _is_time_line(lines[idx]):
        description = lines[idx].strip()
        idx += 1

    # Details (times/yield/servings)
    prep_iso = cook_iso = total_iso = additional_iso = None
    recipe_yield = None
    servings = None

    # Read until we hit a section header like "Ingredients"
    while idx < len(lines):
        L = lines[idx].strip()
        low = L.lower()
        if low == "ingredients":
            break
        if low.startswith("prep time"):
            prep_iso = _to_iso8601_minutes(_extract_minutes(L))
        elif low.startswith("cook time"):
            cook_iso = _to_iso8601_minutes(_extract_minutes(L))
        elif low.startswith(("additional time", "rest time", "inactive time", "chill time", "rise time")):
            additional_iso = _to_iso8601_minutes(_extract_minutes(L))
        elif low.startswith("total time"):
            total_iso = _to_iso8601_minutes(_extract_minutes(L))
        elif low.startswith("yield"):
            try:
                recipe_yield = L.split(":", 1)[1].strip()
            except Exception:
                recipe_yield = L
        elif low.startswith("servings"):
            try:
                servings = re.split(r":", L, 1)[1].strip()
            except Exception:
                servings = L
        idx += 1

    # Ingredients
    ingredients: List[str] = []
    while idx < len(lines):
        L = lines[idx].strip()
        if L.lower() == "ingredients":
            idx += 1
            continue
        if L.lower() == "instructions":
            break
        if L.startswith("-"):
            item = L[1:].strip()
            if item:
                ingredients.append(item)
        idx += 1

    # Instructions
    instructions: List[str] = []
    while idx < len(lines):
        L = lines[idx].strip()
        if L.lower() == "instructions":
            idx += 1
            continue
        if L.lower() == "notes":
            break
        m = re.match(r"^\s*(?:\d+[\.\)]\s*|\-\s*)(.+)$", L)
        if m:
            step = m.group(1).strip()
            if step:
                instructions.append(step)
        idx += 1

    # Notes
    notes: List[str] = []
    while idx < len(lines):
        L = lines[idx].strip()
        if L.lower() == "notes":
            idx += 1
            continue
        if L.lower() == "nutrition":
            break
        if L.startswith("-"):
            n = L[1:].strip()
            if n:
                notes.append(n)
        idx += 1

    # Nutrition
    nutrition: Dict[str, str] = {}
    while idx < len(lines):
        L = lines[idx].strip()
        if L.lower() == "nutrition":
            idx += 1
            continue
        if not L:
            idx += 1
            continue
        if ":" in L:
            key, val = L.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key and val:
                nutrition[key] = val
        idx += 1

    # Normalize Nutrition keys
    alias_map = {
        "Calories": ["Calories", "Energy"],
        "Carbohydrates": ["Carbohydrates", "Carbs"],
        "Protein": ["Protein"],
        "Total Fat": ["Fat", "Total Fat"],
        "Sodium": ["Sodium"],
        "Serving Size": ["Serving Size", "Serving", "ServingSize"],
        "Sugar": ["Sugar", "Sugars"],
        "Saturated Fat": ["Saturated Fat"],
        "Unsaturated Fat": ["Unsaturated Fat"],
        "Trans Fat": ["Trans Fat"],
        "Cholesterol": ["Cholesterol"],
        "Fiber": ["Fiber", "Dietary Fiber"],
    }
    normalized_nutrition: Dict[str, str] = {}
    for canonical, aliases in alias_map.items():
        for a in aliases:
            if a in nutrition and nutrition[a]:
                normalized_nutrition[canonical] = nutrition[a]
                break
    for k, v in nutrition.items():
        if k not in normalized_nutrition and v:
            normalized_nutrition[k] = v

    return {
        "title": title,
        "description": description,
        "ingredients": ingredients,
        "instructions": instructions,
        "notes": notes,
        "nutrition": normalized_nutrition if normalized_nutrition else None,
        "yield": recipe_yield,
        "servings": servings,
        "prepISO": prep_iso,
        "cookISO": cook_iso,
        "additionalISO": additional_iso,
        "totalISO": total_iso,
    }

# =========================================================
# Normalization for Tasty + author injection
# =========================================================

def _normalize_recipe_for_tasty(recipe: Dict[str, Any], author_name: Optional[str] = None) -> Dict[str, Any]:
    """Ensure keys exist and inject author_name if given."""
    r = dict(recipe or {})
    r.setdefault("title", "")
    r.setdefault("description", "")
    r.setdefault("ingredients", [])
    r.setdefault("instructions", [])
    r.setdefault("notes", [])
    r.setdefault("category", "")
    r.setdefault("cuisine", "")
    r.setdefault("keywords", [])
    if author_name:
        r["author"] = author_name
    return r

# =========================================================
# JS generator: Tasty Recipe CPT fill function
# =========================================================

def generate_js_recipe_card(recipe: Dict[str, Any]) -> str:
    """Generate pure JavaScript fillRecipeForm() function for Tasty Recipe CPT integration."""

    def js_escape(text: str) -> str:
        if not text:
            return ""
        return (
            text.replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", "")
        )

    def format_list_for_js(items: List[str]) -> str:
        if not items:
            return ""
        escaped_items = [js_escape(item) for item in items]
        return "\\n".join(escaped_items)

    description = js_escape(recipe.get("description", ""))
    ingredients = format_list_for_js(recipe.get("ingredients", []))
    instructions = format_list_for_js(recipe.get("instructions", []))
    notes = format_list_for_js(recipe.get("notes", []))

    title = js_escape(recipe.get("title", ""))
    author = js_escape(recipe.get("author", ""))
    servings_value = js_escape(str(recipe.get("servings", "") or ""))

    def iso_to_minutes(iso_time: Optional[str]) -> str:
        if not iso_time:
            return ""
        h = re.search(r"(\\d+)\\s*H", iso_time, re.I)
        m = re.search(r"(\\d+)\\s*M", iso_time, re.I)
        total = 0
        if h:
            total += int(h.group(1)) * 60
        if m:
            total += int(m.group(1))
        return str(total) if total else ""

    prep_time = iso_to_minutes(recipe.get("prepISO"))
    cook_time = iso_to_minutes(recipe.get("cookISO"))
    total_time = iso_to_minutes(recipe.get("totalISO"))
    additional_time = iso_to_minutes(recipe.get("additionalISO"))

    if not total_time:
        mins = 0
        for t in (prep_time, cook_time, additional_time):
            try:
                mins += int(t) if t else 0
            except Exception:
                pass
        total_time = str(mins) if mins else ""

    yield_value = js_escape(recipe.get("yield", ""))
    category = js_escape(recipe.get("category", ""))
    method = js_escape(recipe.get("method", ""))
    cuisine = js_escape(recipe.get("cuisine", ""))
    diet = js_escape(recipe.get("diet", ""))
    keywords = js_escape(", ".join(recipe.get("keywords", [])) if isinstance(recipe.get("keywords", []), list) else str(recipe.get("keywords", "")))

    nutrition = recipe.get("nutrition", {}) or {}
    def nv(key: str, fallback_key: Optional[str] = None) -> str:
        if key in nutrition and nutrition[key]:
            return js_escape(str(nutrition[key]))
        if fallback_key and fallback_key in nutrition and nutrition[fallback_key]:
            return js_escape(str(nutrition[fallback_key]))
        return ""

    serving_size = nv("Serving Size", "serving_size")
    calories = nv("Calories", "calories")
    sugar = nv("Sugar", "sugar")
    sodium = nv("Sodium", "sodium")
    fat = nv("Total Fat", "fat")
    saturated_fat = nv("Saturated Fat", "saturated_fat")
    unsaturated_fat = nv("Unsaturated Fat", "unsaturated_fat")
    trans_fat = nv("Trans Fat", "trans_fat")
    cholesterol = nv("Cholesterol", "cholesterol")
    carbohydrates = nv("Carbohydrates", "carbohydrates")
    fiber = nv("Fiber", "fiber")
    protein = nv("Protein", "protein")

    js_code = f"""function fillRecipeForm() {{
const f=(s,v)=>document.querySelector(s)&&(document.querySelector(s).value=v),
p=t=>t.split('\\n').map(x=>`<p>${{x}}</p>`).join(''),
n=t=>t.split('\\n').map((x,i)=>`<p>${{i+1}}. ${{x}}</p>`).join(''),
g={{
description:'{description}',
ingredients:p('{ingredients}'),
instructions:n('{instructions}'),
notes:p('{notes}')
}};

// 1) Fill the WYSIWYG fields (Tasty uses TinyMCE editors with these IDs)
for (const k in g) {{
  const ed = window.tinyMCE?.get(`tasty-recipes-recipe-${{k}}`);
  ed && ed.setContent(g[k]);
}}

// 2) Title (Gutenberg or Classic) and Author Name
f('textarea.editor-post-title__input, #title, input[name="post_title"]','{title}');
['input[name="author_name"]','#tasty-recipes-author-name','input[name="author"]']
  .forEach(sel => f(sel,'{author}'));

// 3) Details fields
[
 "prep_time","cook_time","additional_time","total_time","yield",
 "servings","category","method","cuisine","diet","keywords",
 "serving_size","calories","sugar","sodium","fat","saturated_fat","unsaturated_fat",
 "trans_fat","cholesterol","carbohydrates","fiber","protein"
].forEach(k => f(`[name="${{k}}"]`, {{
  prep_time:'{prep_time}',
  cook_time:'{cook_time}',
  additional_time:'{additional_time}',
  total_time:'{total_time}',
  yield:'{yield_value}',
  servings:'{servings_value}',
  category:'{category}',
  method:'{method}',
  cuisine:'{cuisine}',
  diet:'{diet}',
  keywords:'{keywords}',
  serving_size:'{serving_size}',
  calories:'{calories}',
  sugar:'{sugar}',
  sodium:'{sodium}',
  fat:'{fat}',
  saturated_fat:'{saturated_fat}',
  unsaturated_fat:'{unsaturated_fat}',
  trans_fat:'{trans_fat}',
  cholesterol:'{cholesterol}',
  carbohydrates:'{carbohydrates}',
  fiber:'{fiber}',
  protein:'{protein}'
}}[k] ));
}}
fillRecipeForm();"""
    return js_code

# =========================================================
# Schema.org Recipe JSON-LD builder (no mock data)
# =========================================================

def _minutes_iso8601(minutes: Optional[int]) -> Optional[str]:
    if minutes is None or minutes == "":
        return None
    try:
        m = int(minutes)
    except Exception:
        return None
    h, mm = divmod(m, 60)
    if h and mm:
        return f"PT{h}H{mm}M"
    if h and not mm:
        return f"PT{h}H"
    return f"PT{mm}M"

def _as_list(x) -> List[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if str(i).strip()]
    return [str(x).strip()]

def build_recipe_jsonld(
    recipe: Dict[str, Any],
    *,
    page_url: Optional[str] = None,
    site_name: Optional[str] = None,
    site_logo_url: Optional[str] = None,
    images: Optional[List[str]] = None,
    date_published: Optional[str] = None,
    date_modified: Optional[str] = None,
) -> str:
    """Build Schema.org Recipe JSON-LD using only the values present in `recipe`."""

    name = recipe.get("title") or recipe.get("name")
    description = recipe.get("description")

    prep_iso = recipe.get("prepISO")
    cook_iso = recipe.get("cookISO")
    total_iso = recipe.get("totalISO")
    additional_iso = recipe.get("additionalISO") or recipe.get("restISO") or recipe.get("inactiveISO")

    prep_minutes = recipe.get("prep_minutes")
    cook_minutes = recipe.get("cook_minutes")
    total_minutes = recipe.get("total_minutes")
    additional_minutes = recipe.get("additional_minutes")

    if not prep_iso and prep_minutes is not None:
        prep_iso = _minutes_iso8601(prep_minutes)
    if not cook_iso and cook_minutes is not None:
        cook_iso = _minutes_iso8601(cook_minutes)
    if not additional_iso and additional_minutes is not None:
        additional_iso = _minutes_iso8601(additional_minutes)
    if not total_iso and total_minutes is not None:
        total_iso = _minutes_iso8601(total_minutes)
    if not total_iso:
        try:
            total_calc = 0
            for t in (prep_minutes, cook_minutes, additional_minutes):
                if t:
                    total_calc += int(t)
            if total_calc > 0:
                total_iso = _minutes_iso8601(total_calc)
        except Exception:
            pass

    recipe_yield = recipe.get("yield") or recipe.get("recipe_yield")
    servings = recipe.get("servings")

    recipe_category = recipe.get("category") or recipe.get("recipeCategory")
    recipe_cuisine  = recipe.get("cuisine") or recipe.get("recipeCuisine")
    keywords_list   = recipe.get("keywords") or []
    if isinstance(keywords_list, list):
        keywords = ", ".join([k for k in keywords_list if str(k).strip()])
    else:
        keywords = str(keywords_list or "")

    author_name = recipe.get("author") or recipe.get("author_name")

    ingredients = _as_list(recipe.get("ingredients"))
    instructions = _as_list(recipe.get("instructions"))
    howto_steps = [{"@type": "HowToStep", "text": step} for step in instructions] if instructions else []

    nutr_src = recipe.get("nutrition") or {}
    def nget(*keys):
        for k in keys:
            if k in nutr_src and nutr_src[k] not in (None, ""):
                return nutr_src[k]
        return None

    nutrition_obj: Dict[str, Any] = {"@type": "NutritionInformation"}
    mapping = {
        "servingSize": ("Serving Size", "serving_size"),
        "calories": ("Calories", "calories"),
        "sugarContent": ("Sugar", "sugar"),
        "sodiumContent": ("Sodium", "sodium"),
        "fatContent": ("Total Fat", "fat", "total_fat"),
        "saturatedFatContent": ("Saturated Fat", "saturated_fat"),
        "unsaturatedFatContent": ("Unsaturated Fat", "unsaturated_fat"),
        "transFatContent": ("Trans Fat", "trans_fat"),
        "cholesterolContent": ("Cholesterol", "cholesterol"),
        "carbohydrateContent": ("Carbohydrates", "carbohydrates", "carbs"),
        "fiberContent": ("Fiber", "fiber"),
        "proteinContent": ("Protein", "protein"),
    }
    for out_key, in_keys in mapping.items():
        val = nget(*in_keys)
        if val not in (None, ""):
            nutrition_obj[out_key] = str(val)

    data: Dict[str, Any] = {"@context": "https://schema.org", "@type": "Recipe"}

    if page_url:
        data["mainEntityOfPage"] = page_url
        data["url"] = page_url

    if name: data["name"] = name
    if description: data["description"] = description

    if images:
        imgs = [u for u in images if isinstance(u, str) and u.startswith("http")]
        if imgs:
            data["image"] = imgs if len(imgs) > 1 else imgs[0]

    if date_published: data["datePublished"] = date_published
    if date_modified:  data["dateModified"] = date_modified

    if author_name:
        data["author"] = {"@type": "Person", "name": author_name}

    if recipe_yield: data["recipeYield"] = str(recipe_yield)
    elif servings:   data["recipeYield"] = str(servings)

    if recipe_category: data["recipeCategory"] = recipe_category
    if recipe_cuisine:  data["recipeCuisine"] = recipe_cuisine
    if keywords:        data["keywords"] = keywords

    if prep_iso:        data["prepTime"] = prep_iso
    if cook_iso:        data["cookTime"] = cook_iso
    if additional_iso:  data["additionalTime"] = additional_iso
    if total_iso:       data["totalTime"] = total_iso

    if ingredients:     data["recipeIngredient"] = ingredients
    if howto_steps:     data["recipeInstructions"] = howto_steps

    if len(nutrition_obj.keys()) > 1:
        data["nutrition"] = nutrition_obj

    if site_name and site_logo_url:
        data["publisher"] = {
            "@type": "Organization",
            "name": site_name,
            "logo": {"@type": "ImageObject", "url": site_logo_url}
        }

    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

# =========================================================
# Synthesis: build recipe text from context (LLM)
# =========================================================

def synthesize_recipe_from_context(
    topic: str = "",
    focus_keyword: str = "",
    full_recipe_text: str = "",
    article_md: str = "",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Use the LLM to synthesize a well-organized recipe text from context, then parse it.
    Returns {} on failure. Includes 'Additional time' and richer nutrition keys.
    """
    try:
        mdl = model or st.session_state.get("model_name", "gpt-4o-mini")
        t_default = st.session_state.get("temperature", 0.6)
        try:
            t_val = float(temperature if temperature is not None else t_default)
        except Exception:
            t_val = float(t_default)
        temp = min(max(t_val, 0.0), 1.2)

        CLIP = 6000
        context_bits: List[str] = []
        if full_recipe_text and full_recipe_text.strip():
            context_bits.append("Full Recipe text provided by user:\n" + full_recipe_text.strip()[:CLIP])
        if article_md and article_md.strip():
            context_bits.append("Article content (markdown):\n" + article_md.strip()[:CLIP])
        context = "\n\n".join(context_bits) or "No explicit recipe text was provided."

        def base_prompt(strict: bool = False) -> str:
            return f"""
From the context below, synthesize a single, clean, well-organized recipe in PLAIN TEXT using EXACTLY this format so a simple parser can read it:

Title on the first line
Optional short description on the second line
Prep time: <number> m or h m
Cook time: <number> m or h m
Additional time: <number> m or h m
Total time: <number> m or h m
Yield: <e.g., 4 servings or 1 loaf>
Servings: <e.g., 4 servings>

Ingredients
- item 1
- item 2
- ...

Instructions
1. step 1
2. step 2
3. ...

Notes
- note line 1
- note line 2

Nutrition
Serving Size: <value>
Calories: <value>
Sugar: <value>
Sodium: <value>
Total Fat: <value>
Saturated Fat: <value>
Unsaturated Fat: <value>
Trans Fat: <value>
Cholesterol: <value>
Carbohydrates: <value>
Fiber: <value>
Protein: <value>

Rules:
- Use US measurements and realistic amounts.
- Base details on the provided context faithfully; do not invent exotic, specific brand details.
- Avoid any code fences, Markdown headings (#), or extra labeling not shown in the format.
- Keep the title concise and descriptive.
- Keep ingredient lines one per line; keep steps concise but precise.
{"- Output must include every section and field above in the exact order; if unknown, provide reasonable values." if strict else ""}

Context:
Topic: {topic}
Focus keyword: {focus_keyword}

{context}
""".strip()

        def is_valid(parsed: Dict[str, Any]) -> bool:
            if not parsed:
                return False
            if not (parsed.get("ingredients") and parsed.get("instructions")):
                return False
            if not any(parsed.get(k) for k in ("prepISO", "cookISO", "totalISO")):
                return False
            return True

        raw = _openai_text(base_prompt(strict=False), mdl, temp)
        parsed = parse_recipe_text_blocks(raw)

        if not is_valid(parsed):
            raw2 = _openai_text(base_prompt(strict=True), mdl, max(0.3, temp - 0.2))
            parsed2 = parse_recipe_text_blocks(raw2)
            if is_valid(parsed2):
                return parsed2
            return parsed if parsed else {}

        return parsed
    except Exception:
        return {}

# =========================================================
# Streamlit UI
# =========================================================

st.set_page_config(page_title="Recipe Generator + Tasty JS + JSON-LD", page_icon="🍰", layout="wide")

with st.sidebar:
    st.header("Settings")
    st.session_state["OPENAI_API_KEY"] = st.text_input("OpenAI API Key", os.getenv("OPENAI_API_KEY", ""), type="password")
    st.session_state["model_name"] = st.text_input("Model", st.session_state.get("model_name", "gpt-4o-mini"))
    st.session_state["temperature"] = st.slider("Temperature", 0.0, 1.2, float(st.session_state.get("temperature", 0.6)), 0.05)

st.title("🍰 Recipe Generator → Tasty Recipe JS → Recipe JSON-LD")

# Inputs
st.markdown("### Step 1 — Provide Context")
col1, col2 = st.columns(2)
with col1:
    topic = st.text_input("Topic (e.g., Black Velvet Cheesecake Cookies)", value=st.session_state.get("topic", ""))
    focus_keyword = st.text_input("Focus keyword (SEO)", value=st.session_state.get("focus_keyword", ""))
    author_name = st.text_input("Author Name", value=st.session_state.get("author_name", ""))
with col2:
    canonical_url = st.text_input("Canonical URL (on tastetorate.com)", value=st.session_state.get("canonical_url", ""))
    date_published = st.text_input("Date Published (YYYY-MM-DD, optional)", value=st.session_state.get("date_published", ""))
    date_modified = st.text_input("Date Modified (YYYY-MM-DD, optional)", value=st.session_state.get("date_modified", ""))

full_recipe_text = st.text_area("Full Recipe text (optional, preferred if you have it)", height=160, value=st.session_state.get("full_recipe_text", ""))
article_md = st.text_area("Article content (markdown, optional)", height=160, value=st.session_state.get("article_md", ""))

# Actions
st.markdown("### Step 2 — Generate / Parse PLAIN TEXT Recipe")
gen_col1, gen_col2 = st.columns([1,1])
with gen_col1:
    if st.button("🔮 Synthesize Recipe from Context"):
        parsed = synthesize_recipe_from_context(
            topic=topic,
            focus_keyword=focus_keyword,
            full_recipe_text=full_recipe_text,
            article_md=article_md,
            model=st.session_state.get("model_name"),
            temperature=st.session_state.get("temperature"),
        )
        if parsed:
            st.session_state["parsed_recipe"] = parsed
            st.success("Recipe synthesized and parsed.")
        else:
            st.error("Failed to synthesize or parse recipe. Provide more context or set API key.")
with gen_col2:
    if st.button("🧪 Parse Provided Recipe Text Only"):
        parsed = parse_recipe_text_blocks(full_recipe_text)
        if parsed:
            st.session_state["parsed_recipe"] = parsed
            st.success("Parsed provided recipe text.")
        else:
            st.error("Could not parse provided text. Ensure it matches the required format.")

# Display parsed
parsed = st.session_state.get("parsed_recipe")
if parsed:
    st.markdown("### Step 3 — Parsed Recipe (preview)")
    st.json(parsed, expanded=False)

    # Normalize for Tasty + inject author
    norm = _normalize_recipe_for_tasty(parsed, author_name=author_name)
    st.session_state["normalized_recipe"] = norm

    # Tasty JS
    st.markdown("### Step 5 — AI-Generated TASTY RECIPE CARD (Pure JavaScript)")
    js_code = generate_js_recipe_card(norm)
    st.session_state["js_recipe_card_ai"] = js_code
    st.code(js_code, language="javascript")
    st.download_button("Download fillRecipeForm.js", data=js_code.encode("utf-8"), file_name="fillRecipeForm.js", mime="text/javascript")

    # Schema JSON-LD
    st.markdown("### 🚀 Step 6 — Recipe JSON-LD (Schema.org)")
    SITE_NAME = "Taste to Rate"
    SITE_LOGO = "https://tastetorate.com/wp-content/uploads/2024/08/taste-to-rate-logo.png"
    schema_json = build_recipe_jsonld(
        norm,
        page_url=canonical_url or None,
        site_name=SITE_NAME,
        site_logo_url=SITE_LOGO,
        images=[],
        date_published=date_published or None,
        date_modified=date_modified or None,
    )
    st.session_state["recipe_schema_jsonld"] = schema_json
    st.text_area("Generated JSON-LD", schema_json, height=260)
    st.download_button("Download recipe.schema.json", data=schema_json.encode("utf-8"), file_name="recipe.schema.json", mime="application/ld+json")
else:
    st.info("No parsed recipe yet. Generate or parse a recipe in Step 2.")

# Footer
st.caption("Tip: If Rank Math generates Recipe schema for the same post, disable one to avoid duplicates.")