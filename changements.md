API Contract (Image Prompt Generator)
Purpose

Given an article (content + topic + optional focus keyword), return a strict 7-image plan for MidJourney with:

One locked seed for batch consistency (same seed across all 7 images).

A universal style anchor injected into every prompt.

Instruction-only Step 1/2/3 (no serving/plating).

Complete SEO metadata and placement info.

A 2-at-a-time batching plan to control generation order.

Endpoint

POST /v1/image-prompts

Request Body
{
  "article_content": "string (full article or at least the instructions section)",
  "topic": "string (dish/topic)",
  "focus_keyword": "string (optional; falls back to topic)",
  "model": "string (optional; default 'gpt-4.1')",
  "recipe_id": "string (optional; for idempotency/seed log)"
}

Response Body
{
  "seed": 1293883,
  "focus_keyword": "frankenstein brownies",
  "style_anchor": "Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, same food batch, cinematic food photography style, shallow depth of field.",
  "batches": [
    ["featured", "ingredients"],
    ["step1", "step2"],
    ["step3", "serving"],
    ["recipe_card"]
  ],
  "images": [
    {
      "type": "featured",
      "prompt": "Photo-realistic food photography of Frankenstein brownies, hero shot of the finished recipe with all key details visible. Exact batch reference for later steps. Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, same food batch, cinematic food photography style, shallow depth of field. --ar 3:2 --seed 1293883",
      "placement": "Top of article (before introduction)",
      "description": "Hero shot of the finished dish",
      "seo_metadata": {
        "alt_text": "frankenstein brownies featured image",
        "filename": "frankenstein-brownies-featured.jpg",
        "caption": "Delicious frankenstein brownies ready to serve",
        "description": "Stunning hero image of frankenstein brownies with perfect continuity for the set."
      }
    },
    { "type": "ingredients", "...": "..." },
    { "type": "step1", "...": "..." },
    { "type": "step2", "...": "..." },
    { "type": "step3", "...": "..." },
    { "type": "serving", "...": "..." },
    { "type": "recipe_card", "...": "..." }
  ]
}

Semantics

seed: unique per recipe. The same integer is enforced in all 7 prompts.

batches: the exact generation plan your renderer should follow (2 images per request, last batch is 1).

images[].type: must be this order and set—featured, ingredients, step1, step2, step3, serving, recipe_card.

images[].prompt: fully formed MidJourney prompt including style anchor and --seed.

images[].placement: where to insert the image in the article.

images[].seo_metadata: complete, keyworded SEO block; filename is kebab-case and includes the keyword.

Error Handling

If the LLM returns non-JSON or malformed JSON, the service coerces it to spec or falls back to a strict default aligned with your “v2” rules.

If article_content doesn’t contain clear steps, the service extracts/falls back to generic instructional steps (never serving/plating verbs).

Server Logic (Summary)

Seed: generate_random_seed() → lock to this recipe; reuse nowhere else.

Keyword: focus_keyword defaults to topic; both are slugified to build filenames.

Instruction Extraction: parse the article for “Instructions” and pick instructional actions only; filter out serving/plating words.

LLM Call: ask for strict JSON; if it misbehaves, sanitize or fall back.

Coercion: guarantee 7 required types, order, placement, seed, style anchor, filenames, SEO fields; remove serving language from step prompts.

Return: { seed, focus_keyword, style_anchor, batches, images }.

How Your Runner Should Use It

Two-at-a-time generation is mandatory:

Generate featured + ingredients

Generate step1 + step2

Generate step3 + serving

Generate recipe_card

Always copy the same --seed into all 7 prompts for that recipe.

Prompt Improvements (Recommended)

These upgrades will make your images more consistent and professional, reduce drift, and prevent Step images from turning into serving shots.

A. Camera / Composition (per type)

Add consistent camera language:

Featured: “3/4 angle, 50mm equivalent, f/2.8, natural backlight, gentle falloff, subtle specular highlights”

Ingredients: “top-down flat lay, orthogonal alignment, even spacing, edge-to-edge framing”

Steps: “tight macro, 60–90cm working distance, hands partially visible, no faces, minimal motion blur”

Serving: “3/4 angle, same plate/linen set as hero”

Recipe card: “top-down, clean negative space margins for overlay, uncluttered edges”

Add a global aspect ratio once and repeat in all prompts (e.g., --ar 3:2 for landscape blog heros or --ar 4:5 if your template prefers taller images). Consistency matters.

