const STATUSES = [
    "DRAFT",
    "DOCS_VERIFIED",
    "OFFICIAL_REVIEW",
    "MEETING_PROPOSED",
    "MEETING_SCHEDULED",
    "MINUTES_GENERATED",
    "RESOLVED",
];

const PHD_TYPE_LABELS = {
    comprehensive_exam: "Comprehensive Examination",
    thesis_extension: "Thesis Extension",
    supervisor_allocation: "Supervisor Allocation",
    supervisor_change: "Change of Supervisor",
    semester_leave: "Semester Leave",
    thesis_submission: "Thesis Submission",
    general: "General Request",
};

const MTECH_TYPE_LABELS = {
    conversion_full_part: "Full-time to Part-time Conversion",
    dissertation_extension: "Dissertation Extension",
    supervisor_allocation: "Supervisor Allocation",
    supervisor_change: "Change of Supervisor",
    semester_leave: "Semester Leave",
    thesis_submission: "Thesis / Dissertation Submission",
    general: "General Request",
};

const UG_TYPE_LABELS = {
    semester_leave: "Semester / Medical Leave",
    slow_pace: "Slow Pace of Study",
    make_up_exam: "Make-up Examination",
    back_paper: "Back Paper / Grade Improvement",
    minor_honours: "Minor / Honours Registration",
    general: "General Request",
};

const TYPE_LABELS = { ...PHD_TYPE_LABELS, ...MTECH_TYPE_LABELS, ...UG_TYPE_LABELS };

function typeLabelsForUser() {
    const programme = userProgramme();
    if (/b\.?tech|bachelor|undergrad|^ug$/i.test(programme)) return UG_TYPE_LABELS;
    if (/m\.?tech|master/i.test(programme)) return MTECH_TYPE_LABELS;
    return PHD_TYPE_LABELS;
}

const state = {
    token: localStorage.getItem("dai_token") || "",
    user: null,
    view: "home",
    applications: [],
    currentId: null,
    currentApp: null,
    chatHistory: [],
    askProgramme: "",
};

const $ = (id) => document.getElementById(id);

function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 3200);
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function formatMd(text) {
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
}

function formatSlot(slot) {
    if (!slot) return "—";
    if (typeof slot === "string") return slot;
    const date = slot.date || slot.day || "";
    const start = slot.start || slot.start_time || slot.begin || "";
    const end = slot.end || slot.end_time || "";
    const room = slot.room || slot.venue || "";
    return [date, start && end ? `${start}–${end}` : start, room].filter(Boolean).join(" · ") || JSON.stringify(slot);
}

async function api(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    if (!(options.body instanceof FormData)) {
        headers["Content-Type"] = headers["Content-Type"] || "application/json";
    }
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    const response = await fetch(path, Object.assign({}, options, { headers }));
    let data = {};
    try { data = await response.json(); } catch (_err) { data = {}; }
    if (!response.ok) {
        const detail = data.detail;
        const message = typeof detail === "string" ? detail : (detail && JSON.stringify(detail)) || data.message || `Request failed (${response.status})`;
        throw new Error(message);
    }
    return data;
}

function setAuth(token, user) {
    state.token = token;
    state.user = user;
    if (token) localStorage.setItem("dai_token", token);
    else localStorage.removeItem("dai_token");
}

function logout() {
    setAuth("", null);
    state.applications = [];
    state.currentApp = null;
    state.chatHistory = [];
    window.location.reload();
}

function navItems() {
    const role = state.user.role;
    if (role === "STUDENT") {
        return [
            ["home", "Dashboard"],
            ["apply", "New application"],
            ["chat", "Ordinance chatbot"],
        ];
    }
    if (role === "OFFICIAL") {
        return [
            ["home", "Review queue"],
            ["chat", "Ordinance chatbot"],
        ];
    }
    return [
        ["home", "Proposed meetings"],
        ["chat", "Ordinance chatbot"],
    ];
}

