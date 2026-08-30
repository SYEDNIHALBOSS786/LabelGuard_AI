import os
import io
import traceback
from flask import Flask, request, jsonify, render_template
from google import genai
from PIL import Image

app = Flask(__name__)

# Official Gemini Client
API_KEY = os.environ.get("GEMINI_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if not API_KEY:
            return jsonify({
                "success": False,
                "message": "GEMINI_API_KEY missing in Render environment variables."
            }), 500

        # Check all possible image keys from form data
        file = None
        for key in ["image", "file", "label_image", "upload"]:
            if key in request.files:
                file = request.files[key]
                break

        if not file or file.filename == "":
            return jsonify({
                "success": False,
                "message": "No valid image uploaded."
            }), 400

        file.seek(0)
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        # Init modern Gemini client
        client = genai.Client(api_key=API_KEY)
        
        prompt = (
            "Extract and transcribe all text printed on this product packaging label accurately. "
            "Include MRP, Net Quantity, Dates, Manufacturer details, Ingredients, and all visible text. "
            "Return only the extracted text without introductory phrases or markdown ticks."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, image]
        )

        extracted_text = response.text.strip() if response.text else ""

        if not extracted_text:
            return jsonify({
                "success": False,
                "message": "Could not read the label. Take a closer, brighter and sharper photo."
            }), 200

        return jsonify({
            "success": True,
            "text": extracted_text
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": "OCR Processing Failed.",
            "error_detail": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