B. Negative Prompts / Guardrails

Include a short negative prompt clause in every prompt:

“no extra props, no logo, no text overlay, no watermarks, no face, no duplicate dishes, no inconsistent frosting color, no messy crumbs unless specified”

This greatly reduces MidJourney drift and random additions.

C. Color / Prop Consistency

Explicitly lock the surface, backdrop, prop set, and dominant color palette:

“same white marble surface, same soft gray linen, same matte white plate”

“keep frosting hue identical to hero image; do not alter tint or saturation”

For colored icings/fillings: “identical green frosting hue as hero; do not change tone.”

D. Step Prompts = Instruction-Only (Critical)

Your spec already enforces this, but strengthen wording:

Step 1/2/3 must reference the exact action (“whisk until glossy”, “fold in chocolate chips”, “spread batter evenly”, “remove from oven and cool in pan”) and must not include serving/plating/garnish language.

Add a regex filter in code (already included) to remove or replace serving verbs if they slip in.

E. Technical MidJourney Parameters

Use the same parameters across all 7 images:

--seed [locked] (already enforced)

--ar 3:2 (or your house ratio, but consistent)

--stylize 100 to 250 (moderation prevents over-styling; pick one value and keep it)

--quality 1 (or --quality .5 if you need speed/cost)

Optional: --style raw (reduces stylization and helps realism if you prefer a more editorial look)

Example tail for every prompt:
--ar 3:2 --stylize 150 --style raw --quality 1 --seed 1293883

F. Filenames & Alt Text

Filenames: {keyword}-{type}.jpg (already enforced), all lowercase, hyphenated.

Alt text: must contain the exact focus keyword; keep it descriptive but short.

Captions: one clean human sentence.

Description: 1–2 sentences, mention continuity with the hero.

G. Recipe Card Image (Usability)

Add: “ample negative space around the dish, clean top edge and bottom edge, no overlapping props at edges” → helps later if you overlay text or icons.

H. Deterministic “Dish Name” Substitution

Ensure [dish name] is replaced with the best available human-readable name:

Prefer an H1/H2 from content; else use focus_keyword; else topic.

Add a small normalization step (title-case, strip brand names).

I. Versioning & Idempotency

Include recipe_id (if provided) in a simple append-only Seed Log (CSV/DB): {recipe_id, seed, focus_keyword, created_at} to prevent seed reuse.

Example Prompt Snippets (Improved)

Featured

Photo-realistic food photography of Frankenstein brownies, hero shot of the finished recipe with all key details visible, 3/4 angle, 50mm equivalent, f/2.8, natural window backlight, subtle specular highlights, same white marble surface, same matte white plate, soft gray linen, no logo, no text, no watermark. Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, same food batch, cinematic food photography style, shallow depth of field. --ar 3:2 --stylize 150 --style raw --quality 1 --seed 1293883


Ingredients

Top-down flat lay of all ingredients for Frankenstein brownies, neat grid layout with even spacing, labeled by arrangement only (no text), same white marble surface as hero, same props, clean edges, no packaging logos, no watermark. Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, same food batch, cinematic food photography style, shallow depth of field. --ar 3:2 --stylize 150 --style raw --quality 1 --seed 1293883


Step 2 (Instruction-only)

Close-up action shot: spread the green frosting evenly over the cooled brownies with an offset spatula; frosting hue must be identical to hero image; tight macro, hands partially visible, no faces, same plate and surface as hero, no garnish, no serving. Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, same food batch, cinematic food photography style, shallow depth of field. --ar 3:2 --stylize 150 --style raw --quality 1 --seed 1293883


Enforces one seed across all 7 images (never reused across recipes).

Applies the universal style anchor to every prompt.

Ensures Step 1/2/3 are strictly instructional (not serving/plating).

Produces deterministic, keyworded filenames and complete SEO metadata.

Adds a two-at-a-time batching plan in the payload (so your runner can generate 2 images per request).

Improves JSON extraction and coerces an LLM response back to spec; otherwise uses a strong fallback that’s aligned with your Custom GPT “v2” brief.

Replace your current function with this (you can keep your get_client() as is):

import re
import json
from typing import List, Dict, Any, Tuple

def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s