function initialsFromName(name) {
    return String(name || "")
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0].toUpperCase())
        .join("") || "U";
}

function applyUserPhoto() {
    const photo = $("who-photo");
    const initials = $("who-initials");
    const url = state.user && state.user.photo_url;
    if (photo && url) {
        photo.src = url;
        photo.hidden = false;
        if (initials) initials.hidden = true;
    } else if (photo) {
        photo.removeAttribute("src");
        photo.hidden = true;
        if (initials) {
            initials.hidden = false;
            initials.textContent = initialsFromName(state.user && state.user.full_name);
        }
    }
}

function renderShell() {
    $("login-screen").hidden = true;
    $("app-shell").hidden = false;
    $("who-name").textContent = state.user.full_name;
    $("who-role").textContent = state.user.role.replace("_", " ");
    applyUserPhoto();
    const nav = $("nav");
    nav.innerHTML = "";
    navItems().forEach(([id, label]) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = label;
        btn.className = state.view === id ? "active" : "";
        btn.addEventListener("click", () => { state.view = id; render(); });
        nav.appendChild(btn);
    });
}

function trackerHtml(status) {
    const current = STATUSES.indexOf(status);
    return `<div class="tracker" aria-label="Application status">
        ${STATUSES.map((item, index) => {
            const cls = index < current ? "done" : index === current ? "current" : "";
            return `<div class="step ${cls}">${index + 1}. ${item.replaceAll("_", " ")}</div>`;
        }).join("")}
    </div>`;
}

function appRow(app) {
    return `<tr>
        <td>#${app.id}<br><strong>${escapeHtml(app.title)}</strong></td>
        <td>${escapeHtml(app.student_name || "")}<br><span class="muted">${escapeHtml(app.student_roll || "")}</span></td>
        <td>${escapeHtml(TYPE_LABELS[app.application_type] || app.application_type)}</td>
        <td><span class="badge ${app.status}">${app.status}</span></td>
        <td><button class="btn btn-outline" data-open="${app.id}">Open</button></td>
    </tr>`;
}

function studentHome() {
    $("page-title").textContent = "Scholar dashboard";
    $("page-sub").textContent = `${userProgramme()} · ${state.user.department || "CSE"}`;
    const resolved = state.applications.filter((item) => item.status === "RESOLVED").length;
    $("view").innerHTML = `
        <div class="grid grid-2">
            <div class="card">
                <h3>Profile</h3>
                <div class="profile-card-head">
                    ${state.user.photo_url ? `<img class="avatar-lg" src="${escapeHtml(state.user.photo_url)}" alt="">` : `<span class="avatar-lg avatar-fallback">${escapeHtml(initialsFromName(state.user.full_name))}</span>`}
                    <div>
                        <p><strong>${escapeHtml(state.user.full_name)}</strong></p>
                        <p class="muted">${escapeHtml(state.user.email)}</p>
                    </div>
                </div>
                <p>Roll: ${escapeHtml(state.user.roll_number || "—")}</p>
                <p>Programme: ${escapeHtml(userProgramme())}</p>
                <p>Department: ${escapeHtml(state.user.department || "CSE")}</p>
                <p>Phone: ${escapeHtml(state.user.phone || "—")}</p>
                <div class="btn-row"><button class="btn btn-outline" id="home-profile-btn" type="button">Edit profile</button></div>
            </div>
            <div class="card">
                <h3>Workload</h3>
                <p class="kpi">${state.applications.length}</p>
                <p class="muted">Applications · ${resolved} resolved</p>
            </div>
        </div>
        <div class="card" style="margin-top:16px">
            <h3>My applications</h3>
            ${state.applications.length ? `
            <div class="table-wrap"><table>
                <thead><tr><th>Case</th><th>Scholar</th><th>Type</th><th>Status</th><th></th></tr></thead>
                <tbody>${state.applications.map(appRow).join("")}</tbody>
            </table></div>` : `<p class="empty">No applications yet. Create one from the sidebar.</p>`}
        </div>
    `;
}

