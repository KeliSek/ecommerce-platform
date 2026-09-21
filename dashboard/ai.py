# dashboard/ai.py
"""
Thin wrapper around the Gemini API for the AI-assisted product upload
feature. Kept isolated from views.py so the dashboard's CRUD logic doesn't
depend on network/API details.
"""
import base64
import json

import requests
from django.conf import settings

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

PROMPT = """You are helping a vendor on a Ghanaian e-commerce marketplace list \
a product. Look at the attached product photo and suggest a listing.

Respond with ONLY a JSON object (no markdown, no commentary) with exactly \
these keys:
- "name": a short, specific product title (max 10 words)
- "description": a 2-4 sentence marketing description, written for online \
shoppers in Ghana
- "category_guess": your best single-word-or-two guess at a general product \
category (e.g. "Electronics", "Clothing", "Kitchenware")
- "price_ghs": your best estimate of a fair retail price for this item in \
Ghanaian Cedis, as a plain number (no currency symbol, no commas). This is \
a rough starting-point estimate, not a final price.

If you cannot confidently identify the product, still return your best \
guess for every field rather than leaving any blank."""


class AIAnalysisError(Exception):
    """Raised when the Gemini API call fails or returns unusable data."""


# dashboard/ai.py — replace the analyze_product_image function's request-building section
def analyze_product_image(image_bytes, mime_type):
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise AIAnalysisError("GEMINI_API_KEY is not configured.")

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash-lite")
    url = GEMINI_ENDPOINT.format(model=model)

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4,
        },
    }

    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = ""
        if exc.response is not None:
            detail = f" — {exc.response.status_code}: {exc.response.text[:300]}"
        raise AIAnalysisError(f"Gemini request failed: {exc}{detail}") from exc

    try:
        data = response.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
        raise AIAnalysisError(f"Could not parse Gemini response: {exc}") from exc

    return _clean_result(parsed)


def _clean_result(parsed):
    """Validates/coerces the parsed JSON so bad AI output never reaches the form."""
    name = str(parsed.get("name") or "").strip()[:200]
    description = str(parsed.get("description") or "").strip()
    category_guess = str(parsed.get("category_guess") or "").strip()

    try:
        price = round(float(parsed.get("price_ghs")), 2)
        if price <= 0:
            price = None
    except (TypeError, ValueError):
        price = None

    if not name:
        raise AIAnalysisError("Gemini did not return a usable product name.")

    return {
        "name": name,
        "description": description,
        "category_guess": category_guess,
        "price_ghs": price,
    }