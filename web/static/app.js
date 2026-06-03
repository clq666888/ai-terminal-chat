const chatArea = document.getElementById("chat-area");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnStop = document.getElementById("btn-stop");
const btnClear = document.getElementById("btn-clear");
const btnNewChat = document.getElementById("btn-new-chat");
const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");
const sidebar = document.getElementById("sidebar");
const convList = document.getElementById("conv-list");
const headerTitle = document.getElementById("header-title");
const welcome = document.getElementById("welcome");
const btnSettings = document.getElementById("btn-settings");
const settingsOverlay = document.getElementById("settings-overlay");
const btnCloseSettings = document.getElementById("btn-close-settings");
const btnSaveSettings = document.getElementById("btn-save-settings");

const setMaxRounds = document.getElementById("set-max-rounds");
const setMaxContextSize = document.getElementById("set-max-context-size");
const setBaseUrl = document.getElementById("set-base-url");
const setApiKey = document.getElementById("set-api-key");
const setKeyFile = document.getElementById("set-key-file");
const keyStatus = document.getElementById("key-status");
const quickModel = document.getElementById("quick-model");

const btnManageModels = document.getElementById("btn-manage-models");
const modelManageOverlay = document.getElementById("model-manage-overlay");
const btnCloseManage = document.getElementById("btn-close-manage");
const customModelListEl = document.getElementById("custom-model-list");
const addProvider = document.getElementById("add-provider");
const addModel = document.getElementById("add-model");
const addModelCustom = document.getElementById("add-model-custom");
const btnSaveApiConfig = document.getElementById("btn-save-api-config");

const agentSelector = document.getElementById("agent-selector");
const agentSelectorBtn = document.getElementById("agent-selector-btn");
const agentSelectorAvatar = document.getElementById("agent-selector-avatar");
const agentSelectorName = document.getElementById("agent-selector-name");
const agentDropdown = document.getElementById("agent-dropdown");
const agentDropdownList = document.getElementById("agent-dropdown-list");
const agentDropdownManage = document.getElementById("agent-dropdown-manage");

const agentOverlay = document.getElementById("agent-overlay");
const btnCloseAgentPanel = document.getElementById("btn-close-agent-panel");
const agentPanelTitle = document.getElementById("agent-panel-title");
const agentGrid = document.getElementById("agent-grid");
const btnCreateAgent = document.getElementById("btn-create-agent");
const agentListView = document.getElementById("agent-list-view");
const agentFormView = document.getElementById("agent-form-view");
const agentAvatarPreview = document.getElementById("agent-avatar-preview");
const agentAvatarInput = document.getElementById("agent-avatar-input");
const agentName = document.getElementById("agent-name");
const agentPrompt = document.getElementById("agent-prompt");
const agentProvider = document.getElementById("agent-provider");
const agentModel = document.getElementById("agent-model");
const btnAgentCancel = document.getElementById("btn-agent-cancel");
const btnAgentSave = document.getElementById("btn-agent-save");
const agentFormActions = document.getElementById("agent-form-actions");
const agentCallable = document.getElementById("agent-callable");
const callableFields = document.getElementById("callable-fields");
const agentSlug = document.getElementById("agent-slug");
const agentWhenToCall = document.getElementById("agent-when-to-call");

const btnAttach = document.getElementById("btn-attach");
const btnWebsearch = document.getElementById("btn-websearch");
const imageFileInput = document.getElementById("image-file-input");
const imagePreviewBar = document.getElementById("image-preview-bar");

let webSearchOn = false;
if (btnWebsearch) {
    btnWebsearch.addEventListener("click", () => {
        webSearchOn = !webSearchOn;
        btnWebsearch.classList.toggle("active", webSearchOn);
        showToast(webSearchOn ? "联网搜索已开启" : "联网搜索已关闭", "info");
    });
}

let isGenerating = false;
let currentAbort = null;
let currentConvId = null;
let welcomeHTML = welcome ? welcome.outerHTML : "";
let providers = {};
let currentAgentId = null;
let editingAgentId = null;
let agentAvatarUrl = "";
let cachedAgents = [];
let pendingImages = [];
let pendingDocs = [];

function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
        try {
            return marked.parse(text);
        } catch (e) {
            return escapeHtml(text).replace(/\n/g, "<br>");
        }
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

const DEFAULT_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const SMALL_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const DROPDOWN_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CARD_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>';

btnToggleSidebar.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
btnNewChat.addEventListener("click", createNewConversation);
btnSend.addEventListener("click", sendMessage);
btnStop.addEventListener("click", stopGeneration);
btnClear.addEventListener("click", clearCurrentConversation);
userInput.addEventListener("input", autoResize);
userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

btnSettings.addEventListener("click", openSettings);
btnCloseSettings.addEventListener("click", closeSettings);
settingsOverlay.addEventListener("click", e => { if (e.target === settingsOverlay) closeSettings(); });
btnSaveSettings.addEventListener("click", saveSettings);

quickModel.addEventListener("change", onQuickModelChange);
btnManageModels.addEventListener("click", openManageModels);
btnCloseManage.addEventListener("click", closeManageModels);
modelManageOverlay.addEventListener("click", e => { if (e.target === modelManageOverlay) closeManageModels(); });
addProvider.addEventListener("change", onAddProviderChange);
addModel.addEventListener("change", () => {
    if (addModel.value === "__custom__") { addModelCustom.style.display = "block"; addModelCustom.focus(); }
    else { addModelCustom.style.display = "none"; }
});
btnSaveApiConfig.addEventListener("click", saveApiConfig);

agentSelectorBtn.addEventListener("click", toggleAgentDropdown);
agentDropdownManage.addEventListener("click", () => { closeAgentDropdown(); openAgentPanel(); });
document.addEventListener("click", e => {
    if (!agentSelector.contains(e.target)) closeAgentDropdown();
});