function staffHome(title, emptyText) {
    $("page-title").textContent = title;
    $("page-sub").textContent = "Human-in-the-loop DUGC / DMPC / DDPC workflow";
    const queue = state.user.role === "OFFICIAL"
        ? state.applications.filter((item) => item.status === "OFFICIAL_REVIEW" || item.status === "MEETING_SCHEDULED")
        : state.applications.filter((item) => item.status === "MEETING_PROPOSED");
    $("view").innerHTML = `
        <div class="card">
            <h3>Action queue</h3>
            ${queue.length ? `
            <div class="table-wrap"><table>
                <thead><tr><th>Case</th><th>Scholar</th><th>Type</th><th>Status</th><th></th></tr></thead>
                <tbody>${queue.map(appRow).join("")}</tbody>
            </table></div>` : `<p class="empty">${emptyText}</p>`}
        </div>
        <div class="card" style="margin-top:16px">
            <h3>All visible cases</h3>
            ${state.applications.length ? `
            <div class="table-wrap"><table>
                <thead><tr><th>Case</th><th>Scholar</th><th>Type</th><th>Status</th><th></th></tr></thead>
                <tbody>${state.applications.map(appRow).join("")}</tbody>
            </table></div>` : `<p class="empty">No cases yet.</p>`}
        </div>
    `;
}

function applyView() {
    $("page-title").textContent = "New application";
    $("page-sub").textContent = "Draft is created first. Upload PDFs, then submit for AI verification.";
    $("view").innerHTML = `
        <div class="card">
            <form id="apply-form">
                <label for="app-type">Application type</label>
                <select id="app-type">
                    ${Object.entries(typeLabelsForUser()).map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}
                </select>
                <label for="app-title">Title</label>
                <input id="app-title" required placeholder="e.g. Request for thesis duration extension">
                <label for="app-desc">Description</label>
                <textarea id="app-desc" required placeholder="State the academic request, dates, CPI/SPI, supervisor, and ordinance clauses if known."></textarea>
                <label for="app-files">Supporting PDFs</label>
                <input id="app-files" type="file" accept="application/pdf" multiple>
                <div class="btn-row">
                    <button class="btn btn-primary" type="submit">Create, upload and submit</button>
                </div>
            </form>
        </div>
    `;
    $("apply-form").addEventListener("submit", onCreateSubmit);
}

function userProgramme() {
    if (state.askProgramme) return state.askProgramme;
    const raw = state.user && state.user.programme;
    if (raw) return raw;
    if (state.user && state.user.role === "STUDENT") return "Ph.D.";
    return state.askProgramme || "Ph.D.";
}

function programmeKind(programme) {
    const text = String(programme || "");
    if (/b\.?tech|bachelor|undergrad|^ug$/i.test(text)) return "ug";
    if (/m\.?tech|master/i.test(text)) return "mtech";
    return "phd";
}

