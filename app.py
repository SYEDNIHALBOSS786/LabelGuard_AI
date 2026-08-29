from flask import Flask, render_template, request, jsonify
import os
import re
import shutil
import subprocess
import tempfile

app = Flask(__name__)

ALLERGENS = {
    "Milk": [
        "milk", "milk solids", "whey", "casein",
        "lactose", "butter", "cream", "cheese"
    ],
    "Peanut": [
        "peanut", "groundnut", "peanut butter"
    ],
    "Soy": [
        "soy", "soya", "soybean", "soy lecithin"
    ],
    "Gluten": [
        "wheat", "wheat flour", "barley",
        "rye", "gluten", "maida"
    ],
    "Egg": [
        "egg", "eggs", "albumin", "ovalbumin"
    ],
    "Nuts": [
        "almond", "cashew", "walnut",
        "pistachio", "hazelnut"
    ]
}

WARNINGS = {
    "Sugar": [
        "sugar", "glucose syrup", "fructose",
        "maltose", "sucrose"
    ],
    "High Sodium": [
        "sodium", "salt"
    ],
    "Preservatives": [
        "preservative", "sodium benzoate",
        "potassium sorbate", "benzoate"
    ],
    "Artificial Colours": [
        "artificial colour", "artificial color",
        "tartrazine", "sunset yellow",
        "brilliant blue", "caramel colour"
    ]
}


def clean_text(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def analyze_label(text):
    original_text = text.strip()
    text = clean_text(text)

    allergens = []
    warnings = []

    for name, terms in ALLERGENS.items():
        for term in terms:
            if term in text:
                allergens.append(name)
                break

    for name, terms in WARNINGS.items():
        for term in terms:
            if term in text:
                warnings.append(name)
                break

    ingredients = [
        item.strip()
        for item in re.split(r",|;|\n", original_text)
        if item.strip()
    ]

    # Simple hackathon screening score
    score = 100
    score -= len(allergens) * 15
    score -= len(warnings) * 7
    score = max(0, min(100, score))

    if score >= 80:
        status = "Looks relatively clean"
    elif score >= 55:
        status = "Review before consuming"
    else:
        status = "Needs careful review"

    return {
        "score": score,
        "status": status,
        "allergens": allergens,
        "warnings": warnings,
        "ingredient_count": len(ingredients),
        "text": original_text
    }


def run_tesseract(image_path):
    """
    Try multiple OCR modes.
    Returns the longest useful OCR result.
    """

    results = []

    for psm in ["6", "11", "3"]:
        try:
            result = subprocess.run(
                [
                    "tesseract",
                    image_path,
                    "stdout",
                    "--psm",
                    psm,
                    "-l",
                    "eng"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                text = result.stdout.strip()

                if text:
                    results.append(text)

        except Exception:
            pass

    if not results:
        return ""

    # Usually the longest result contains more label text
    return max(results, key=len)


def preprocess_image(original):
    """
    ImageMagick is optional.
    If available, create a cleaner OCR image.
    """

    magick = shutil.which("magick")

    if not magick:
        return original

    processed = original + "_processed.png"

    try:
        result = subprocess.run(
            [
                magick,
                original,
                "-auto-orient",
                "-resize",
                "220%",
                "-colorspace",
                "Gray",
                "-contrast-stretch",
                "0x12%",
                "-sharpen",
                "0x1",
                processed
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and os.path.exists(processed):
            return processed

    except Exception:
        pass

    return original


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    text = data.get("text", "")

    if not text.strip():
        return jsonify({
            "error": "Please enter ingredient or label text."
        }), 400

    return jsonify(analyze_label(text))


@app.route("/ocr", methods=["POST"])
def ocr():
    if "image" not in request.files:
        return jsonify({
            "error": "No image selected."
        }), 400

    image = request.files["image"]

    if not image.filename:
        return jsonify({
            "error": "No image selected."
        }), 400

    original = None
    processed = None

    try:
        suffix = os.path.splitext(image.filename)[1].lower()

        if suffix not in [".jpg", ".jpeg", ".png", ".webp"]:
            suffix = ".jpg"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp:
            image.save(temp.name)
            original = temp.name

        processed = preprocess_image(original)

        text = run_tesseract(processed)

        # If processed image produced nothing, try original
        if not text and processed != original:
            text = run_tesseract(original)

        if not text:
            return jsonify({
                "error": (
                    "Could not read the label. "
                    "Take a closer, brighter and sharper photo."
                )
            }), 400

        return jsonify(analyze_label(text))

    except Exception as e:
        return jsonify({
            "error": "OCR processing failed: " + str(e)
        }), 500

    finally:
        if processed and processed != original:
            if os.path.exists(processed):
                os.remove(processed)

        if original and os.path.exists(original):
            os.remove(original)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