btnCloseAgentPanel.addEventListener("click", closeAgentPanel);
agentOverlay.addEventListener("click", e => { if (e.target === agentOverlay) closeAgentPanel(); });
btnCreateAgent.addEventListener("click", () => showAgentForm(null));
btnAgentCancel.addEventListener("click", showAgentList);
btnAgentSave.addEventListener("click", saveAgent);
agentAvatarInput.addEventListener("change", uploadAvatar);
agentCallable.addEventListener("change", () => {
    callableFields.style.display = agentCallable.checked ? "block" : "none";
});

btnAttach.addEventListener("click", () => imageFileInput.click());
imageFileInput.addEventListener("change", handleImageSelect);
userInput.addEventListener("paste", handleImagePaste);

const DOC_EXTENSIONS = new Set([
    "pdf","docx","xlsx","csv","txt","md","log",
    "json","xml","html","py","js","ts","java","c","cpp","go","rs","sh",
    "yaml","yml","ini","conf","cfg","toml"
]);

const REJECTED_EXTENSIONS = {
    "doc": "请将 .doc 转换为 .docx 后上传",
    "xls": "请将 .xls 转换为 .xlsx 后上传",
    "ppt": "请将 .ppt 转换为 .pptx 后上传",
    "pptx": "暂不支持 .pptx 格式",
    "rtf": "暂不支持 .rtf 格式",
    "odt": "暂不支持 .odt 格式",
    "ods": "暂不支持 .ods 格式",
    "odp": "暂不支持 .odp 格式",
    "zip": "不支持压缩包",
    "rar": "不支持压缩包",
    "7z": "不支持压缩包",
    "tar": "不支持压缩包",
    "gz": "不支持压缩包",
    "exe": "不支持可执行文件",
    "bin": "不支持二进制文件",
    "dll": "不支持二进制文件"
};

let dragCounter = 0;
document.addEventListener("dragenter", e => {
    e.preventDefault();
    dragCounter++;
    chatArea.classList.add("drag-over");
});
document.addEventListener("dragover", e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
});
document.addEventListener("dragleave", e => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter <= 0) {
        dragCounter = 0;
        chatArea.classList.remove("drag-over");
    }
});
document.addEventListener("drop", e => {
    e.preventDefault();
    dragCounter = 0;
    chatArea.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (!files || !files.length) return;
    for (const file of files) {
        if (!checkFileAllowed(file)) continue;
        if (file.type.startsWith("image/")) {
            readImageFile(file);
        } else {
            uploadDocFile(file);
        }
    }
});

function handleImageSelect() {
    const files = imageFileInput.files;
    if (!files || !files.length) return;
    for (const file of files) {
        if (!checkFileAllowed(file)) continue;
        if (file.type.startsWith("image/")) {
            readImageFile(file);
        } else {
            uploadDocFile(file);
        }
    }
    imageFileInput.value = "";
}

function checkFileAllowed(file) {
    const ext = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    if (file.type.startsWith("image/")) return true;
    if (DOC_EXTENSIONS.has(ext)) return true;
    if (REJECTED_EXTENSIONS[ext]) {
        showToast(REJECTED_EXTENSIONS[ext] + "\n\n支持的文档格式: PDF、Word(.docx)、Excel(.xlsx)、CSV、TXT、Markdown、代码文件", "error");
    } else {
        showToast("不支持的文件格式: ." + ext + "\n\n支持的文档格式: PDF、Word(.docx)、Excel(.xlsx)、CSV、TXT、Markdown、代码文件", "error");
    }
    return false;
}

async function uploadDocFile(file) {
    if (file.size > 50 * 1024 * 1024) {
        showToast("文档不能超过 50MB", "error");
        return;
    }
    const placeholder = { name: file.name, text: null, loading: true, charCount: 0, truncated: false };
    pendingDocs.push(placeholder);
    renderPreviews();
    try {
        const formData = new FormData();
        formData.append("file", file);
        const resp = await fetch("/api/upload-doc", { method: "POST", body: formData });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            showToast(err.error || "文档上传失败", "error");
            pendingDocs.splice(pendingDocs.indexOf(placeholder), 1);
            renderPreviews();
            return;
        }
        const data = await resp.json();
        placeholder.text = data.text;
        placeholder.loading = false;
        placeholder.charCount = data.char_count;
        placeholder.truncated = data.truncated;
        renderPreviews();
    } catch (e) {
        showToast("文档上传失败: " + e.message, "error");
        pendingDocs.splice(pendingDocs.indexOf(placeholder), 1);
        renderPreviews();
    }
}

function handleImagePaste(e) {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {
        if (item.type.startsWith("image/")) {
            e.preventDefault();
            readImageFile(item.getAsFile());
        }
    }
}

function readImageFile(file) {
    if (file.size > 20 * 1024 * 1024) {
        showToast("图片不能超过 20MB", "error");
        return;
    }
    const reader = new FileReader();
    reader.onload = () => {
        pendingImages.push({ name: file.name, base64: reader.result });
        renderPreviews();
    };
    reader.readAsDataURL(file);
}

function renderPreviews() {
    imagePreviewBar.innerHTML = "";
    if (pendingImages.length === 0 && pendingDocs.length === 0) {
        imagePreviewBar.style.display = "none";
        return;
    }
    imagePreviewBar.style.display = "flex";
    pendingImages.forEach((img, idx) => {
        const item = document.createElement("div");
        item.className = "image-preview-item";
        const thumb = document.createElement("img");
        thumb.src = img.base64;
        thumb.alt = img.name;
        const removeBtn = document.createElement("button");
        removeBtn.className = "image-preview-remove";
        removeBtn.textContent = "\u00d7";
        removeBtn.addEventListener("click", () => {
            pendingImages.splice(idx, 1);
            renderPreviews();
        });
        item.appendChild(thumb);
        item.appendChild(removeBtn);
        imagePreviewBar.appendChild(item);
    });
    pendingDocs.forEach((doc, idx) => {
        const item = document.createElement("div");
        item.className = "doc-preview-item";
        const icon = document.createElement("span");
        icon.className = "doc-preview-icon";
        const ext = doc.name.includes(".") ? doc.name.split(".").pop().toLowerCase() : "";
        icon.textContent = ext === "pdf" ? "\ud83d\udcc4" : ext === "xlsx" ? "\ud83d\udcca" : ext === "docx" ? "\ud83d\udcdd" : ext === "csv" ? "\ud83d\udcca" : "\ud83d\udcc3";
        const info = document.createElement("div");
        info.className = "doc-preview-info";
        const nameEl = document.createElement("div");
        nameEl.className = "doc-preview-name";
        nameEl.textContent = doc.name;
        info.appendChild(nameEl);
        if (doc.loading) {
            const status = document.createElement("div");
            status.className = "doc-preview-status";
            status.textContent = "解析中...";
            info.appendChild(status);
        } else {
            const status = document.createElement("div");
            status.className = "doc-preview-status";
            status.textContent = doc.charCount.toLocaleString() + " 字符" + (doc.truncated ? " (已截断)" : "");
            info.appendChild(status);
        }
        const removeBtn = document.createElement("button");
        removeBtn.className = "doc-preview-remove";
        removeBtn.textContent = "\u00d7";
        removeBtn.addEventListener("click", () => {
            pendingDocs.splice(idx, 1);
            renderPreviews();
        });
        item.appendChild(icon);
        item.appendChild(info);
        item.appendChild(removeBtn);
        imagePreviewBar.appendChild(item);
    });
}