function chatView() {
    const programme = userProgramme();
    const kind = programmeKind(programme);
    $("page-title").textContent = "Ordinance chatbot";
    $("page-sub").textContent = kind === "ug"
        ? "Answers are grounded in the Ordinances for Bachelors Programmes, 2023."
        : kind === "mtech"
            ? "Answers are grounded in the Ordinances for Masters' Programmes, 2023."
            : "Answers are grounded in the Doctoral Programmes Ordinance, 2023.";
    const intro = kind === "ug"
        ? "Ask a question about B.Tech. rules, DUGC, leave, registration, or academic performance."
        : kind === "mtech"
            ? "Ask a question about M.Tech. rules, DMPC, dissertation, leave, or registration."
            : "Ask a question about Ph.D. rules, DDPC, comprehensive examination, leave, or thesis processes.";
    const selector = state.user && state.user.role !== "STUDENT"
        ? `<label for="ask-programme">Knowledge base</label>
            <select id="ask-programme">
                <option value="B.Tech." ${kind === "ug" ? "selected" : ""}>B.Tech. / DUGC</option>
                <option value="M.Tech." ${kind === "mtech" ? "selected" : ""}>M.Tech. / DMPC</option>
                <option value="Ph.D." ${kind === "phd" ? "selected" : ""}>Ph.D. / DDPC</option>
            </select>`
        : "";
    $("view").innerHTML = `
        <div class="card">
            ${selector}
            <div id="chat-box" class="chat-box">
                <div class="message bot-message">${intro}</div>
            </div>
            <div class="chat-input">
                <input id="question-input" placeholder="Ask a question...">
                <button class="btn btn-primary" id="send-button" type="button">Send</button>
            </div>
        </div>
    `;
    const programmeSelect = $("ask-programme");
    if (programmeSelect) {
        programmeSelect.addEventListener("change", () => {
            state.askProgramme = programmeSelect.value;
            state.chatHistory = [];
            chatView();
        });
    }
    $("send-button").addEventListener("click", sendQuestion);
    $("question-input").addEventListener("keydown", (event) => {
        if (event.key === "Enter") sendQuestion();
    });
}

function missingBanner(app) {
    const missing = app.missing_documents || [];
    if (!missing.length || app.status !== "DRAFT") return "";
    return `<div class="alert alert-warn"><strong>Documents flagged.</strong> Missing or unmatched: ${missing.map(escapeHtml).join("; ")}</div>`;
}

function resolvedBanner(app) {
    if (app.status !== "RESOLVED") return "";
    return `<div class="alert alert-ok"><strong>Resolved.</strong> The committee decision and minutes are available below.</div>`;
}

