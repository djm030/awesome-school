(() => {
  const postcodeButton = document.getElementById("postcode-search");
  postcodeButton?.addEventListener("click", () => {
    const form = postcodeButton.form;
    new daum.Postcode({
      oncomplete: (data) => {
        form.postcode.value = data.zonecode;
        form.address.value = data.roadAddress || data.jibunAddress;
        form.address_detail.focus();
      },
    }).open();
  });

  for (const button of document.querySelectorAll("[data-add-row]")) {
    const prefix = button.dataset.addRow;
    button.addEventListener("click", () => {
      const total = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
      const html = document.getElementById(`${prefix}-template`).innerHTML.replaceAll("__prefix__", total.value);
      document.getElementById(`${prefix}-rows`).insertAdjacentHTML("beforeend", html);
      total.value = Number(total.value) + 1;
    });
  }
})();