function autoResize() {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 150) + "px";
}

async function loadProviders() {
    const resp = await fetch("/api/providers");
    providers = await resp.json();
}

// ==================== 智能体下拉选择器 ====================
function toggleAgentDropdown() {
    if (agentSelector.classList.contains("open")) {
        closeAgentDropdown();
    } else {
        openAgentDropdown();
    }
}

async function openAgentDropdown() {
    const resp = await fetch("/api/agents");
    cachedAgents = resp.ok ? await resp.json() : [];
    renderAgentDropdown();
    agentSelector.classList.add("open");
}

function closeAgentDropdown() {
    agentSelector.classList.remove("open");
}

function renderAgentDropdown() {
    agentDropdownList.innerHTML = "";

    const defaultItem = document.createElement("div");
    defaultItem.className = "agent-dropdown-item" + (!currentAgentId ? " active" : "");
    defaultItem.innerHTML =
        '<div class="agent-dropdown-item-avatar">' + DROPDOWN_AVATAR_SVG + '</div>' +
        '<div class="agent-dropdown-item-info">' +
        '<div class="agent-dropdown-item-name">通用助手</div>' +
        '<div class="agent-dropdown-item-model">全局模型</div>' +
        '</div>' +
        '<div class="agent-dropdown-item-check">' + CHECK_SVG + '</div>';
    defaultItem.addEventListener("click", () => { selectAgent(null); closeAgentDropdown(); });
    agentDropdownList.appendChild(defaultItem);

    cachedAgents.forEach(a => {
        const item = document.createElement("div");
        item.className = "agent-dropdown-item" + (currentAgentId === a.id ? " active" : "");
        const avatarHTML = a.avatar
            ? '<div class="agent-dropdown-item-avatar"><img src="' + a.avatar + '" alt=""></div>'
            : '<div class="agent-dropdown-item-avatar">' + DROPDOWN_AVATAR_SVG + '</div>';
        const modelText = a.model || "全局模型";
        item.innerHTML =
            avatarHTML +
            '<div class="agent-dropdown-item-info">' +
            '<div class="agent-dropdown-item-name">' + escapeHtml(a.name) + '</div>' +
            '<div class="agent-dropdown-item-model">' + escapeHtml(modelText) + '</div>' +
            '</div>' +
            '<div class="agent-dropdown-item-check">' + CHECK_SVG + '</div>';
        item.addEventListener("click", () => { selectAgent(a.id); closeAgentDropdown(); });
        agentDropdownList.appendChild(item);
    });
}

function updateSelectorButton() {
    if (!currentAgentId) {
        agentSelectorAvatar.innerHTML = SMALL_AVATAR_SVG;
        agentSelectorName.textContent = "通用助手";
        return;
    }
    const agent = cachedAgents.find(a => a.id === currentAgentId);
    if (agent) {
        agentSelectorAvatar.innerHTML = agent.avatar
            ? '<img src="' + agent.avatar + '" alt="">'
            : SMALL_AVATAR_SVG;
        agentSelectorName.textContent = agent.name;
    } else {
        agentSelectorAvatar.innerHTML = SMALL_AVATAR_SVG;
        agentSelectorName.textContent = "通用助手";
        currentAgentId = null;
    }
}

async function selectAgent(agentId) {
    currentAgentId = agentId;
    await fetch("/api/current-agent", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId })
    });

    if (currentConvId) {
        await fetch("/api/conversations/" + currentConvId + "/agent", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_id: agentId })
        });
    }

    updateSelectorButton();

    const agent = cachedAgents.find(a => a.id === agentId);
    showToast("已切换到: " + (agent ? agent.name : "通用助手"), "success");
}

async function loadAgentBar() {
    const resp = await fetch("/api/agents");
    cachedAgents = resp.ok ? await resp.json() : [];
    const curResp = await fetch("/api/current-agent");
    const cur = curResp.ok ? await curResp.json() : {};
    currentAgentId = cur.agent_id || null;
    updateSelectorButton();
}

// ==================== 智能体管理面板 ====================
async function openAgentPanel() {
    if (Object.keys(providers).length === 0) await loadProviders();
    showAgentList();
    agentOverlay.classList.add("active");
}

function closeAgentPanel() {
    agentOverlay.classList.remove("active");
}

