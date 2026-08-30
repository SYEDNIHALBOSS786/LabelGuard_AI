import os
import json
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
                "message": "GEMINI_API_KEY environment variable missing on Render."
            }), 500

        file = None
        for key in ["image", "file", "label_image", "upload"]:
            if key in request.files:
                file = request.files[key]
                break

        if not file or file.filename == "":
            return jsonify({
                "success": False,
                "message": "No image file provided."
            }), 400

        file.seek(0)
        image_bytes = file.read()
        mime_type = file.mimetype or "image/jpeg"
        if mime_type not in ["image/jpeg", "image/png", "image/webp"]:
            mime_type = "image/jpeg"

        client = genai.Client(api_key=API_KEY)

        prompt = """
        You are an expert Legal Metrology & FSSAI Packaging Compliance Auditor.
        Read this product packaging label image and extract all text and audit mandatory fields.

        Return ONLY a JSON object (no markdown fences, no backticks) with this exact schema:
        {
            "raw_text": "All transcribed label text...",
            "checks": [
                {
                    "field": "MRP Declaration",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted MRP string or Not Detected",
                    "feedback": "Must state 'inclusive of all taxes'"
                },
                {
                    "field": "Net Quantity",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Net Qty or Not Detected",
                    "feedback": "Must use standard metric units (g, kg, ml, l)"
                },
                {
                    "field": "Manufacturer / Packer Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Name & Address or Not Detected",
                    "feedback": "Full manufacturer/packer identity and address"
                },
                {
                    "field": "Manufacturing / Expiry Date",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Dates or Not Detected",
                    "feedback": "Date of manufacturing or Best Before date"
                },
                {
                    "field": "Consumer Care Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Customer care or Not Detected",
                    "feedback": "Customer care number/email mandatory"
                },
                {
                    "field": "Country of Origin",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted Country or Not Detected",
                    "feedback": "Country of origin declaration"
                }
            ],
            "overall_status": "COMPLIANT or NON_COMPLIANCE",
            "summary": "Brief verdict"
        }
        """

        # Using the active model: gemini-3.6-flash
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ]
        )

        res_text = response.text.strip() if response.text else ""

        if "```" in res_text:
            res_text = res_text.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(res_text)
        except Exception:
            data = {
                "raw_text": res_text,
                "checks": [],
                "overall_status": "COMPLIANT"
            }

        checks = data.get("checks", [])
        pass_count = sum(1 for c in checks if c.get("status") == "PASS")
        total_checks = len(checks) if checks else 6

        return jsonify({
            "success": True,
            "text": data.get("raw_text", ""),
            "checks": checks,
            "detected_count": pass_count,
            "total_checks": total_checks,
            "status": "COMPLIANT" if pass_count >= 5 else "POTENTIAL NON-COMPLIANCE",
            "summary": data.get("summary", "")
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": f"AI Processing Error: {str(e)}"
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
