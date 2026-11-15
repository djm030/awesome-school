// 신청 폼: 카카오 우편번호 검색 + fetch 로 DRF API 에 제출하고 결과를 같은 자리에서 보여 준다.
(() => {
  const form = document.getElementById("apply-form");
  const done = document.getElementById("apply-done");
  const button = form.querySelector("button[type=submit]");
  const formError = form.querySelector('[data-error-for="non_field_errors"]');

  document.getElementById("postcode-search").addEventListener("click", () => {
    new daum.Postcode({
      oncomplete(data) {
        form.postcode.value = data.zonecode;
        form.address.value = data.roadAddress || data.jibunAddress;
        form.address_detail.focus();
      },
    }).open();
  });

  const showErrors = (errors) => {
    form.querySelectorAll("[data-error-for]").forEach((el) => (el.textContent = ""));
    form.querySelectorAll("[aria-invalid]").forEach((el) => el.removeAttribute("aria-invalid"));
    let first = null;
    for (const [field, messages] of Object.entries(errors)) {
      (form.querySelector(`[data-error-for="${field}"]`) || formError).textContent = [].concat(messages).join(" ");
      const input = form.elements[field];
      const target = input instanceof RadioNodeList ? input[0] : input;
      if (target) {
        target.setAttribute("aria-invalid", "true");
        first ??= target;
      }
    }
    (first || formError).focus?.();
  };

  const showDone = (application) => {
    const [y, m, d] = application.contact_date.split("-").map(Number);
    const weekday = "일월화수목금토"[new Date(y, m - 1, d).getDay()];
    const slot = form.querySelector(`input[name=contact_slot][value="${application.contact_slot}"]`);
    const values = {
      ...application,
      contact_date: `${m}월 ${d}일(${weekday})`,
      contact_slot: slot.nextElementSibling.textContent.trim(),
    };
    done.querySelectorAll("[data-done]").forEach((el) => (el.textContent = values[el.dataset.done]));
    form.hidden = true;
    done.hidden = false;
    done.focus();
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries([...new FormData(form)].filter(([key, value]) => value !== "" && key !== "csrfmiddlewaretoken"));
    data.course = form.dataset.course;
    data.privacy_agreed = form.privacy_agreed.checked;

    button.disabled = true; // 중복 신청은 막지 않으므로 더블클릭만은 여기서 막는다
    button.textContent = "보내는 중…";
    try {
      const response = await fetch(form.dataset.api, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": form.csrfmiddlewaretoken.value },
        body: JSON.stringify(data),
      });
      const body = await response.json().catch(() => ({}));
      if (response.status === 201) return showDone(body);
      if (response.status === 400) return showErrors(body);
      showErrors({
        non_field_errors: response.status === 429
          ? "짧은 시간에 신청이 많았습니다. 잠시 후 다시 시도해 주세요."
          : "일시적인 오류입니다. 잠시 후 다시 시도해 주세요.",
      });
    } catch {
      showErrors({ non_field_errors: "네트워크 오류입니다. 연결을 확인하고 다시 시도해 주세요." });
    } finally {
      button.disabled = false;
      button.textContent = "신청하기";
    }
  });
})();