async function showAgentList() {
    agentListView.style.display = "block";
    agentFormView.style.display = "none";
    agentFormActions.style.display = "none";
    agentPanelTitle.textContent = "管理智能体";

    const resp = await fetch("/api/agents");
    cachedAgents = resp.ok ? await resp.json() : [];
    agentGrid.innerHTML = "";

    if (cachedAgents.length === 0) {
        agentGrid.innerHTML = '<div class="empty-hint">还没有创建智能体，点击下方按钮创建</div>';
        return;
    }

    cachedAgents.forEach(a => {
        const card = document.createElement("div");
        card.className = "agent-card";
        const avatarHTML = a.avatar
            ? '<div class="agent-card-avatar"><img src="' + a.avatar + '" alt=""></div>'
            : '<div class="agent-card-avatar">' + CARD_AVATAR_SVG + '</div>';
        const modelText = a.model ? a.model : "全局模型";
        const callableBadge = a.callable ? '<span class="callable-badge" title="可被调用: ' + escapeHtml(a.slug || '') + '">⚡</span>' : '';
        card.innerHTML = avatarHTML +
            '<div class="agent-card-name">' + escapeHtml(a.name) + callableBadge + '</div>' +
            '<div class="agent-card-model">' + escapeHtml(modelText) + '</div>' +
            '<div class="agent-card-actions">' +
            '<button class="btn-edit-agent" title="编辑">✎</button>' +
            '<button class="btn-delete-agent" title="删除">✕</button>' +
            '</div>';

        card.querySelector(".btn-edit-agent").addEventListener("click", e => {
            e.stopPropagation();
            showAgentForm(a);
        });
        card.querySelector(".btn-delete-agent").addEventListener("click", async e => {
            e.stopPropagation();
            await fetch("/api/agents/" + a.id, { method: "DELETE" });
            if (currentAgentId === a.id) await selectAgent(null);
            await showAgentList();
            updateSelectorButton();
        });
        card.addEventListener("click", () => {
            selectAgent(a.id);
            closeAgentPanel();
        });

        agentGrid.appendChild(card);
    });
}

async function showAgentForm(agent) {
    agentListView.style.display = "none";
    agentFormView.style.display = "block";
    agentFormActions.style.display = "flex";
    editingAgentId = agent ? agent.id : null;
    agentPanelTitle.textContent = agent ? "编辑智能体" : "创建智能体";

    agentName.value = agent ? agent.name : "";
    agentPrompt.value = agent ? (agent.system_prompt || "") : "";
    agentAvatarUrl = agent ? (agent.avatar || "") : "";

    if (agentAvatarUrl) {
        agentAvatarPreview.innerHTML = '<img src="' + agentAvatarUrl + '" alt="">';
    } else {
        agentAvatarPreview.innerHTML = DEFAULT_AVATAR_SVG;
    }

    agentProvider.innerHTML = '<option value="">使用全局模型</option>';
    for (const [key, val] of Object.entries(providers)) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        agentProvider.appendChild(opt);
    }
    agentProvider.value = agent ? (agent.provider || "") : "";
    onAgentProviderChange();
    if (agent && agent.model) {
        agentModel.value = agent.model;
    }

    agentCallable.checked = agent ? !!agent.callable : false;
    callableFields.style.display = agentCallable.checked ? "block" : "none";
    agentSlug.value = agent ? (agent.slug || "") : "";
    agentWhenToCall.value = agent ? (agent.when_to_call || "") : "";

    agentProvider.onchange = onAgentProviderChange;
}

function onAgentProviderChange() {
    const key = agentProvider.value;
    agentModel.innerHTML = '<option value="">使用全局模型</option>';
    if (!key) return;
    const p = providers[key];
    if (p && p.models) {
        p.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            agentModel.appendChild(opt);
        });
    }
}

async function uploadAvatar() {
    const file = agentAvatarInput.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
        const resp = await fetch("/api/agents/upload-avatar", { method: "POST", body: formData });
        if (resp.ok) {
            const data = await resp.json();
            agentAvatarUrl = data.url;
            agentAvatarPreview.innerHTML = '<img src="' + agentAvatarUrl + '" alt="">';
            showToast("头像已上传", "success");
        } else {
            const err = await resp.json();
            showToast(err.error || "上传失败", "error");
        }
    } catch (e) {
        showToast("上传失败", "error");
    }
    agentAvatarInput.value = "";
}

