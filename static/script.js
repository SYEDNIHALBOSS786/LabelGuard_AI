const imageInput = document.getElementById("imageInput");
const preview = document.getElementById("preview");

imageInput.addEventListener("change", function () {

    const file = this.files[0];

    if (!file) {
        preview.style.display = "none";
        return;
    }

    const url = URL.createObjectURL(file);

    preview.src = url;
    preview.style.display = "block";
});


function loadExample(number) {

    const box = document.getElementById("labelText");

    if (number === 1) {

        box.value =
            "rice flour, chickpea flour, sunflower oil, spices, salt";

    } else {

        box.value =
            "wheat flour, sugar, milk solids, soy lecithin, salt, sodium benzoate";

    }
}


async function analyzeLabel() {

    const text =
        document.getElementById("labelText").value.trim();

    if (!text) {

        showError(
            "Please enter ingredient or label text."
        );

        return;
    }

    await sendText(text);
}


async function sendText(text) {

    clearError();

    try {

        const response = await fetch(
            "/analyze",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    text: text
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.error || "Analysis failed."
            );
        }

        displayResult(data);

    } catch (error) {

        showError(error.message);

    }
}


async function scanImage() {

    const input =
        document.getElementById("imageInput");

    const status =
        document.getElementById("ocrStatus");

    if (!input.files || !input.files[0]) {

        showError(
            "Please select or take a label photo first."
        );

        return;
    }

    clearError();

    const formData = new FormData();

    formData.append(
        "image",
        input.files[0]
    );

    status.textContent =
        "🔄 Reading food label...";

    try {

        const response = await fetch(
            "/ocr",
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!response.ok) {

            throw new Error(
                data.error || "OCR failed."
            );

        }

        document.getElementById(
            "labelText"
        ).value = data.text;

        status.textContent =
            "✅ Label text detected.";

        displayResult(data);

    } catch (error) {

        status.textContent = "";

        showError(error.message);

    }
}


function displayResult(data) {

    document.getElementById(
        "score"
    ).textContent = data.score;

    document.getElementById(
        "status"
    ).textContent = data.status;

    document.getElementById(
        "ingredientCount"
    ).textContent = data.ingredient_count;

    document.getElementById(
        "extractedText"
    ).textContent =
        data.text || "No text available.";

    renderList(
        "allergens",
        data.allergens
    );

    renderList(
        "warnings",
        data.warnings
    );

    document
        .getElementById("result")
        .classList.remove("hidden");
}


function renderList(id, items) {

    const list =
        document.getElementById(id);

    list.innerHTML = "";

    if (!items || items.length === 0) {

        const li =
            document.createElement("li");

        li.textContent =
            "None detected";

        list.appendChild(li);

        return;
    }

    items.forEach(item => {

        const li =
            document.createElement("li");

        li.textContent = item;

        list.appendChild(li);

    });
}


function showError(message) {

    document.getElementById(
        "error"
    ).textContent = message;
}


function clearError() {

    document.getElementById(
        "error"
    ).textContent = "";

}