function detailActions(app) {
    const role = state.user.role;
    if (role === "STUDENT" && app.status === "DRAFT") {
        return `
            <form id="more-docs">
                <label>Upload additional PDFs</label>
                <input id="more-files" type="file" accept="application/pdf" multiple>
                <div class="btn-row">
                    <button class="btn btn-outline" type="submit">Upload</button>
                    <button class="btn btn-gold" id="submit-btn" type="button">Submit for verification</button>
                </div>
            </form>`;
    }
    if (role === "OFFICIAL" && (app.status === "OFFICIAL_REVIEW" || app.status === "DOCS_VERIFIED")) {
        const availability = app.member_availability || [];
        const availabilityHtml = availability.length
            ? `<div class="avail-card"><h4>Committee free time</h4>${availability.map((member) => `
                <p><strong>${escapeHtml(member.name)}</strong> (${escapeHtml(member.role || "Member")})
                <span class="muted"> — ${escapeHtml(member.summary || (member.typical_free_windows || []).join("; "))}</span></p>`).join("")}</div>`
            : "";
        return `${availabilityHtml}<div class="btn-row">
            <button class="btn btn-gold" id="draft-btn" type="button">Generate / refresh draft resolution</button>
            <button class="btn btn-outline" id="save-draft-btn" type="button">Save edits</button>
            <button class="btn btn-primary" id="propose-btn" type="button">Schedule meeting</button>
        </div>
        <textarea id="draft-area" class="draft-area">${escapeHtml(app.draft_resolution || "")}</textarea>`;
    }
    if (role === "OFFICIAL" && app.status === "MEETING_SCHEDULED") {
        const availability = app.member_availability || [];
        const availabilityHtml = availability.length
            ? `<div class="avail-card"><h4>Committee free time</h4>${availability.map((member) => `
                <p><strong>${escapeHtml(member.name)}</strong>
                <span class="muted"> — ${escapeHtml(member.summary || "")}</span></p>`).join("")}</div>`
            : "";
        return `${availabilityHtml}<div class="btn-row"><button class="btn btn-green" id="minutes-btn" type="button">Generate minutes</button></div>`;
    }
    if (role === "OFFICIAL" && app.status === "MEETING_PROPOSED") {
        const slots = app.proposed_slots || [];
        const availability = app.member_availability || [];
        const availabilityHtml = availability.length
            ? `<div class="avail-card"><h4>Committee free time</h4>${availability.map((member) => `
                <p><strong>${escapeHtml(member.name)}</strong> (${escapeHtml(member.role || "Member")})
                <span class="muted"> — ${escapeHtml(member.summary || (member.typical_free_windows || []).join("; "))}</span></p>`).join("")}</div>`
            : "";
        return `${availabilityHtml}<h3>Proposed slots</h3>
        <div id="slots">${slots.map((slot, index) => {
            const members = slot.member_availability || [];
            const memberLines = members.length
                ? members.map((item) => `<li>${escapeHtml(item.summary || item.name)}</li>`).join("")
                : "";
            return `<div class="slot">
                <div>
                    <strong>Slot ${index + 1}</strong><br>${escapeHtml(formatSlot(slot))}
                    ${memberLines ? `<ul class="avail-list">${memberLines}</ul>` : ""}
                </div>
            </div>`;
        }).join("") || "<p class='muted'>Waiting for committee approval.</p>"}</div>
        ${app.draft_resolution ? `<h3 style="margin-top:16px">Draft resolution</h3><div class="bot-message" style="padding:12px">${formatMd(app.draft_resolution)}</div>` : ""}`;
    }
    if (role === "COMMITTEE_DDPC" && app.status === "MEETING_PROPOSED") {
        const slots = app.proposed_slots || [];
        const availability = app.member_availability || [];
        const availabilityHtml = availability.length
            ? `<div class="avail-card"><h4>Committee free time</h4>${availability.map((member) => `
                <p><strong>${escapeHtml(member.name)}</strong> (${escapeHtml(member.role || "Member")})
                <span class="muted"> — ${escapeHtml(member.summary || (member.typical_free_windows || []).join("; "))}</span></p>`).join("")}</div>`
            : "";
        return `${availabilityHtml}<div id="slots">${slots.map((slot, index) => {
            const members = slot.member_availability || [];
            const memberLines = members.length
                ? members.map((item) => `<li>${escapeHtml(item.summary || item.name)}</li>`).join("")
                : "";
            return `<div class="slot">
                <div>
                    <strong>Slot ${index + 1}</strong><br>${escapeHtml(formatSlot(slot))}
                    ${memberLines ? `<ul class="avail-list">${memberLines}</ul>` : ""}
                </div>
                <button class="btn btn-green" data-slot="${index + 1}" type="button">Approve slot</button>
            </div>`;
        }).join("") || "<p class='muted'>No slots were returned by the scheduler.</p>"}</div>`;
    }
    if (app.draft_resolution) {
        return `<h3>Draft resolution</h3><div class="bot-message" style="padding:12px">${formatMd(app.draft_resolution)}</div>`;
    }
    return "";
}