async function saveAgent() {
    const name = agentName.value.trim();
    if (!name) { showToast("请输入名称", "error"); return; }

    const callable = agentCallable.checked;
    const slug = agentSlug.value.trim();
    const whenToCall = agentWhenToCall.value.trim();
    if (callable && !slug) { showToast("请填写英文标识名", "error"); return; }
    if (callable && !whenToCall) { showToast("请填写何时调用", "error"); return; }

    const payload = {
        name: name,
        avatar: agentAvatarUrl,
        system_prompt: agentPrompt.value,
        provider: agentProvider.value,
        model: agentModel.value,
        base_url: "",
        callable: callable,
        slug: slug,
        when_to_call: whenToCall
    };

    if (payload.provider) {
        const p = providers[payload.provider];
        if (p) payload.base_url = p.base_url || "";
    }

    try {
        let resp;
        if (editingAgentId) {
            resp = await fetch("/api/agents/" + editingAgentId, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            resp = await fetch("/api/agents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }
        if (resp.ok) {
            showToast(editingAgentId ? "已更新" : "已创建", "success");
            const agentsResp = await fetch("/api/agents");
            cachedAgents = agentsResp.ok ? await agentsResp.json() : [];
            updateSelectorButton();
            await showAgentList();
        } else {
            const err = await resp.json();
            showToast(err.error || "保存失败", "error");
        }
    } catch (e) {
        showToast("保存失败", "error");
    }
}

// ==================== 模型快选 ====================
async function buildQuickModelList() {
    const [activeResp, customResp] = await Promise.all([
        fetch("/api/active-model"),
        fetch("/api/custom-models")
    ]);
    const active = activeResp.ok ? await activeResp.json() : {};
    const customModels = customResp.ok ? await customResp.json() : [];

    quickModel.innerHTML = "";
    const activeKey = active.provider + "|" + active.model;

    if (customModels.length === 0) {
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "点击 + 添加模型";
        placeholder.disabled = true;
        placeholder.selected = true;
        quickModel.appendChild(placeholder);
        return;
    }

    customModels.forEach(m => {
        const key = m.provider + "|" + m.model;
        const opt = document.createElement("option");
        opt.value = key;
        opt.dataset.baseUrl = m.base_url || "";
        opt.textContent = m.name || m.model;
        if (key === activeKey) opt.selected = true;
        quickModel.appendChild(opt);
    });
}

async function onQuickModelChange() {
    const val = quickModel.value;
    if (!val) return;
    const [provider, model] = val.split("|", 2);
    const selected = quickModel.selectedOptions[0];
    const baseUrl = selected && selected.dataset.baseUrl ? selected.dataset.baseUrl : "";
    try {
        const body = { provider, model };
        if (baseUrl) body.base_url = baseUrl;
        const resp = await fetch("/api/model", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        if (resp.ok) showToast("已切换到 " + model, "success");
    } catch (err) {
        showToast("切换失败", "error");
    }
}

async function openManageModels() {
    if (Object.keys(providers).length === 0) await loadProviders();
    addProvider.innerHTML = "";
    for (const [key, val] of Object.entries(providers)) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        addProvider.appendChild(opt);
    }
    const resp = await fetch("/api/settings");
    const cfg = resp.ok ? await resp.json() : {};
    addProvider.value = cfg.provider || "deepseek";
    onAddProviderChange();
    setBaseUrl.value = cfg.base_url || "";
    setApiKey.value = "";
    setKeyFile.value = cfg.key_file_path || "";
    if (cfg.model) {
        if (addModel.querySelector('option[value="' + cfg.model + '"]')) {
            addModel.value = cfg.model;
        }
    }
    keyStatus.textContent = cfg.has_api_key ? "✓ 已配置 API Key" : "✗ 未配置 API Key";
    keyStatus.className = "key-status " + (cfg.has_api_key ? "ok" : "no");
    await renderCustomModelList();
    modelManageOverlay.classList.add("active");
}

function closeManageModels() { modelManageOverlay.classList.remove("active"); }

function onAddProviderChange() {
    const key = addProvider.value;
    const p = providers[key];
    if (!p) return;
    if (p.base_url) setBaseUrl.value = p.base_url;
    addModel.innerHTML = "";
    if (p.models && p.models.length > 0) {
        p.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            addModel.appendChild(opt);
        });
    }
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "-- 自定义模型名 --";
    addModel.appendChild(customOpt);
    addModelCustom.style.display = "none";
    addModelCustom.value = "";
}

async function renderCustomModelList() {
    const [customResp, activeResp] = await Promise.all([
        fetch("/api/custom-models"),
        fetch("/api/active-model")
    ]);
    const customModels = customResp.ok ? await customResp.json() : [];
    const active = activeResp.ok ? await activeResp.json() : {};
    customModelListEl.innerHTML = "";
    if (customModels.length === 0) {
        customModelListEl.innerHTML = '<div class="empty-hint">还没有保存任何模型配置</div>';
        return;
    }
    customModels.forEach(m => {
        const isActive = m.provider === active.provider && m.model === active.model;
        const item = document.createElement("div");
        item.className = "custom-model-item" + (isActive ? " is-active" : "");
        item.innerHTML =
            '<span class="model-name">' + escapeHtml(m.model) + '</span>' +
            '<span class="model-provider">' + escapeHtml(m.name || m.provider) + '</span>' +
            '<div class="model-item-actions">' +
            '<button class="btn-edit-model" title="编辑">✎</button>' +
            '<button class="btn-remove-model" title="删除">✕</button>' +
            '</div>';
        item.querySelector(".btn-edit-model").addEventListener("click", () => {
            addProvider.value = m.provider;
            onAddProviderChange();
            setBaseUrl.value = m.base_url || "";
            if (addModel.querySelector('option[value="' + m.model + '"]')) {
                addModel.value = m.model;
                addModelCustom.style.display = "none";
            } else {
                addModel.value = "__custom__";
                addModelCustom.value = m.model;
                addModelCustom.style.display = "block";
            }
            btnSaveApiConfig.dataset.editingKey = m.provider + "|" + m.model;
            btnSaveApiConfig.textContent = "保存修改";
        });
        item.querySelector(".btn-remove-model").addEventListener("click", async () => {
            await fetch("/api/custom-models", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ provider: m.provider, model: m.model })
            });
            if (btnSaveApiConfig.dataset.editingKey === m.provider + "|" + m.model) {
                btnSaveApiConfig.dataset.editingKey = "";
                btnSaveApiConfig.textContent = "保存配置";
            }
            await renderCustomModelList();
            await buildQuickModelList();
        });
        customModelListEl.appendChild(item);
    });
}


async function saveApiConfig() {
    const provider = addProvider.value;
    const model = addModel.value === "__custom__" ? addModelCustom.value.trim() : addModel.value;
    const base_url = setBaseUrl.value.trim();
    if (!base_url) { showToast("请填写 API 地址", "error"); return; }
    if (!model) { showToast("请选择或输入模型名称", "error"); return; }
    const payload = { provider, base_url, model };
    const apiKeyVal = setApiKey.value.trim();
    const keyFileVal = setKeyFile.value.trim();
    if (apiKeyVal) payload.api_key = apiKeyVal;
    if (keyFileVal) payload.key_file_path = keyFileVal;
    try {
        const settingsResp = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!settingsResp.ok) {
            const err = await settingsResp.json();
            showToast(err.error || "保存失败", "error");
            return;
        }
        const p = providers[provider];
        const name = (p ? p.name : provider) + " / " + model;
        const editingKey = btnSaveApiConfig.dataset.editingKey || "";
        if (editingKey) {
            const [oldProvider, oldModel] = editingKey.split("|", 2);
            await fetch("/api/custom-models", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ old_provider: oldProvider, old_model: oldModel, provider, model, base_url, name })
            });
            btnSaveApiConfig.dataset.editingKey = "";
            btnSaveApiConfig.textContent = "保存配置";
        } else {
            await fetch("/api/custom-models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ provider, model, base_url, name })
            });
        }
        showToast("配置已保存", "success");
        if (apiKeyVal || keyFileVal) {
            keyStatus.textContent = "✓ 已配置 API Key";
            keyStatus.className = "key-status ok";
        }
        await renderCustomModelList();
        await buildQuickModelList();
    } catch (err) {
        showToast("保存失败: " + err.message, "error");
    }
}



