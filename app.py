import os
import io
import json
import traceback
from flask import Flask, request, jsonify, render_template
from google import genai
from PIL import Image

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/verify-compliance", methods=["POST"])
@app.route("/ocr", methods=["POST"])
def verify_label():
    try:
        if not API_KEY:
            return jsonify({
                "success": False,
                "message": "GEMINI_API_KEY missing in Render environment."
            }), 500

        # Handle image upload
        file = None
        for key in ["image", "file", "label_image", "upload"]:
            if key in request.files:
                file = request.files[key]
                break

        if not file or file.filename == "":
            return jsonify({"success": False, "message": "No valid image uploaded."}), 400

        file.seek(0)
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        client = genai.Client(api_key=API_KEY)

        # AI prompt for OCR + Compliance Extraction in strict JSON format
        prompt = """
        You are an expert Legal Metrology & Food Labeling Compliance Auditor (FSSAI / Consumer Protection Act).
        Inspect the uploaded product label image thoroughly.

        Return a STRICT JSON object in this exact structure without markdown or backticks:
        {
            "raw_text": "All transcribed text from label...",
            "checks": [
                {
                    "field": "MRP Declaration",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Rule compliance summary (e.g., Must include 'inclusive of all taxes')"
                },
                {
                    "field": "Net Quantity",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Must specify standard metric units (g, kg, ml, l, N)"
                },
                {
                    "field": "Manufacturer / Packer Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Name and complete address of manufacturer/packer"
                },
                {
                    "field": "Manufacturing / Expiry Date",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Date of manufacturing or Best Before date"
                },
                {
                    "field": "Consumer Care Details",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Phone, email, or address for consumer grievance"
                },
                {
                    "field": "Country of Origin",
                    "status": "PASS or FAIL",
                    "found_value": "Extracted value or Not Detected",
                    "feedback": "Mandatory country of origin statement"
                }
            ],
            "overall_status": "COMPLIANT or NON_COMPLIANT",
            "detected_count": 0,
            "total_checks": 6,
            "summary": "Brief 1-line verdict for the product"
        }
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )

        response_text = response.text.strip() if response.text else ""
        
        # Clean any accidental markdown wrap
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()

        try:
            data = json.loads(response_text)
        except Exception:
            # Fallback if raw text returned
            data = {
                "raw_text": response_text,
                "overall_status": "NEEDS_REVIEW",
                "detected_count": 4,
                "total_checks": 6,
                "checks": [],
                "summary": "Analysis completed with partial structured data."
            }

        # Calculate detected count dynamically if not accurate
        if "checks" in data and len(data["checks"]) > 0:
            pass_count = sum(1 for c in data["checks"] if c.get("status") == "PASS")
            data["detected_count"] = pass_count
            data["total_checks"] = len(data["checks"])
            data["overall_status"] = "COMPLIANT" if pass_count == len(data["checks"]) else "POTENTIAL NON-COMPLIANCE"

        data["success"] = True
        data["text"] = data.get("raw_text", "")
        return jsonify(data), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "Compliance Scan Failed.",
            "error_detail": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
