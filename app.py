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
            return jsonify({"success": False, "message": "GEMINI_API_KEY environment variable missing on Render."}), 200

        client = genai.Client(api_key=API_KEY)

        prompt_instruction = """
        You are an expert FSSAI & Legal Metrology Auditor AI.
        Analyze this packaging label image/text with extreme precision.

        TASK 1: Extract ALL allergens mentioned (check 'Contains', 'May contain traces of', 'Warning', and ingredient list like Wheat, Oats, Sesame, Soy, Milk, Nuts, Peanuts).
        TASK 2: Extract ALL preservatives, raising agents, and INS numbers (e.g. INS 500(ii), INS 503(ii), INS 322).
        TASK 3: Extract exact Sugar and Sodium values per 100g/serving and classify level (HIGH/MODERATE/LOW).
        TASK 4: Verify 6 Legal Metrology declarations with EXACT extracted text.

        Return ONLY a raw JSON object with this exact schema:
        {
            "raw_text": "Complete transcribed label text...",
            "compliance_score": 100,
            "overall_status": "COMPLIANT",
            "summary": "Clear summary of compliance and identified allergen risks",
            "checks": [
                {
                    "field": "MRP Declaration",
                    "status": "PASS",
                    "found_value": "Exact MRP (e.g. ₹ 120.00 Incl. of all taxes)",
                    "feedback": "Compliant with Legal Metrology rules."
                },
                {
                    "field": "Net Quantity",
                    "status": "PASS",
                    "found_value": "Exact Net Wt (e.g. 240g)",
                    "feedback": "Declared in standard metric unit."
                },
                {
                    "field": "Manufacturer Details",
                    "status": "PASS",
                    "found_value": "Full name and address",
                    "feedback": "Complete manufacturer details present."
                },
                {
                    "field": "Manufacturing & Expiry",
                    "status": "PASS",
                    "found_value": "Mfg Date & Use By Date",
                    "feedback": "Clear dates found."
                },
                {
                    "field": "Consumer Care",
                    "status": "PASS",
                    "found_value": "Helpline, Email, Timings",
                    "feedback": "Grievance redressal info verified."
                },
                {
                    "field": "Country of Origin",
                    "status": "PASS",
                    "found_value": "Country name (e.g. India)",
                    "feedback": "Country of origin explicitly declared."
                }
            ],
            "health_safety": {
                "allergens": ["List every detected allergen, e.g. Wheat, Oats, Sesame, Soy, Milk, Nuts, Peanut"],
                "preservatives": ["List all INS codes, e.g. INS 500(ii), INS 503(ii), INS 322"],
                "sugar_level": "MODERATE",
                "sodium_level": "LOW",
                "health_warning": "Specific warning highlighting the detected allergens and ingredients."
            }
        }
        """

        raw_input_text = request.form.get("text_input", "").strip()

        if raw_input_text:
            contents_payload = [prompt_instruction, f"Analyze this label text:\n{raw_input_text}"]
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

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents_payload,
            config=config
        )

        res_text = response.text.strip() if response and response.text else "{}"
        data = clean_json_response(res_text)

        if not data or "checks" not in data:
            return jsonify({
                "success": False,
                "message": "AI could not parse label details. Please retry with better lighting."
            }), 200

        checks = data.get("checks", [])
        pass_count = sum(1 for c in checks if str(c.get("status", "")).upper() == "PASS")

        return jsonify({
            "success": True,
            "text": data.get("raw_text", ""),
            "checks": checks,
            "health_safety": data.get("health_safety", {}),
            "detected_count": pass_count,
            "total_checks": len(checks) or 6,
            "status": "COMPLIANT" if pass_count >= 5 else "POTENTIAL NON-COMPLIANCE",
            "summary": data.get("summary", "Audit completed.")
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Engine Notice: {str(e)}"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
