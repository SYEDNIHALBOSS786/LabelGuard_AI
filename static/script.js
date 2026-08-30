const imageInput = document.getElementById("imageInput");
const cameraInput = document.getElementById("cameraInput");
const galleryInput = document.getElementById("galleryInput");
const preview = document.getElementById("preview");

if (imageInput) {
    imageInput.addEventListener("change", function () {
        const file = this.files[0];

        if (!file) {
            preview.style.display = "none";
            return;
        }

        preview.src = URL.createObjectURL(file);
        preview.style.display = "block";

        const status = document.getElementById("ocrStatus");
        if (status) {
            status.textContent = "✅ Image ready.";
        }
    });
}

function openCamera() {
    cameraInput.click();
}

function openGallery() {
    galleryInput.click();
}

function handleSelectedImage(file) {
    if (!file) return;

    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    imageInput.files = dataTransfer.files;

    preview.src = URL.createObjectURL(file);
    preview.style.display = "block";

    const status = document.getElementById("ocrStatus");
    if (status) {
        status.textContent = "✅ Image ready. Tap Scan & Check Label.";
    }
}

cameraInput.addEventListener("change", function () {
    handleSelectedImage(this.files[0]);
});

galleryInput.addEventListener("change", function () {
    handleSelectedImage(this.files[0]);
});

function loadExample(number) {
    const box = document.getElementById("labelText");

    if (number === 1) {
        box.value = `MRP ₹99.00 (Incl. of all taxes)
Net Quantity 500 g
Manufactured by ABC Foods Pvt Ltd
Packed by ABC Foods Pvt Ltd
Date of Mfg: 08/2026
Consumer Care: 1800-123-4567`;
    } else {
        box.value = `MRP ₹149
Net Quantity 1 kg
Manufactured by Fresh Foods`;
    }

    clearError();
}

async function analyzeLabel() {
    const text = document.getElementById("labelText").value.trim();

    if (!text) {
        showError("Please enter packaged-product label text.");
        return;
    }

    await sendText(text);
}

async function sendText(text) {
    clearError();

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text: text})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Compliance analysis failed.");
        }

        displayResult(data);

    } catch (error) {
        showError(error.message);
    }
}

async function scanImage() {
    const input = document.getElementById("imageInput");
    const status = document.getElementById("ocrStatus");

    if (!input || !input.files || !input.files[0]) {
        showError("Please select a product label photo first.");
        return;
    }

    clearError();
    status.textContent = "🔄 Reading product label...";

    const formData = new FormData();
    formData.append("image", input.files[0]);

    try {
        const response = await fetch("/ocr", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "OCR failed.");
        }

        document.getElementById("labelText").value = data.text || "";
        status.textContent = "✅ Label text detected.";
        displayResult(data);

    } catch (error) {
        status.textContent = "";
        showError(error.message);
    }
}

function displayResult(data) {
    document.getElementById("score").textContent =
        data.score ?? "--";

    document.getElementById("status").textContent =
        data.status || "Result";

    document.getElementById("detectedCount").textContent =
        data.detected_count ?? 0;

    document.getElementById("totalChecks").textContent =
        data.total_checks ?? 0;

    document.getElementById("missingCount").textContent =
        data.missing ? data.missing.length : 0;

    document.getElementById("resultSummary").textContent =
        buildSummary(data);

    document.getElementById("extractedText").textContent =
        data.text || "No text available.";

    document.getElementById("analysisTime").textContent =
        data.analysis_time || "Screening completed";

    renderChecks(data.checks || []);
    renderMissing(data.missing || []);

    document.getElementById("result").classList.remove("hidden");

    document.getElementById("result").scrollIntoView({
        behavior: "smooth"
    });
}

function buildSummary(data) {
    const missing = data.missing ? data.missing.length : 0;

    if (missing === 0) {
        return "All configured declaration fields were detected. Verify the original package before final determination.";
    }

    return `${missing} declaration field(s) were not detected. Manual verification is recommended.`;
}

function renderChecks(checks) {
    const container = document.getElementById("checks");
    container.innerHTML = "";

    checks.forEach(check => {
        const row = document.createElement("div");
        row.className = "check-row";

        const name = document.createElement("div");
        name.className = "check-name";
        name.textContent = check.name;

        const status = document.createElement("div");
        status.className =
            check.status === "FOUND"
                ? "check-status found"
                : "check-status missing";

        status.textContent =
            check.status === "FOUND"
                ? "✓ FOUND"
                : "⚠ NOT DETECTED";

        row.appendChild(name);
        row.appendChild(status);

        if (check.evidence) {
            const evidence = document.createElement("div");
            evidence.className = "evidence";
            evidence.textContent = "Evidence: " + check.evidence;
            row.appendChild(evidence);
        }

        container.appendChild(row);
    });
}

function renderMissing(items) {
    const list = document.getElementById("missing");
    list.innerHTML = "";

    if (!items.length) {
        const li = document.createElement("li");
        li.textContent = "No configured fields were missing from the supplied text.";
        list.appendChild(li);
        return;
    }

    items.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item + " — manual verification required.";
        list.appendChild(li);
    });
}

function showError(message) {
    const error = document.getElementById("error");
    if (error) {
        error.textContent = message;
    }
}

function clearError() {
    const error = document.getElementById("error");
    if (error) {
        error.textContent = "";
    }
}
