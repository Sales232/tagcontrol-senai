document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("packing-volumes");
    const template = document.getElementById("packing-volume-template");
    const addButton = document.getElementById("add-volume");

    if (!container || !template || !addButton) {
        return;
    }

    const nextVolumeId = () => {
        const ids = Array.from(container.querySelectorAll('input[name="volume_id"]'))
            .map((input) => Number(input.value))
            .filter(Number.isInteger);
        return Math.max(0, ...ids) + 1;
    };

    addButton.addEventListener("click", () => {
        const volumeId = nextVolumeId();
        const markup = template.innerHTML.replace(/__INDEX__/g, String(volumeId));
        container.insertAdjacentHTML("beforeend", markup);
        const cards = container.querySelectorAll("[data-volume-card]");
        cards[cards.length - 1].querySelector("legend").textContent = `Volume ${cards.length}`;
    });

    container.addEventListener("click", (event) => {
        const removeButton = event.target.closest("[data-remove-volume]");
        if (!removeButton || container.querySelectorAll("[data-volume-card]").length <= 1) {
            return;
        }

        removeButton.closest("[data-volume-card]").remove();
        container.querySelectorAll("[data-volume-card] legend").forEach((legend, index) => {
            legend.textContent = `Volume ${index + 1}`;
        });
    });
});
