import os
from flask import Flask, request, jsonify, render_template_string
from PIL import Image, ImageEnhance
import pytesseract

app = Flask(__name__)

# Tesseract setup for Termux
TESSDATA_PREFIX = "/data/data/com.termux/files/usr/share/tessdata"
os.environ["TESSDATA_PREFIX"] = TESSDATA_PREFIX
TESSERACT_PATH = "/data/data/com.termux/files/usr/bin/tesseract"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    pytesseract.pytesseract.tesseract_cmd = "tesseract"

def preprocess_image(image):
    gray = image.convert("L")
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.0)
    threshold = 140
    return enhanced.point(lambda p: 255 if p > threshold else 0)

# 1. Homepage Route (Isse Not Found error nahi aayega)
@app.route("/")
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LabelGuard AI - Local</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: sans-serif; background: #121212; color: #fff; padding: 20px; text-align: center; }
            .card { background: #1e1e1e; padding: 20px; border-radius: 10px; max-width: 400px; margin: auto; }
            input, button { width: 100%; padding: 12px; margin-top: 15px; border-radius: 6px; box-sizing: border-box; }
            button { background: #2563eb; color: #fff; border: none; font-weight: bold; }
            pre { background: #000; padding: 10px; text-align: left; white-space: pre-wrap; word-wrap: break-word; border-radius: 6px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>LabelGuard OCR</h2>
            <input type="file" id="imageInput" accept="image/*">
            <button onclick="scanImage()">Scan Image</button>
            <h4 id="status"></h4>
            <pre id="output"></pre>
        </div>

        <script>
            async function scanImage() {
                const input = document.getElementById('imageInput');
                const status = document.getElementById('status');
                const output = document.getElementById('output');
                
                if(!input.files[0]) {
                    alert('Select an image first!');
                    return;
                }
                
                status.innerText = "Scanning label...";
                output.innerText = "";
                
                const formData = new FormData();
                formData.append('image', input.files[0]);
                
                try {
                    const res = await fetch('/ocr', { method: 'POST', body: formData });
                    const data = await res.json();
                    
                    if(data.success) {
                        status.innerText = "Scan Successful ✅";
                        output.innerText = data.text;
                    } else {
                        status.innerText = "Error ❌";
                        output.innerText = data.message + (data.error_detail ? "\\n" + data.error_detail : "");
                    }
                } catch(e) {
                    status.innerText = "Request Failed ❌";
                    output.innerText = e.message;
                }
            }
        </script>
    </body>
    </html>
    """)

# 2. OCR API Route
@app.route("/ocr", methods=["POST"])
def process_ocr():
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "message": "No image uploaded"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "message": "Empty file"}), 400

        file.seek(0)
        raw_image = Image.open(file.stream)

        # Attempt OCR
        processed_img = preprocess_image(raw_image)
        extracted_text = pytesseract.image_to_string(processed_img, config=r"--oem 3 --psm 6")

        if not extracted_text.strip():
            extracted_text = pytesseract.image_to_string(raw_image.convert("RGB"), config=r"--oem 3 --psm 3")

        if not extracted_text.strip():
            return jsonify({
                "success": False,
                "message": "Could not read the label. Take a closer, brighter and sharper photo."
            }), 200

        return jsonify({"success": True, "text": extracted_text.strip()}), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": "OCR Processing Failed",
            "error_detail": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
