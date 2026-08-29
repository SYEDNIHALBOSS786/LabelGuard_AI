const imageInput = document.getElementById("imageInput");
const preview = document.getElementById("preview");

if (imageInput) {
    imageInput.addEventListener("change", function () {
        const file = this.files[0];

        if (!file) {
            preview.style.display = "none";
            return;
        }

        const reader = new FileReader();

        reader.onload = function (event) {
            preview.src = event.target.result;
            preview.style.display = "block";
        };

        reader.readAsDataURL(file);
    });
}
