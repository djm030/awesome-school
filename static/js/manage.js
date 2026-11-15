(() => {
  const root = document.getElementById("manage");
  const csrf = root.querySelector("[name=csrfmiddlewaretoken]").value;
  const filters = document.getElementById("filters");
  const tbody = root.querySelector("tbody");
  const rowTemplate = document.getElementById("row-template");
  const message = document.getElementById("status-message");
  const dialog = document.getElementById("memo-dialog");
  const { api, exportApi, adminUrl, login, today } = root.dataset;

  const say = (text) => (message.textContent = text);

  async function request(url, options = {}) {
    const response = await fetch(url, {
      ...options,
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
    });
    if (response.status === 403) {
      location.href = login; // staff 세션이 끝났거나 권한이 없으면 로그인 화면으로 보낸다
      throw new Error("다시 로그인해 주세요.");
    }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(Object.values(body).flat().join(" ") || `오류가 났습니다 (${response.status}).`);
    return body;
  }

  function renderRow(application) {
    const row = rowTemplate.content.firstElementChild.cloneNode(true);
    const set = (field, text) => (row.querySelector(`[data-field=${field}]`).textContent = text);
    set("created_at", application.created_at.slice(0, 16).replace("T", " "));
    set("organization", application.organization);
    set("name", application.name);
    set("address", `${application.address} ${application.address_detail}`.trim());
    set("phone", application.phone);
    set("email", application.email);
    set("contact_date", application.contact_date);
    set("contact_slot", application.contact_slot_display);
    set("memo", application.memo);
    row.classList.toggle("is-today", application.contact_date === today);
    row.classList.toggle("is-closed", ["done", "cancelled"].includes(application.status));
    row.querySelector("[data-duplicate]").hidden = !application.is_duplicate;
    row.querySelector("[data-admin]").href = adminUrl.replace("/0/", `/${application.id}/`);

    const select = row.querySelector("select");
    select.value = application.status;
    select.addEventListener("change", () => save(application, { status: select.value }));
    row.querySelector("[data-memo]").addEventListener("click", () => editMemo(application));
    return row;
  }

  async function load() {
    const params = new URLSearchParams([...new FormData(filters)].filter(([, value]) => value));
    say("불러오는 중…");
    try {
      const applications = await request(`${api}?${params}`);
      tbody.replaceChildren(...applications.map(renderRow));
      say(applications.length ? `${applications.length}건` : "조건에 맞는 신청이 없습니다.");
    } catch (error) {
      say(error.message);
    }
  }

  async function save(application, changes) {
    try {
      await request(`${api}${application.id}/`, { method: "PATCH", body: JSON.stringify(changes) });
      await load(); // 상태가 바뀌면 다른 행의 중복 표시도 달라질 수 있다
      say(`${application.organization} ${application.name} 신청을 저장했습니다.`);
    } catch (error) {
      say(`저장하지 못했습니다. ${error.message}`);
      await load();
    }
  }

  function editMemo(application) {
    dialog.querySelector("#memo-target").textContent = `${application.organization} ${application.name}`;
    dialog.querySelector("textarea").value = application.memo;
    dialog.onclose = () => dialog.returnValue === "save" && save(application, { memo: dialog.querySelector("textarea").value });
    dialog.showModal();
  }

  filters.addEventListener("change", load);
  filters.addEventListener("submit", (event) => (event.preventDefault(), load()));
  filters.addEventListener("reset", () => setTimeout(load));
  document.getElementById("today-button").addEventListener("click", () => {
    filters.contact_date.value = today;
    load();
  });

  const exportButton = document.getElementById("export-button");
  exportButton.addEventListener("click", async () => {
    exportButton.disabled = true;
    say("Google 시트로 내보내는 중…");
    try {
      const result = await request(exportApi, { method: "POST" });
      say(`시트에 ${result.rows}건을 내보냈습니다.`);
    } catch (error) {
      say(`내보내지 못했습니다. ${error.message}`);
    } finally {
      exportButton.disabled = false;
    }
  });

  load();
})();