function detailView(app) {
    $("page-title").textContent = app.title;
    $("page-sub").textContent = `Application #${app.id} · ${TYPE_LABELS[app.application_type] || app.application_type}`;
    const docs = (app.documents || []).map((doc) => `<li>${escapeHtml(doc.filename)} <span class="muted">(${doc.text_length || 0} chars extracted)</span></li>`).join("") || "<li class='muted'>No files</li>";
    const history = (app.history || []).map((item) => `<li><strong>${escapeHtml(item.to_status)}</strong> — ${escapeHtml(item.note || "")} <span class="muted">${escapeHtml(item.actor_name || "")}</span></li>`).join("");
    $("view").innerHTML = `
        ${trackerHtml(app.status)}
        ${missingBanner(app)}
        ${resolvedBanner(app)}
        <div class="grid grid-2">
            <div class="card">
                <h3>Case</h3>
                <p><span class="badge ${app.status}">${app.status}</span></p>
                <p>${escapeHtml(app.description)}</p>
                <p class="muted">Scholar: ${escapeHtml(app.student?.full_name || "")} · ${escapeHtml(app.student?.roll_number || "")}</p>
            </div>
            <div class="card">
                <h3>Documents</h3>
                <ul>${docs}</ul>
            </div>
        </div>
        <div class="card" style="margin-top:16px">
            ${detailActions(app)}
            ${app.minutes_text ? `<h3 style="margin-top:16px">Minutes / decision</h3><div>${formatMd(app.minutes_text)}</div>` : ""}
            ${app.final_summary && app.status === "RESOLVED" ? `<div class="alert alert-ok" style="margin-top:12px">${formatMd(app.final_summary)}</div>` : ""}
        </div>
        <div class="card" style="margin-top:16px">
            <h3>History</h3>
            <ul>${history}</ul>
            <div class="btn-row"><button class="btn btn-outline" id="back-btn" type="button">Back to list</button></div>
        </div>
    `;
    bindDetailEvents(app);
}

function bindDetailEvents(app) {
    const back = $("back-btn");
    if (back) back.addEventListener("click", () => { state.view = "home"; state.currentId = null; render(); });
    const more = $("more-docs");
    if (more) more.addEventListener("submit", async (event) => {
        event.preventDefault();
        await uploadFiles(app.id, $("more-files").files);
        await openApp(app.id);
    });
    const submitBtn = $("submit-btn");
    if (submitBtn) submitBtn.addEventListener("click", async () => {
        submitBtn.disabled = true;
        try {
            const data = await api(`/api/applications/${app.id}/submit`, { method: "POST", body: "{}" });
            toast(data.message || "Submitted");
            await openApp(app.id);
        } catch (err) {
            toast(err.message);
            submitBtn.disabled = false;
        }
    });
    const draftBtn = $("draft-btn");
    if (draftBtn) draftBtn.addEventListener("click", async () => {
        draftBtn.disabled = true;
        draftBtn.textContent = "Retrieving ordinance context...";
        try {
            const data = await api(`/api/applications/${app.id}/draft-resolution`, { method: "POST", body: "{}" });
            $("draft-area").value = data.application.draft_resolution || "";
            toast("Draft ready");
        } catch (err) {
            toast(err.message);
        } finally {
            draftBtn.disabled = false;
            draftBtn.textContent = "Generate / refresh draft resolution";
        }
    });
    const saveDraft = $("save-draft-btn");
    if (saveDraft) saveDraft.addEventListener("click", async () => {
        try {
            await api(`/api/applications/${app.id}/draft-resolution`, {
                method: "PUT",
                body: JSON.stringify({ draft_resolution: $("draft-area").value }),
            });
            toast("Draft saved");
        } catch (err) { toast(err.message); }
    });
    const proposeBtn = $("propose-btn");
    if (proposeBtn) proposeBtn.addEventListener("click", async () => {
        if ($("draft-area") && $("draft-area").value.trim()) {
            await api(`/api/applications/${app.id}/draft-resolution`, {
                method: "PUT",
                body: JSON.stringify({ draft_resolution: $("draft-area").value }),
            });
        }
        proposeBtn.disabled = true;
        proposeBtn.textContent = "Finding common slots...";
        try {
            await api(`/api/applications/${app.id}/schedule/propose`, {
                method: "POST",
                body: JSON.stringify({ date_range: "2026-09-14 to 2026-09-25", use_gemini: false }),
            });
            toast("Three slots proposed");
            await openApp(app.id);
        } catch (err) {
            toast(err.message);
            proposeBtn.disabled = false;
            proposeBtn.textContent = "Schedule meeting";
        }
    });
    const minutesBtn = $("minutes-btn");
    if (minutesBtn) minutesBtn.addEventListener("click", async () => {
        minutesBtn.disabled = true;
        try {
            await api(`/api/applications/${app.id}/minutes`, { method: "POST", body: "{}" });
            toast("Minutes generated and case resolved");
            await openApp(app.id);
        } catch (err) {
            toast(err.message);
            minutesBtn.disabled = false;
        }
    });
    document.querySelectorAll("[data-slot]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            btn.disabled = true;
            try {
                await api(`/api/applications/${app.id}/schedule/approve`, {
                    method: "POST",
                    body: JSON.stringify({ slot_index: Number(btn.dataset.slot), use_gemini: false }),
                });
                toast("Meeting scheduled");
                await openApp(app.id);
            } catch (err) {
                toast(err.message);
                btn.disabled = false;
            }
        });
    });
}

