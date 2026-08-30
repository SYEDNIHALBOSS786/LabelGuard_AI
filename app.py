import os
import json
import re
import traceback
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types

app = Flask(__name__)

RAW_KEY = os.environ.get("GEMINI_API_KEY", "")
API_KEY = RAW_KEY.strip().strip('"').strip("'")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ocr", methods=["POST"])
@app.route("/api/verify-compliance", methods=["POST"])
def process_ocr():
    try:
        if not API_KEY:
            return jsonify({
                "success": False,
                "message": "GEMINI_API_KEY environment variable is missing on Render."
            }), 500

        client = genai.Client(api_key=API_KEY)

        prompt_instruction = """
        You are an expert Legal Metrology, FSSAI Packaging Compliance & Food Safety Auditor.
        Analyze the packaging label details (from the provided image or text) and verify both Legal Compliance and Health/Safety Warnings.

        Return ONLY a JSON object with this exact structure:
        {
            "raw_text": "Complete transcribed label text here...",
            "checks": [
                {
                    "field": "MRP Declaration",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted MRP string or Not Detected",
                    "feedback": "Must state inclusive of all taxes"
                },
                {
                    "field": "Net Quantity",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Net Qty or Not Detected",
                    "feedback": "Declared in standard metric unit"
                },
                {
                    "field": "Manufacturer Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Name & Address or Not Detected",
                    "feedback": "Full manufacturer name and address required"
                },
                {
                    "field": "Mfg / Expiry Date",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Dates or Not Detected",
                    "feedback": "Date of manufacturing or Best Before/Expiry"
                },
                {
                    "field": "Consumer Care Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted contact or Not Detected",
                    "feedback": "Customer care number/email mandatory"
                },
                {
                    "field": "Country of Origin",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Country or Not Detected",
                    "feedback": "Country of origin declaration"
                }
            ],
            "health_safety": {
                "allergens": ["List of detected allergens like Nuts, Dairy, Gluten, Soy or 'None Detected'"],
                "preservatives_additives": ["List of detected INS numbers, artificial colors, preservatives or 'Standard/None'"],
                "sugar_level": "HIGH / MODERATE / LOW / NOT_MENTIONED",
                "sodium_level": "HIGH / MODERATE / LOW / NOT_MENTIONED",
                "health_warning": "Clear brief health summary (e.g. High in added sugars, contains allergens: Peanuts)."
            },
            "overall_status": "COMPLIANT or NON_COMPLIANCE",
            "summary": "Brief overall verdict"
        }
        """

        raw_input_text = request.form.get("text_input", "").strip()

        if raw_input_text:
            contents_payload = [
                prompt_instruction,
                f"Verify this label text:\n{raw_input_text}"
            ]
        else:
            file = None
            for key in ["image", "file", "label_image", "upload"]:
                if key in request.files:
                    file = request.files[key]
                    break

            if not file or file.filename == "":
                return jsonify({
                    "success": False,
                    "message": "No image uploaded or text provided."
                }), 400

            file.seek(0)
            image_bytes = file.read()
            mime_type = file.mimetype or "image/jpeg"
            if mime_type not in ["image/jpeg", "image/png", "image/webp"]:
                mime_type = "image/jpeg"

            contents_payload = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt_instruction
            ]

        config = types.GenerateContentConfig(
            response_mime_type="application/json"
        )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=contents_payload,
            config=config
        )

        res_text = response.text.strip() if response.text else "{}"

        if "```" in res_text:
            res_text = re.sub(r"^```[a-zA-Z]*\n?", "", res_text)
            res_text = re.sub(r"```$", "", res_text).strip()

        try:
            data = json.loads(res_text)
        except Exception:
            data = {
                "raw_text": raw_input_text if raw_input_text else res_text,
                "checks": [],
                "health_safety": {
                    "allergens": ["None Detected"],
                    "preservatives_additives": ["None"],
                    "sugar_level": "NOT_MENTIONED",
                    "sodium_level": "NOT_MENTIONED",
                    "health_warning": "Could not analyze nutritional parameters."
                },
                "overall_status": "COMPLIANT"
            }

        checks = data.get("checks", [])
        pass_count = sum(1 for c in checks if str(c.get("status", "")).upper() == "PASS")
        total_checks = len(checks) if checks else 6

        return jsonify({
            "success": True,
            "text": data.get("raw_text", raw_input_text),
            "checks": checks,
            "health_safety": data.get("health_safety", {}),
            "detected_count": pass_count,
            "total_checks": total_checks,
            "status": "COMPLIANT" if pass_count >= 5 else "POTENTIAL NON-COMPLIANCE",
            "summary": data.get("summary", "")
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"Processing Error: {str(e)}"
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