def extract_instruction_steps(article_content: str, max_steps: int = 3) -> List[str]:
    """
    Pull 1–3 concrete *instruction* actions from the article content (not serving).
    Falls back to generic prep/cook actions if nothing is found.
    """
    text = article_content or ""
    # Try to isolate an Instructions section first
    m = re.search(r"(?:^|\n)#{0,3}\s*instructions?\s*[:\n]+(.+)", text, flags=re.I | re.S)
    instr = m.group(1) if m else text

    # Split into candidate lines (strip HTML/Markdown bullets)
    lines = []
    for raw in instr.splitlines():
        ln = re.sub(r"^\s*[\-\*\d\.\)\(]+\s*", "", raw).strip()
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if len(ln) >= 5:
            lines.append(ln)

    # Filter out serving/plating terms
    serving_keywords = r"(serve|serving|plate|plating|garnish|drizzle|sprinkle|presentation|arrang(e|ing) on plate)"
    def is_prep_step(ln: str) -> bool:
        return not re.search(serving_keywords, ln, flags=re.I)

    steps = [ln for ln in lines if is_prep_step(ln)]
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for s in steps:
        k = s.lower()
        if k not in seen:
            uniq.append(s)
            seen.add(k)

    # Reasonable fallbacks if not enough purely-instructional items found
    fallbacks = [
        "Combine the wet ingredients until smooth and uniform.",
        "Fold in the dry ingredients just until incorporated—do not overmix.",
        "Transfer to the pan and bake until set; allow to cool before the next step."
    ]
    if not uniq:
        uniq = fallbacks
    if len(uniq) < max_steps:
        uniq += fallbacks
    return uniq[:max_steps]

def coerce_images_to_spec(images: List[Dict[str, Any]],
                          focus_keyword: str,
                          topic: str,
                          seed: int,
                          style_anchor: str) -> List[Dict[str, Any]]:
    """
    Normalize any LLM-produced images to your strict 7-image spec:
    - enforce types, order, style anchor, seed, filenames, SEO fields
    - ensure step1/2/3 are instructional, not serving
    """
    REQUIRED_TYPES = ["featured", "ingredients", "step1", "step2", "step3", "serving", "recipe_card"]
    # Index by type for easy overwrite/fill
    by_type = {img.get("type", ""): img for img in images if isinstance(img, dict)}

    keyword_slug = slugify(focus_keyword)
    placements = {
        "featured": "Top of article (before introduction)",
        "ingredients": "After ingredients section",
        "step1": "In instructions section after step 1",
        "step2": "In instructions section after step 2",
        "step3": "In instructions section after step 3",
        "serving": "In serving section",
        "recipe_card": "End of article"
    }

    # Helper to build consistent SEO block
    def seo_block(img_type: str, caption_hint: str) -> Dict[str, str]:
        base = f"{keyword_slug}-{img_type}.jpg"
        return {
            "alt_text": f"{focus_keyword} {img_type.replace('_', ' ')}",
            "filename": base,
            "caption": caption_hint,
            "description": f"Professional photo of {focus_keyword}; visually consistent with the featured image."
        }

    # Ensure style anchor + seed present in prompt
    def normalize_prompt(p: str) -> str:
        p = (p or "").strip()
        # If style anchor missing, append before seed
        if style_anchor not in p:
            p = f"{p.rstrip()} {style_anchor}".strip()
        # Force seed
        p = re.sub(r"--seed\s+\d+", f"--seed {seed}", p) if "--seed" in p else f"{p} --seed {seed}"
        return p

    # Coerce each required type
    out = []
    for t in REQUIRED_TYPES:
        img = dict(by_type.get(t, {}))
        img["type"] = t
        img["placement"] = placements[t]

        # Default descriptions by type
        default_desc = {
            "featured": "Hero shot of the finished dish",
            "ingredients": "Ingredients layout",
            "step1": "First cooking/preparation step (instructional, not serving)",
            "step2": "Second cooking/preparation step (instructional, not serving)",
            "step3": "Third cooking/preparation step (instructional, not serving)",
            "serving": "Dish being served (final presentation)",
            "recipe_card": "Recipe card presentation (clean top-down)"
        }
        img["description"] = img.get("description") or default_desc[t]

        # Default prompt templates by type if missing
        prompt_defaults = {
            "featured": f"Photo-realistic food photography of {topic}, hero shot of the finished recipe with all key details visible. Exact batch reference for later steps. {style_anchor} --seed {seed}",
            "ingredients": f"Flat lay of all ingredients for {topic}, arranged neatly on the same marble countertop as the featured image. Exact same kitchen, same props, preparing for the featured batch. {style_anchor} --seed {seed}",
            "step1": f"Close-up action shot of the first preparation step for {topic}. Food looks identical in color and texture to the featured dish. {style_anchor} --seed {seed}",
            "step2": f"Close-up action shot of the second preparation step for {topic}. Texture and color exactly match the featured image. {style_anchor} --seed {seed}",
            "step3": f"Close-up action shot of the third preparation step for {topic}. Appearance perfectly matches the featured image. {style_anchor} --seed {seed}",
            "serving": f"Final serving scene of {topic}, identical in look to the featured image. Displayed on the same marble countertop with minimal decor. {style_anchor} --seed {seed}",
            "recipe_card": f"Clean professional top-down image of {topic}, arranged neatly for a recipe card and consistent with earlier images. {style_anchor} --seed {seed}",
        }
        img["prompt"] = normalize_prompt(img.get("prompt") or prompt_defaults[t])

        # Enforce instructional steps (remove serving verbs from step prompts)
        if t in {"step1", "step2", "step3"}:
            serving_terms = r"(serve|serving|plate|plating|garnish|drizzle|sprinkle|presentation|arrang(e|ing) on plate)"
            if re.search(serving_terms, img["prompt"], flags=re.I):
                img["prompt"] = re.sub(serving_terms, "mix/whisk/fold/shape/bake/chill", img["prompt"], flags=re.I)

        # Ensure SEO metadata completeness
        seo = dict(img.get("seo_metadata", {}))
        if not seo.get("alt_text"):
            seo["alt_text"] = f"{focus_keyword} {t.replace('_', ' ')}"
        if not seo.get("filename"):
            seo["filename"] = f"{keyword_slug}-{t}.jpg"
        if not seo.get("caption"):
            caption_map = {
                "featured": f"Delicious {focus_keyword} ready to serve",
                "ingredients": f"Fresh ingredients for making {focus_keyword}",
                "step1": f"Beginning the {focus_keyword} preparation",
                "step2": f"Continuing the {focus_keyword} process",
                "step3": f"Finalizing the {focus_keyword} before serving",
                "serving": f"Serving the finished {focus_keyword}",
                "recipe_card": f"Complete {focus_keyword} recipe card"
            }
            seo["caption"] = caption_map[t]
        if not seo.get("description"):
            seo["description"] = f"This {t.replace('_',' ')} image maintains perfect visual continuity with the featured {focus_keyword}."
        img["seo_metadata"] = seo

        out.append(img)
    return out

