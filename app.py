import os
from flask import Flask, request, jsonify, render_template
import google.generativeai as genai
from PIL import Image

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "message": "No image uploaded"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "message": "Empty file"}), 400

        file.seek(0)
        image = Image.open(file.stream)

        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Extract all printed text from this product label accurately. "
            "Include MRP, Net Quantity, Dates, Manufacturer details, and all visible text. "
            "Do not add extra explanation, only return the extracted text."
        )

        response = model.generate_content([prompt, image])
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
        return jsonify({
            "success": False,
            "message": "Could not read the label. Take a closer, brighter and sharper photo.",
            "error_detail": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