// ==================== 对话管理 ====================
async function loadConversations() {
    const resp = await fetch("/api/conversations");
    const list = await resp.json();
    renderConvList(list);
}

function renderConvList(list) {
    convList.innerHTML = "";
    list.forEach(c => {
        const item = document.createElement("div");
        item.className = "conv-item" + (c.id === currentConvId ? " active" : "");
        item.dataset.id = c.id;
        item.innerHTML =
            '<span class="conv-item-icon">💬</span>' +
            '<span class="conv-item-title">' + escapeHtml(c.title) + '</span>' +
            '<button class="conv-item-delete" title="删除">✕</button>';
        item.addEventListener("click", e => {
            if (e.target.closest(".conv-item-delete")) return;
            switchConversation(c.id);
        });
        item.querySelector(".conv-item-delete").addEventListener("click", e => {
            e.stopPropagation();
            deleteConversation(c.id);
        });
        convList.appendChild(item);
    });
}

async function createNewConversation() {
    const resp = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: currentAgentId })
    });
    const conv = await resp.json();
    currentConvId = conv.id;
    await loadConversations();
    showWelcome();
    headerTitle.textContent = conv.title;
    userInput.focus();
}

async function switchConversation(cid) {
    if (isGenerating) stopGeneration();
    currentConvId = cid;
    document.querySelectorAll(".conv-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === cid);
    });
    const resp = await fetch("/api/conversations/" + cid + "/messages");
    const msgs = await resp.json();
    chatArea.innerHTML = "";
    if (msgs.length === 0) { showWelcome(); }
    else {
        msgs.forEach(m => {
            const role = m.role === "user" ? "user" : "ai";
            let text = typeof m.content === "string" ? m.content : (m.content.find(c => c.type === "text") || {}).text || "";
            const imgs = typeof m.content !== "string" ? m.content.filter(c => c.type === "image_url").map(c => c.image_url.url) : [];
            let historyDocs = [];
            if (role === "user") {
                const docRegex = /\[文档: (.+?)\]\n[\s\S]*?(?=\n\n\[文档:|$)/g;
                let dm;
                while ((dm = docRegex.exec(text)) !== null) {
                    historyDocs.push({ name: dm[1] });
                }
                if (historyDocs.length > 0) {
                    const lastDoc = text.lastIndexOf("\n\n[文档:");
                    const firstDoc = text.indexOf("[文档:");
                    if (firstDoc === 0) {
                        const afterDocs = text.replace(/^(\[文档: .+?\]\n[\s\S]*?)(\n\n(?!\[文档:)[\s\S]*)?$/, "$2").replace(/^\n\n/, "");
                        text = afterDocs || "";
                    }
                }
            }
            addMessage(role, text, imgs, historyDocs);
        });
        const allMsgs = chatArea.querySelectorAll(".message.ai");
        if (allMsgs.length > 0) {
            appendRetryButton(allMsgs[allMsgs.length - 1], "", false);
        }
    }

    const convResp = await fetch("/api/conversations");
    const list = await convResp.json();
    const conv = list.find(c => c.id === cid);
    headerTitle.textContent = conv ? conv.title : "AI Chat";

    if (conv && conv.agent_id !== undefined) {
        currentAgentId = conv.agent_id;
        await fetch("/api/current-agent", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_id: currentAgentId })
        });
        updateSelectorButton();
    }
}

async function deleteConversation(cid) {
    await fetch("/api/conversations/" + cid, { method: "DELETE" });
    if (currentConvId === cid) { currentConvId = null; showWelcome(); headerTitle.textContent = "AI Chat"; }
    await loadConversations();
}

async function clearCurrentConversation() {
    if (!currentConvId) return;
    if (isGenerating) stopGeneration();
    await fetch("/api/conversations/" + currentConvId + "/clear", { method: "POST" });
    chatArea.innerHTML = "";
    showWelcome();
}

function showWelcome() { chatArea.innerHTML = welcomeHTML; }
function hideWelcome() { const w = chatArea.querySelector(".welcome"); if (w) w.remove(); }

// ==================== 消息渲染与发送 ====================
let userScrolledUp = false;

chatArea.addEventListener("scroll", () => {
    const gap = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight;
    if (gap < 30) {
        userScrolledUp = false;
    }
}, { passive: true });

chatArea.addEventListener("wheel", (e) => {
    if (e.deltaY < 0) userScrolledUp = true;
}, { passive: true });

chatArea.addEventListener("touchmove", () => {
    const gap = chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight;
    if (gap > 50) userScrolledUp = true;
}, { passive: true });

function shouldAutoScroll() {
    if (userScrolledUp) return false;
    return chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < 30;
}

function addMessage(role, content, images, docs) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "message " + role;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "U" : "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "ai") {
        const rendered = renderCallBlocks(content);
        if (rendered) {
            bubble.appendChild(rendered);
        } else {
            bubble.innerHTML = renderMarkdown(content);
        }
    } else {
        if (docs && docs.length > 0) {
            const docRow = document.createElement("div");
            docRow.className = "msg-docs";
            docs.forEach(d => {
                const chip = document.createElement("span");
                chip.className = "msg-doc-chip";
                const ext = d.name.includes(".") ? d.name.split(".").pop().toLowerCase() : "";
                const icon = ext === "pdf" ? "\ud83d\udcc4" : ext === "xlsx" ? "\ud83d\udcca" : ext === "docx" ? "\ud83d\udcdd" : ext === "csv" ? "\ud83d\udcca" : "\ud83d\udcc3";
                chip.textContent = icon + " " + d.name;
                docRow.appendChild(chip);
            });
            bubble.appendChild(docRow);
        }
        if (images && images.length > 0) {
            const imgRow = document.createElement("div");
            imgRow.className = "msg-images";
            images.forEach(img => {
                const src = typeof img === "string" ? img : img.base64;
                const el = document.createElement("img");
                el.src = src;
                el.addEventListener("click", () => openImageViewer(src));
                imgRow.appendChild(el);
            });
            bubble.appendChild(imgRow);
        }
        if (content) {
            const textNode = document.createElement("div");
            textNode.textContent = content;
            bubble.appendChild(textNode);
        }
    }
    div.appendChild(avatar);
    div.appendChild(bubble);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return bubble;
}