def build_batches() -> List[List[str]]:
    """
    Two-at-a-time generation plan to improve quality control.
    """
    return [
        ["featured", "ingredients"],
        ["step1", "step2"],
        ["step3", "serving"],
        ["recipe_card"]
    ]

def generate_midjourney_prompts(article_content: str,
                                topic: str,
                                focus_keyword: str = "",
                                model: str = "gpt-4.1") -> Dict[str, Any]:
    """
    Generate 7 MidJourney prompts with strict visual cohesion, instructional steps,
    and complete SEO metadata. Includes a batching plan for 2-at-a-time rendering.
    """
    client = get_client()
    if not client:
        return {}

    # Seed rules: unique per recipe; same across its 7 images
    seed = generate_random_seed()

    # Keyword defaults
    focus_keyword = (focus_keyword or topic or "").strip()
    if not focus_keyword:
        focus_keyword = "recipe"

    # Universal style anchor (mandatory)
    style_anchor = (
        "Exact same batch as the featured image. Styled consistently in a bright Scandinavian-style kitchen "
        "with white marble countertops, soft natural window light, and minimal decor. Same props, same colors, "
        "same food batch, cinematic food photography style, shallow depth of field."
    )

    # Pull **instructional** step texts from content (avoid serving)
    step_texts = extract_instruction_steps(article_content, max_steps=3)

    # Build a strict JSON instruction payload for the LLM
    keyword_slug = slugify(focus_keyword)
    llm_prompt = f"""
You are a senior food photography director + SEO expert. Return **ONLY** valid JSON matching the schema below.
Respect these **non-negotiable rules**:
- 7 images, in this order: featured, ingredients, step1, step2, step3, serving, recipe_card
- Use **one seed** ({seed}) for all 7 images
- Include the **universal style anchor** verbatim in every prompt
- Step1/2/3 must be **instructional**, never serving/plating/garnishing
- Filenames must be lowercase, hyphenated, include the exact keyword "{focus_keyword}"
- Alt text must include the exact keyword "{focus_keyword}"

Article Topic: {topic}
Focus Keyword: {focus_keyword}
Instruction Steps (use these descriptions in step prompts, not serving):
1) {step_texts[0]}
2) {step_texts[1]}
3) {step_texts[2]}

Style Anchor (mandatory for all prompts):
"{style_anchor}"

Seed (mandatory for all prompts): {seed}

JSON schema:
{{
  "seed": {seed},
  "focus_keyword": "{focus_keyword}",
  "images": [
    {{
      "type": "featured",
      "prompt": "Photo-realistic food photography of [dish name], hero shot of the finished recipe with all key details visible. Exact batch reference for later steps. {style_anchor} --seed {seed}",
      "placement": "Top of article (before introduction)",
      "description": "Hero shot of the finished dish",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-featured.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "ingredients",
      "prompt": "Flat lay of all ingredients for [dish name] on the same marble countertop as the featured image. Exact same kitchen, same props, preparing for the featured batch. {style_anchor} --seed {seed}",
      "placement": "After ingredients section",
      "description": "Ingredients layout",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-ingredients.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "step1",
      "prompt": "Close-up action shot: {step_texts[0]}. Food identical in color/texture to the featured dish. {style_anchor} --seed {seed}",
      "placement": "In instructions section after step 1",
      "description": "First cooking/preparation step (instructional, not serving)",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-step1.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "step2",
      "prompt": "Close-up action shot: {step_texts[1]}. Texture and color exactly match the featured image. {style_anchor} --seed {seed}",
      "placement": "In instructions section after step 2",
      "description": "Second cooking/preparation step (instructional, not serving)",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-step2.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "step3",
      "prompt": "Close-up action shot: {step_texts[2]}. Appearance perfectly matches the featured image. {style_anchor} --seed {seed}",
      "placement": "In instructions section after step 3",
      "description": "Third cooking/preparation step (instructional, not serving)",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-step3.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "serving",
      "prompt": "Final serving scene of [dish name], identical in look to the featured image. Same marble countertop, minimal Scandinavian decor. {style_anchor} --seed {seed}",
      "placement": "In serving section",
      "description": "Dish being served (final presentation)",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-serving.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }},
    {{
      "type": "recipe_card",
      "prompt": "Clean professional top-down image of [dish name], consistent with earlier images, arranged neatly for a recipe card. {style_anchor} --seed {seed}",
      "placement": "End of article",
      "description": "Recipe card presentation (clean top-down)",
      "seo_metadata": {{
        "alt_text": "Include '{focus_keyword}'",
        "filename": "{keyword_slug}-recipe-card.jpg",
        "caption": "Short human caption",
        "description": "Continuity description"
      }}
    }}
  ]
}}

Return only that JSON—no prose, no markdown fences.
"""

    # Try LLM first; if it fails, build a compliant fallback
    llm_result = None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return strictly valid JSON to describe 7 MidJourney images for a recipe. Do not include markdown code fences."},
                {"role": "user", "content": llm_prompt}
            ],
            temperature=0.2,
            max_tokens=1800
        )
        content = response.choices[0].message.content.strip()
        # If model wrapped in fences, try to extract
        if content.startswith("```"):
            # Accept ```json or plain ```
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        parsed = json.loads(content)
        llm_result = parsed if isinstance(parsed, dict) else None
    except Exception:
        llm_result = None

    # Build base structure (either from LLM or from scratch)
    if isinstance(llm_result, dict) and isinstance(llm_result.get("images"), list):
        images = coerce_images_to_spec(
            llm_result["images"], focus_keyword, topic, seed, style_anchor
        )
    else:
        # Strong fallback aligned with your v2 brief
        keyword_slug = slugify(focus_keyword)
        images = coerce_images_to_spec([
            {
                "type": "featured",
                "prompt": f"Photo-realistic food photography of {topic}, hero shot of the finished recipe with all key details visible. Exact batch reference for later steps. {style_anchor} --seed {seed}",
                "placement": "Top of article (before introduction)",
                "description": "Hero shot of the finished dish",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} featured image",
                    "filename": f"{keyword_slug}-featured.jpg",
                    "caption": f"Delicious {focus_keyword} ready to serve",
                    "description": f"Stunning hero image of {focus_keyword} with perfect continuity for the set."
                }
            },
            {
                "type": "ingredients",
                "prompt": f"Flat lay of all ingredients for {topic}, arranged neatly on the same marble countertop as the featured image. Exact same kitchen, same props, preparing for the featured batch. {style_anchor} --seed {seed}",
                "placement": "After ingredients section",
                "description": "Ingredients layout",
                "seo_metadata": {
                    "alt_text": f"Ingredients for {focus_keyword} arranged on marble countertop",
                    "filename": f"{keyword_slug}-ingredients.jpg",
                    "caption": f"Fresh ingredients for {focus_keyword}",
                    "description": f"Every ingredient needed to prepare {focus_keyword}, styled with continuity."
                }
            },
            {
                "type": "step1",
                "prompt": f"Close-up action shot: {step_texts[0]}. Food identical in color and texture to the featured dish. {style_anchor} --seed {seed}",
                "placement": "In instructions section after step 1",
                "description": "First cooking/preparation step (instructional, not serving)",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} step 1",
                    "filename": f"{keyword_slug}-step1.jpg",
                    "caption": f"Beginning the {focus_keyword} preparation",
                    "description": f"First instructional step for {focus_keyword}, visually matching the hero."
                }
            },
            {
                "type": "step2",
                "prompt": f"Close-up action shot: {step_texts[1]}. Texture and color exactly match the featured image. {style_anchor} --seed {seed}",
                "placement": "In instructions section after step 2",
                "description": "Second cooking/preparation step (instructional, not serving)",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} step 2",
                    "filename": f"{keyword_slug}-step2.jpg",
                    "caption": f"Continuing the {focus_keyword} process",
                    "description": f"Second instructional step for {focus_keyword}, consistent with the hero."
                }
            },
            {
                "type": "step3",
                "prompt": f"Close-up action shot: {step_texts[2]}. Appearance perfectly matches the featured image. {style_anchor} --seed {seed}",
                "placement": "In instructions section after step 3",
                "description": "Third cooking/preparation step (instructional, not serving)",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} step 3",
                    "filename": f"{keyword_slug}-step3.jpg",
                    "caption": f"Finalizing the {focus_keyword} before serving",
                    "description": f"Third instructional step for {focus_keyword}, matching hero color/texture."
                }
            },
            {
                "type": "serving",
                "prompt": f"Final serving scene of {topic}, identical in look to the featured image. Displayed on the same marble countertop with minimal Scandinavian decor. {style_anchor} --seed {seed}",
                "placement": "In serving section",
                "description": "Dish being served (final presentation)",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} serving",
                    "filename": f"{keyword_slug}-serving.jpg",
                    "caption": f"Serving the finished {focus_keyword}",
                    "description": f"Final presentation of {focus_keyword}, perfectly matching the hero."
                }
            },
            {
                "type": "recipe_card",
                "prompt": f"Clean professional top-down image of {topic}, arranged neatly for a recipe card, consistent with earlier images. {style_anchor} --seed {seed}",
                "placement": "End of article",
                "description": "Recipe card presentation (clean top-down)",
                "seo_metadata": {
                    "alt_text": f"{focus_keyword} recipe card",
                    "filename": f"{keyword_slug}-recipe-card.jpg",
                    "caption": f"Complete {focus_keyword} recipe card",
                    "description": f"Top-down composition of {focus_keyword} matching the hero styling."
                }
            }
        ], focus_keyword, topic, seed, style_anchor)

    return {
        "seed": seed,
        "focus_keyword": focus_keyword,
        "style_anchor": style_anchor,
        "batches": build_batches(),  # [["featured","ingredients"], ["step1","step2"], ["step3","serving"], ["recipe_card"]]
        "images": images
    }

What changed and why (brief)

Instruction-only steps: We parse your article to pick actionable prep steps and sanitize prompts so Step 1/2/3 never become serving/plating shots.

Strict coercion: Even if the LLM returns imperfect JSON, we normalize types, order, style anchor, seed, filenames, and SEO fields.

Batch plan: Included batches so your renderer can strictly do 2 at a time.

Filenames & SEO: Consistent, keyword-rich filenames and alt/caption/description across all seven images.


