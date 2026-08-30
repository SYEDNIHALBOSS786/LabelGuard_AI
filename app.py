import os
import json
import re
import traceback
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

RAW_KEY = os.environ.get("GEMINI_API_KEY", "")
API_KEY = RAW_KEY.strip().strip('"').strip("'")

@app.errorhandler(Exception)
def handle_all_exceptions(e):
    traceback.print_exc()
    return jsonify({
        "success": False,
        "message": f"Server Notice: {str(e)}"
    }), 200

def clean_json_response(raw_resp):
    if not raw_resp:
        return {}
    clean = re.sub(r"^```[a-zA-Z]*\n?|```$", "", raw_resp.strip()).strip()
    try:
        return json.loads(clean)
    except Exception:
        match = re.search(r'(\{[\s\S]*\})', clean)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health-check")
def health():
    return jsonify({
        "status": "ONLINE",
        "key_configured": bool(API_KEY and len(API_KEY) > 10)
    }), 200

@app.route("/ocr", methods=["POST"])
@app.route("/api/verify-compliance", methods=["POST"])
def process_ocr():
    try:
        if not API_KEY:
            return jsonify({"success": False, "message": "GEMINI_API_KEY missing in Render environment."}), 200

        client = genai.Client(api_key=API_KEY)

        prompt_instruction = """
        You are an elite FSSAI, Legal Metrology & Chemical Food Safety Auditor AI.
        Analyze this packaging label with deep ingredient and legal inspection.

        1. ALLERGENS: Identify ALL allergen items (e.g. Wheat, Gluten, Oats, Sesame, Soy, Milk/Dairy, Nuts, Peanuts, Eggs, Fish).
        2. HARMFUL CHEMICALS & PRESERVATIVES: Extract all INS numbers, artificial colors (e.g. Tartrazine, Red 40), chemical preservatives (e.g. INS 211, BHA/BHT, INS 220), raising agents (INS 500, INS 503), emulsifiers (INS 322).
        3. HARMFUL INGREDIENTS DETECTION: Flag high Palm oil, Trans fats, Invert sugar, High Fructose Corn Syrup, Excess MSG/E621.
        4. NUTRITION: Classify Sugar and Sodium levels (HIGH / MODERATE / LOW).
        5. LEGAL METROLOGY (6 Rules): Extract exact MRP (with tax mention), Net Quantity, Manufacturer details, Mfg/Expiry dates, Customer Care, and Country of Origin.

        Return ONLY a JSON object:
        {
            "raw_text": "Complete OCR transcribed label text...",
            "compliance_score": 100,
            "overall_status": "COMPLIANT",
            "summary": "Compliance and chemical/health safety summary",
            "checks": [
                {"field": "MRP Declaration", "status": "PASS", "found_value": "Exact MRP", "feedback": "Inclusive of all taxes verified."},
                {"field": "Net Quantity", "status": "PASS", "found_value": "Exact Net Wt", "feedback": "Standard metric unit verified."},
                {"field": "Manufacturer Details", "status": "PASS", "found_value": "Name & Address", "feedback": "Full details present."},
                {"field": "Manufacturing & Expiry", "status": "PASS", "found_value": "Mfg & Expiry dates", "feedback": "Valid dates found."},
                {"field": "Consumer Care", "status": "PASS", "found_value": "Helpline/Email", "feedback": "Customer contact details verified."},
                {"field": "Country of Origin", "status": "PASS", "found_value": "Origin Country", "feedback": "Country of origin declared."}
            ],
            "health_safety": {
                "allergens": ["List of detected allergens"],
                "preservatives": ["List of all INS codes, raising agents & additives found"],
                "harmful_substances": ["List any flagged harmful additives, palm oil, artificial colors, or 'None Detected'"],
                "sugar_level": "MODERATE",
                "sodium_level": "LOW",
                "health_warning": "Clear summary of health, allergen, and chemical risks."
            }
        }
        """

        raw_input_text = request.form.get("text_input", "").strip()

        if raw_input_text:
            contents_payload = [prompt_instruction, f"Audit text:\n{raw_input_text}"]
        else:
            file = request.files.get("image") or request.files.get("file")
            if not file or not file.filename:
                return jsonify({"success": False, "message": "No image uploaded."}), 200

            image_bytes = file.read()
            mime_type = file.mimetype or "image/jpeg"
            if "png" in mime_type:
                mime_type = "image/png"
            elif "webp" in mime_type:
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            contents_payload = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt_instruction
            ]

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0
        )

        # Multi-model cascade: gemini-3.6-flash with seamless failovers
        candidate_models = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        res_text = ""
        last_error = ""

        for model_id in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_id,
                    contents=contents_payload,
                    config=config
                )
                if response and response.text:
                    res_text = response.text.strip()
                    break
            except Exception as e:
                last_error = str(e)
                continue

        if not res_text:
            return jsonify({
                "success": False,
                "message": f"AI Engine Notice: {last_error}"
            }), 200

        data = clean_json_response(res_text)
        checks = data.get("checks", [])
        pass_count = sum(1 for c in checks if str(c.get("status", "")).upper() == "PASS")

        return jsonify({
            "success": True,
            "text": data.get("raw_text", raw_input_text or "Label scanned successfully."),
            "checks": checks,
            "health_safety": data.get("health_safety", {}),
            "detected_count": pass_count,
            "total_checks": len(checks) if checks else 6,
            "status": "COMPLIANT" if pass_count >= 5 else "POTENTIAL NON-COMPLIANCE",
            "summary": data.get("summary", "Audit completed.")
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Engine Error: {str(e)}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
