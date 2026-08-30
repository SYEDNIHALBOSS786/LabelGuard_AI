from flask import Flask, render_template, request, jsonify
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime

app = Flask(__name__)

# SIH26034 — Packaged Commodity Compliance Assistant
#
# This is a screening tool, not a legal determination.
# It checks whether expected declaration text can be detected
# from the supplied label text/image.

CHECKS = {
    "MRP": [
        r"\bm\.?\s*r\.?\s*p\.?\b",
        r"maximum retail price",
        r"retail price"
    ],
    "Net Quantity": [
        r"net\s*(qty|quantity|wt|weight|volume)",
        r"net\s*w?t\.?",
        r"\b\d+(?:\.\d+)?\s*(g|kg|mg|ml|l|litre|liter)\b"
    ],
    "Manufacturer / Packer": [
        r"manufactured by",
        r"manufactured\s*&?\s*packed by",
        r"manufactured\s*and\s*packed by",
        r"packed by",
        r"manufacturer",
        r"packer"
    ],
    "Importer": [
        r"imported by",
        r"importer",
        r"imported\s*&?\s*marketed by",
        r"imported\s*and\s*marketed by"
    ],
    "Date": [
        r"date of manufacture",
        r"date of mfg",
        r"mfg\.?\s*date",
        r"manufacturing date",
        r"packed on",
        r"packing date",
        r"date of packing",
        r"date of import",
        r"import date"
    ],
    "Consumer Care": [
        r"consumer care",
        r"consumer\s*complaint",
        r"customer care",
        r"customer\s*care",
        r"toll[-\s]?free",
        r"helpline",
        r"care@",
        r"contact us"
    ]
}


def clean_text(text):
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matches(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def analyze_compliance(text):
    original_text = text.strip()

    if not original_text:
        return {
            "error": "No readable label text was found."
        }

    cleaned = clean_text(original_text)

    checks = []
    found_count = 0

    for name, patterns in CHECKS.items():
        match = find_matches(cleaned, patterns)

        if match:
            found_count += 1
            checks.append({
                "name": name,
                "status": "FOUND",
                "evidence": match
            })
        else:
            checks.append({
                "name": name,
                "status": "NOT DETECTED",
                "evidence": ""
            })

    total = len(checks)
    score = round((found_count / total) * 100)

    missing = [
        item["name"]
        for item in checks
        if item["status"] == "NOT DETECTED"
    ]

    if score >= 85:
        status = "LIKELY COMPLIANT — VERIFY"
    elif score >= 60:
        status = "PARTIAL — MANUAL REVIEW REQUIRED"
    else:
        status = "POTENTIAL NON-COMPLIANCE"

    return {
        "score": score,
        "status": status,
        "checks": checks,
        "missing": missing,
        "detected_count": found_count,
        "total_checks": total,
        "text": original_text,
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "disclaimer": (
            "Screening result only. Presence of text does not by itself "
            "prove legal compliance. Final verification should be done "
            "against the applicable Legal Metrology requirements."
        )
    }


def run_tesseract(image_path):
    import os
    import requests

    api_key = os.getenv("OCR_SPACE_API_KEY")

    if not api_key:
        print("OCR API KEY: NOT SET")
        return ""

    print("OCR API KEY: SET")

    try:
        with open(image_path, "rb") as f:
            response = requests.post(
                "https://api.ocr.space/parse/image",
                files={"filename": f},
                data={
                    "apikey": api_key,
                    "language": "eng",
                    "isOverlayRequired": "false",
                    "OCREngine": "2",
                    "scale": "true"
                },
                timeout=60
            )

        if response.status_code != 200:
            print("OCR API HTTP error:", response.status_code, response.text[:500])
            return ""

        data = response.json()

        if data.get("IsErroredOnProcessing"):
            print("OCR API processing error:", data.get("ErrorMessage"))
            return ""

        parsed = data.get("ParsedResults", [])

        if not parsed:
            return ""

        return "\n".join(
            item.get("ParsedText", "")
            for item in parsed
        ).strip()

    except Exception as e:
        print("OCR API exception:", type(e).__name__, str(e))
        return ""

def preprocess_image(original):
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
                "250%",
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
            "error": "Please enter packaged-product label text."
        }), 400

    return jsonify(analyze_compliance(text))


@app.route("/ocr", methods=["POST"])
def ocr():
    if "image" not in request.files:
        return jsonify({
            "error": "No label image selected."
        }), 400

    image = request.files["image"]

    if not image.filename:
        return jsonify({
            "error": "No label image selected."
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

        processed = original

        text = run_tesseract(original)

        if not text and processed != original:
            text = run_tesseract(original)

        if not text:
            return jsonify({
                "error": (
                    "Could not read the label. "
                    "Take a closer, brighter and sharper photo."
                )
            }), 400

        return jsonify(analyze_compliance(text))

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