function openImageViewer(src) {
    const overlay = document.createElement("div");
    overlay.className = "image-viewer-overlay";
    const img = document.createElement("img");
    img.src = src;
    overlay.appendChild(img);
    overlay.addEventListener("click", () => overlay.remove());
    document.body.appendChild(overlay);
}

function addAiBubble() {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "message ai";
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble streaming";
    const cursor = document.createElement("span");
    cursor.className = "typing-cursor";
    bubble.appendChild(cursor);
    div.appendChild(avatar);
    div.appendChild(bubble);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return { bubble, cursor };
}


async function retryLastMessage(userText, rolledBack) {
    if (isGenerating || !currentConvId) return;
    if (rolledBack) {
        const messages = chatArea.querySelectorAll(".message");
        if (messages.length >= 2) {
            messages[messages.length - 1].remove();
            messages[messages.length - 2].remove();
        } else if (messages.length >= 1) {
            messages[messages.length - 1].remove();
        }
        if (userText) {
            userInput.value = userText;
            autoResize();
            userInput.focus();
        }
    } else {
        const resp = await fetch("/api/conversations/" + currentConvId + "/retry", { method: "POST" });
        if (!resp.ok) return;
        const data = await resp.json();
        const messages = chatArea.querySelectorAll(".message");
        if (messages.length >= 2) {
            messages[messages.length - 1].remove();
            messages[messages.length - 2].remove();
        } else if (messages.length >= 1) {
            messages[messages.length - 1].remove();
        }
        if (data.images && data.images.length > 0) {
            pendingImages = data.images.map((url, i) => ({ name: "image_" + i, base64: url }));
            renderPreviews();
        }
        if (data.user_message) {
            userInput.value = data.user_message;
            autoResize();
            userInput.focus();
        }
    }
    await loadConversations();
}

function appendRetryButton(msgDiv, userText, rolledBack) {
    const existing = msgDiv.querySelector(".btn-retry");
    if (existing) existing.remove();
    const btn = document.createElement("button");
    btn.className = "btn-retry" + (rolledBack ? " error-retry" : "");
    btn.title = "重试";
    btn.innerHTML = "&#x21bb;";
    btn.addEventListener("click", () => retryLastMessage(userText, rolledBack));
    msgDiv.appendChild(btn);
}

function stopGeneration() {
    if (currentAbort) {
        currentAbort.abort();
        currentAbort = null;
    }
    isGenerating = false;
    btnSend.style.display = "";
    btnStop.style.display = "none";
    btnSend.disabled = false;
}

