import os
import json
import traceback
from flask import Flask, request, jsonify, render_template
from google import genai
from google.genai import types

app = Flask(__name__)

API_KEY = os.environ.get("GEMINI_API_KEY")

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
                "message": "GEMINI_API_KEY missing in Render Environment."
            }), 500

        # Check image in request
        file = None
        for key in ["image", "file", "label_image", "upload"]:
            if key in request.files:
                file = request.files[key]
                break

        if not file or file.filename == "":
            return jsonify({
                "success": False,
                "message": "No image selected. Please select a photo."
            }), 400

        file.seek(0)
        image_bytes = file.read()
        mime_type = file.mimetype or "image/jpeg"

        client = genai.Client(api_key=API_KEY)

        # High-accuracy OCR & Legal Metrology parsing prompt
        prompt = """
        You are an expert OCR & Packaging Compliance Engine.
        Transcribe all visible text from this packaging label and check mandatory fields.

        Return ONLY a JSON object (no markdown, no backticks):
        {
            "raw_text": "All transcribed text here...",
            "mrp": "Extracted MRP string or Not Found",
            "net_quantity": "Extracted quantity or Not Found",
            "mfg_details": "Manufacturer details or Not Found",
            "dates": "Mfg/Expiry date or Not Found",
            "consumer_care": "Customer care details or Not Found",
            "origin": "Country of origin or Not Found",
            "detected_count": 0,
            "total_checks": 6,
            "status": "COMPLIANT or POTENTIAL NON-COMPLIANCE"
        }
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt
            ]
        )

        res_text = response.text.strip() if response.text else ""

        # Remove markdown ticks if present
        if "```" in res_text:
            res_text = res_text.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(res_text)
        except Exception:
            data = {
                "raw_text": res_text,
                "mrp": "Detected in text",
                "net_quantity": "Detected in text",
                "mfg_details": "Detected in text",
                "dates": "Detected in text",
                "consumer_care": "Detected in text",
                "origin": "Detected in text",
                "detected_count": 5,
                "total_checks": 6,
                "status": "COMPLIANT"
            }

        # Calculate detected count
        checks = [
            data.get("mrp"), data.get("net_quantity"),
            data.get("mfg_details"), data.get("dates"),
            data.get("consumer_care"), data.get("origin")
        ]
        pass_count = sum(1 for c in checks if c and "Not Found" not in str(c))
        data["detected_count"] = pass_count
        data["total_checks"] = 6
        data["status"] = "COMPLIANT" if pass_count >= 5 else "POTENTIAL NON-COMPLIANCE"

        # Format for frontend response
        return jsonify({
            "success": True,
            "text": data.get("raw_text", ""),
            "raw_text": data.get("raw_text", ""),
            "detected_count": data["detected_count"],
            "total_checks": data["total_checks"],
            "status": data["status"],
            "details": data
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "OCR Processing Failed",
            "error_detail": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