async function onCreateSubmit(event) {
    event.preventDefault();
    const btn = event.target.querySelector("button");
    btn.disabled = true;
    try {
        const created = await api("/api/applications", {
            method: "POST",
            body: JSON.stringify({
                title: $("app-title").value.trim(),
                description: $("app-desc").value.trim(),
                application_type: $("app-type").value,
            }),
        });
        const appId = created.application.id;
        const files = $("app-files").files;
        if (files.length) await uploadFiles(appId, files);
        const submitted = await api(`/api/applications/${appId}/submit`, { method: "POST", body: "{}" });
        toast(submitted.message || "Application submitted");
        await openApp(appId);
    } catch (err) {
        toast(err.message);
        btn.disabled = false;
    }
}

async function uploadFiles(appId, fileList) {
    if (!fileList || !fileList.length) return;
    const body = new FormData();
    Array.from(fileList).forEach((file) => body.append("files", file));
    await api(`/api/applications/${appId}/documents`, { method: "POST", body });
}

async function sendQuestion() {
    const input = $("question-input");
    const question = input.value.trim();
    if (!question) return;
    const box = $("chat-box");
    const userMsg = document.createElement("div");
    userMsg.className = "message user-message";
    userMsg.textContent = question;
    box.appendChild(userMsg);
    input.value = "";
    $("send-button").disabled = true;
    try {
        const data = await api("/ask", {
            method: "POST",
            body: JSON.stringify({
                question,
                conversation_history: state.chatHistory,
                role: state.user && state.user.role,
                programme: userProgramme(),
            }),
        });
        const bot = document.createElement("div");
        bot.className = "message bot-message";
        bot.innerHTML = formatMd(data.answer || "");
        box.appendChild(bot);
        if (state.user && state.user.role !== "STUDENT" && data.sources && data.sources.length) {
            const src = document.createElement("div");
            src.className = "message bot-message muted";
            src.textContent = data.sources.map((item, index) => {
                const kind = item.chunk_type || "ordinance_clause";
                return `${index + 1}. [${kind}] ${item.chunk_id || ""} ${item.clause ? "Clause " + item.clause : ""}`.trim();
            }).join("\n");
            box.appendChild(src);
        }
        state.chatHistory.push({ role: "user", content: question });
        state.chatHistory.push({ role: "assistant", content: data.answer });
    } catch (err) {
        const bot = document.createElement("div");
        bot.className = "message bot-message";
        bot.textContent = "Error: " + err.message;
        box.appendChild(bot);
    }
    $("send-button").disabled = false;
    box.scrollTop = box.scrollHeight;
}

async function openApp(id) {
    const data = await api(`/api/applications/${id}`);
    let app = data.application;
    if (
        state.user.role === "OFFICIAL" &&
        (app.status === "OFFICIAL_REVIEW" || app.status === "DOCS_VERIFIED") &&
        !app.draft_resolution
    ) {
        toast("Generating 5-heading draft resolution from the ordinance...");
        try {
            const drafted = await api(`/api/applications/${id}/draft-resolution`, { method: "POST", body: "{}" });
            app = drafted.application;
        } catch (err) {
            toast(err.message);
        }
    }
    state.currentId = id;
    state.currentApp = app;
    state.view = "detail";
    render();
}