async function sendMessage() {
    userScrolledUp = false;
    const text = userInput.value.trim();
    const hasDoc = pendingDocs.some(d => !d.loading && d.text);
    if ((!text && pendingImages.length === 0 && !hasDoc) || isGenerating) return;
    if (pendingDocs.some(d => d.loading)) {
        showToast("文档正在解析中，请稍候", "error");
        return;
    }

    if (!currentConvId) {
        await createNewConversation();
    }

    const abortCtrl = new AbortController();
    currentAbort = abortCtrl;
    isGenerating = true;
    btnSend.style.display = "none";
    btnStop.style.display = "";
    const images = pendingImages.slice();
    const docs = pendingDocs.slice();
    pendingImages = [];
    pendingDocs = [];
    renderPreviews();
    userInput.value = "";
    autoResize();

    addMessage("user", text, images, docs);
    let renderPending = false;
    function scheduleRender() {
        if (renderPending) return;
        renderPending = true;
        requestAnimationFrame(() => {
            renderPending = false;
            if (cursor.parentNode) cursor.remove();
            let html = "";
            if (searchStatusText) {
                html += '<div class="search-status">🌐 ' + escapeHtml(searchStatusText) + '</div>';
            }
            if (reasoningText) {
                const summary = isReasoning ? "思考中..." : "已深度思考";
                html += '<details class="reasoning-block"' + (isReasoning ? ' open' : '') + '><summary>' + summary + '</summary><div class="reasoning-content">' + renderMarkdown(reasoningText) + '</div></details>';
            }
            if (fullText) {
                html += renderMarkdown(fullText);
            }
            bubble.innerHTML = html;
            bubble.appendChild(cursor);
            if (shouldAutoScroll()) chatArea.scrollTop = chatArea.scrollHeight;
        });
    }
    const { bubble, cursor } = addAiBubble();
    let fullText = "";
    let reasoningText = "";
    let isReasoning = false;
    let searchStatusText = "";
    let searchSources = [];

    let messageText = text;
    if (docs.length > 0) {
        const docParts = docs.map(d => "[文档: " + d.name + "]\n" + d.text).join("\n\n");
        messageText = docParts + (text ? "\n\n" + text : "");
    }
    const payload = { conversation_id: currentConvId, message: messageText };
    if (images.length > 0) {
        payload.images = images.map(img => img.base64);
    }
    if (webSearchOn) {
        payload.web_search = true;
    }

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: abortCtrl.signal
        });

        if (!resp.ok) {
            let errMsg = "请求失败 (" + resp.status + ")";
            try {
                const errData = await resp.json();
                if (errData.error) errMsg = errData.error;
            } catch {}
            if (cursor.parentNode) cursor.remove();
            bubble.textContent = "";
            const errDiv = document.createElement("div");
            errDiv.className = "error-msg";
            errDiv.textContent = errMsg;
            bubble.appendChild(errDiv);
            appendRetryButton(bubble.closest(".message"), text, true);
            return;
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6);
                if (data === "[DONE]") continue;

                try {
                    const parsed = JSON.parse(data);
                    if (parsed.error) {
                        bubble.textContent = "";
                        const errDiv = document.createElement("div");
                        errDiv.className = "error-msg";
                        errDiv.textContent = parsed.error;
                        bubble.appendChild(errDiv);
                        appendRetryButton(bubble.closest(".message"), text, true);
                        break;
                    }
                    if (parsed.replace) {
                        fullText = parsed.replace;
                        if (cursor.parentNode) cursor.remove();
                        bubble.textContent = "";
                        const rendered = renderCallBlocks(fullText);
                        if (rendered) {
                            bubble.appendChild(rendered);
                        } else {
                            bubble.innerHTML = renderMarkdown(fullText);
                        }
                        if (shouldAutoScroll()) chatArea.scrollTop = chatArea.scrollHeight;
                    }
                    if (parsed.reasoning_start) {
                        isReasoning = true;
                    }
                    if (parsed.reasoning) {
                        reasoningText += parsed.reasoning;
                        scheduleRender();
                    }
                    if (parsed.reasoning_end) {
                        isReasoning = false;
                        scheduleRender();
                    }
                    if (parsed.chunk) {
                        fullText += parsed.chunk;
                        scheduleRender();
                    }
                    if (parsed.search_status) {
                        searchStatusText = parsed.search_status;
                        scheduleRender();
                    }
                    if (parsed.sources) {
                        searchSources = parsed.sources;
                    }
                } catch {
                    fullText += data;
                    scheduleRender();
                }
            }
        }
    } catch (err) {
        if (err.name === "AbortError") {
            if (cursor.parentNode) cursor.remove();
            if (!fullText) {
                bubble.textContent = "";
                const hint = document.createElement("div");
                hint.className = "error-msg";
                hint.textContent = "[已中断]";
                bubble.appendChild(hint);
            }
        } else {
            if (cursor.parentNode) cursor.remove();
            bubble.textContent = "";
            const errDiv = document.createElement("div");
            errDiv.className = "error-msg";
            errDiv.textContent = "网络错误: " + err.message;
            bubble.appendChild(errDiv);
            appendRetryButton(bubble.closest(".message"), text, true);
        }
    } finally {
        if (cursor.parentNode) cursor.remove();
        currentAbort = null;
        isGenerating = false;
        btnSend.style.display = "";
        btnStop.style.display = "none";
        btnSend.disabled = false;
        userInput.focus();
    }
    if (fullText || reasoningText) {
        bubble.classList.remove("streaming");
        let finalHtml = "";
        if (reasoningText) {
            finalHtml += '<details class="reasoning-block"><summary>已深度思考</summary><div class="reasoning-content">' + renderMarkdown(reasoningText) + '</div></details>';
        }
        if (fullText) {
            const rendered = renderCallBlocks(fullText);
            if (rendered) {
                const tmp = document.createElement("div");
                tmp.appendChild(rendered);
                finalHtml += tmp.innerHTML;
            } else {
                finalHtml += renderMarkdown(fullText);
            }
        }
        if (searchStatusText) {
            finalHtml = '<div class="search-status">🌐 ' + escapeHtml(searchStatusText) + '</div>' + finalHtml;
        }
        if (searchSources && searchSources.length > 0) {
            let srcHtml = '<div class="search-sources"><div class="src-title">参考来源</div>';
            searchSources.forEach((src, i) => {
                const u = String(src.url || "");
                const ti = escapeHtml(String(src.title || u));
                srcHtml += '<a href="' + escapeHtml(u) + '" target="_blank" rel="noopener">' + (i + 1) + '. ' + ti + '</a>';
            });
            srcHtml += '</div>';
            finalHtml += srcHtml;
        }
        bubble.innerHTML = finalHtml;
        appendRetryButton(bubble.closest(".message"), text, false);
    }
    await loadConversations();
}

// ==================== 设置面板 ====================
async function openSettings() {
    const resp = await fetch("/api/settings");
    const cfg = resp.ok ? await resp.json() : {};
    setMaxRounds.value = cfg.max_history_rounds || 50;
    setMaxContextSize.value = cfg.max_context_size_kb || 0;
    settingsOverlay.classList.add("active");
}

function closeSettings() { settingsOverlay.classList.remove("active"); }



async function saveSettings() {
    const payload = {
        max_history_rounds: parseInt(setMaxRounds.value) || 50,
        max_context_size_kb: parseInt(setMaxContextSize.value) || 0
    };
    try {
        const resp = await fetch("/api/settings", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await resp.json();
        if (resp.ok) {
            showToast("设置已保存", "success");
            closeSettings();
        } else {
            showToast(result.error || "保存失败", "error");
        }
    } catch (err) {
        showToast("保存失败: " + err.message, "error");
    }
}

// ==================== 工具函数 ====================
function showToast(msg, type) {
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();
    const toast = document.createElement("div");
    toast.className = "toast " + (type || "");
    toast.textContent = msg;
    document.body.appendChild(toast);
    const duration = type === "error" ? 4000 : 2500;
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, duration);
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function renderCallBlocks(text) {
    const regex = /\[CALL:(\S+?)\]([\s\S]*?)\[\/CALL\]/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push({ type: "text", content: text.slice(lastIndex, match.index) });
        }
        parts.push({ type: "call", slug: match[1], content: match[2].trim() });
        lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
        parts.push({ type: "text", content: text.slice(lastIndex) });
    }
    if (parts.length <= 1 && parts[0] && parts[0].type === "text") return null;

    const container = document.createDocumentFragment();
    for (const p of parts) {
        if (p.type === "text") {
            const span = document.createElement("span");
            span.textContent = p.content;
            container.appendChild(span);
        } else {
            const block = document.createElement("div");
            block.className = "agent-call-block";
            const header = document.createElement("div");
            header.className = "agent-call-header";
            header.innerHTML = '<span class="call-arrow">▶</span> 调用智能体 <span class="call-agent-name">' + escapeHtml(p.slug) + '</span>';
            header.addEventListener("click", () => block.classList.toggle("expanded"));
            const body = document.createElement("div");
            body.className = "agent-call-body";
            body.textContent = p.content;
            block.appendChild(header);
            block.appendChild(body);
            container.appendChild(block);
        }
    }
    return container;
}

// ==================== 初始化 ====================
loadConversations();
buildQuickModelList();
loadAgentBar();