async function loadApps() {
    const data = await api("/api/applications");
    state.applications = data.applications || [];
}

async function render() {
    renderShell();
    if (state.view === "detail" && state.currentApp) {
        detailView(state.currentApp);
        bindListButtons();
        return;
    }
    if (state.view === "apply") {
        applyView();
        return;
    }
    if (state.view === "chat") {
        chatView();
        return;
    }
    await loadApps();
    if (state.user.role === "STUDENT") studentHome();
    else if (state.user.role === "OFFICIAL") staffHome("Official review", "No applications waiting in official review.");
    else staffHome("Committee desk", "No proposed meetings awaiting slot approval.");
    bindListButtons();
    const homeProfile = $("home-profile-btn");
    if (homeProfile) homeProfile.addEventListener("click", openProfileModal);
}

function bindListButtons() {
    document.querySelectorAll("[data-open]").forEach((btn) => {
        btn.addEventListener("click", () => openApp(Number(btn.dataset.open)));
    });
}

async function bootSession() {
    if (!state.token) return false;
    try {
        const data = await api("/api/auth/me");
        state.user = data.user;
        return true;
    } catch (_err) {
        setAuth("", null);
        return false;
    }
}

$("login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = $("login-btn");
    const error = $("login-error");
    error.hidden = true;
    btn.disabled = true;
    try {
        const data = await api("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: $("login-email").value.trim(),
                password: $("login-password").value,
            }),
        });
        setAuth(data.token, data.user);
        state.view = "home";
        await render();
    } catch (err) {
        error.textContent = err.message;
        error.hidden = false;
    } finally {
        btn.disabled = false;
    }
});

document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
        $("login-email").value = chip.dataset.email;
        $("login-password").value = chip.dataset.password;
    });
});

$("logout-btn").addEventListener("click", logout);

function openProfileModal() {
    if (!state.user) return;
    $("profile-name").value = state.user.full_name || "";
    $("profile-phone").value = state.user.phone || "";
    $("profile-dept").value = state.user.department || "";
    const preview = $("profile-preview");
    if (state.user.photo_url) {
        preview.src = state.user.photo_url;
        preview.hidden = false;
    } else {
        preview.removeAttribute("src");
        preview.hidden = true;
    }
    $("profile-photo").value = "";
    $("profile-modal").hidden = false;
}

function closeProfileModal() {
    $("profile-modal").hidden = true;
}

$("profile-btn").addEventListener("click", openProfileModal);
$("who-avatar-btn").addEventListener("click", openProfileModal);
$("profile-cancel").addEventListener("click", closeProfileModal);
$("profile-modal").addEventListener("click", (event) => {
    if (event.target === $("profile-modal")) closeProfileModal();
});
$("profile-photo").addEventListener("change", () => {
    const file = $("profile-photo").files[0];
    if (!file) return;
    const preview = $("profile-preview");
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
});
$("profile-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const btn = $("profile-save");
    btn.disabled = true;
    try {
        const data = await api("/api/auth/profile", {
            method: "PUT",
            body: JSON.stringify({
                full_name: $("profile-name").value.trim(),
                phone: $("profile-phone").value.trim(),
                department: $("profile-dept").value.trim(),
            }),
        });
        state.user = data.user;
        const file = $("profile-photo").files[0];
        if (file) {
            const body = new FormData();
            body.append("file", file);
            const photo = await api("/api/auth/profile/photo", { method: "POST", body });
            state.user = photo.user;
        }
        toast("Profile saved");
        closeProfileModal();
        renderShell();
        if (state.view === "home") render();
    } catch (err) {
        toast(err.message);
    } finally {
        btn.disabled = false;
    }
});

bootSession().then((ok) => { if (ok) render(); });
