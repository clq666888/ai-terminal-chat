const chatArea = document.getElementById("chat-area");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnStop = document.getElementById("btn-stop");
const btnNewChat = document.getElementById("btn-new-chat");
const btnNewProject = document.getElementById("btn-new-project");
const projectOverlay = document.getElementById("project-overlay");
const projectPanelTitle = document.getElementById("project-panel-title");
const btnCloseProject = document.getElementById("btn-close-project");
const btnSaveProject = document.getElementById("btn-save-project");
const projectName = document.getElementById("project-name");
const projectPrompt = document.getElementById("project-prompt");
const projectProvider = document.getElementById("project-provider");
const projectModel = document.getElementById("project-model");
const projectKbGroup = document.getElementById("project-kb-group");
const projectKbList = document.getElementById("project-kb-list");
const btnKbUpload = document.getElementById("btn-kb-upload");
const projectKbFile = document.getElementById("project-kb-file");
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
const setAutoCompress = document.getElementById("set-auto-compress");
const setCompressThreshold = document.getElementById("set-compress-threshold");
const compressThresholdRow = document.getElementById("compress-threshold-row");
const setBaseUrl = document.getElementById("set-base-url");
const setApiKey = document.getElementById("set-api-key");
const keyStatus = document.getElementById("key-status");
const quickModel = document.getElementById("quick-model");

const btnManageModels = document.getElementById("btn-manage-models");
const modelManageOverlay = document.getElementById("model-manage-overlay");
const btnCloseManage = document.getElementById("btn-close-manage");
const customModelListEl = document.getElementById("custom-model-list");
const btnOpenModelManager = document.getElementById("btn-open-model-manager");
const modelListOverlay = document.getElementById("model-list-overlay");
const btnCloseModelList = document.getElementById("btn-close-model-list");
const modelConfigTitle = document.getElementById("model-config-title");
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
const agentCustomToggle = document.getElementById("agent-custom-toggle");
const agentSavedModel = document.getElementById("agent-saved-model");
const agentSavedModelWrap = document.getElementById("agent-saved-model-wrap");
const agentCustomWrap = document.getElementById("agent-custom-wrap");
const agentBaseUrl = document.getElementById("agent-base-url");
const agentApiKey = document.getElementById("agent-api-key");
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
let generatingConvId = null;
let welcomeHTML = welcome ? welcome.outerHTML : "";
let providers = {};
let currentAgentId = null;
let editingAgentId = null;
let agentAvatarUrl = "";
let cachedAgents = [];
let pendingImages = [];
let pendingDocs = [];
let convUserCount = 0;

let _markedConfigured = false;
function _ensureMarkedConfig() {
    if (_markedConfigured || typeof marked === "undefined" || !marked.setOptions) return;
    try {
        marked.setOptions({ gfm: true, breaks: true });
    } catch (e) { /* 忽略 */ }
    _markedConfigured = true;
}

function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
        try {
            _ensureMarkedConfig();
            return marked.parse(text);
        } catch (e) {
            return escapeHtml(text).replace(/\n/g, "<br>");
        }
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

function renderMathInElement_safe(el) {
    if (!el || typeof window.renderMathInElement !== "function") return;
    try {
        window.renderMathInElement(el, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "\\[", right: "\\]", display: true },
                { left: "\\(", right: "\\)", display: false },
                { left: "$", right: "$", display: false }
            ],
            throwOnError: false,
            ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"]
        });
    } catch (e) { /* 公式渲染失败保持原样 */ }
}

const DEFAULT_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const SMALL_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const DROPDOWN_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CARD_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>';

btnToggleSidebar.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
btnNewChat.addEventListener("click", () => createNewConversation());
if (btnNewProject) btnNewProject.addEventListener("click", () => openProjectModal(null));
if (btnCloseProject) btnCloseProject.addEventListener("click", closeProjectModal);
if (btnSaveProject) btnSaveProject.addEventListener("click", saveProject);
if (projectOverlay) projectOverlay.addEventListener("click", e => { if (e.target === projectOverlay) closeProjectModal(); });
if (btnKbUpload) btnKbUpload.addEventListener("click", () => { if (!btnKbUpload.disabled) projectKbFile.click(); });
if (projectKbFile) projectKbFile.addEventListener("change", async () => {
    if (projectKbFile.files && projectKbFile.files.length) {
        await uploadKbFiles(Array.from(projectKbFile.files));
        projectKbFile.value = "";
    }
});
const convSearchInput = document.getElementById("conv-search-input");
if (convSearchInput) {
    convSearchInput.addEventListener("input", () => {
        convSearchKeyword = convSearchInput.value || "";
        renderConvList(convCache);
    });
}
btnSend.addEventListener("click", () => sendMessage());
btnStop.addEventListener("click", stopGeneration);
userInput.addEventListener("input", autoResize);
userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

btnSettings.addEventListener("click", openSettings);
btnCloseSettings.addEventListener("click", closeSettings);
btnSaveSettings.addEventListener("click", saveSettings);

quickModel.addEventListener("change", onQuickModelChange);
btnManageModels.addEventListener("click", openManageModels);
btnCloseManage.addEventListener("click", closeManageModels);
btnOpenModelManager.addEventListener("click", openModelList);
btnCloseModelList.addEventListener("click", closeModelList);
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
    if (!e.target.closest(".conv-item-more") && !e.target.closest(".conv-menu")) closeConvMenus();
});

btnCloseAgentPanel.addEventListener("click", closeAgentPanel);
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
        const img = new Image();
        img.onload = () => {
            const MAX = 800;
            let w = img.width, h = img.height;
            if (w > MAX || h > MAX) {
                if (w >= h) { h = Math.round(h * MAX / w); w = MAX; }
                else { w = Math.round(w * MAX / h); h = MAX; }
            }
            const canvas = document.createElement("canvas");
            canvas.width = w; canvas.height = h;
            canvas.getContext("2d").drawImage(img, 0, 0, w, h);
            const compressed = canvas.toDataURL("image/jpeg", 0.80);
            pendingImages.push({ name: file.name, base64: compressed });
            renderPreviews();
        };
        img.src = reader.result;
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

function providerEntriesCustomFirst() {
    const entries = Object.entries(providers);
    entries.sort((a, b) => {
        if (a[0] === "custom") return -1;
        if (b[0] === "custom") return 1;
        return 0;
    });
    return entries;
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
    await syncQuickModelToAgent();

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
    await syncQuickModelToAgent();
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

    agentProvider.innerHTML = "";
    for (const [key, val] of providerEntriesCustomFirst()) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        agentProvider.appendChild(opt);
    }

    await buildAgentSavedModelList(agent);

    const savedKey = agentSavedModel.value;
    const isCustom = !!(agent && agent.model) && savedKey === "";
    agentCustomToggle.checked = isCustom;
    if (isCustom) {
        agentProvider.value = agent.provider || agentProvider.value;
        agentBaseUrl.value = agent.base_url || "";
        agentApiKey.value = "";
        agentModel.value = agent.model || "";
    } else {
        agentProvider.value = agentProvider.options.length ? agentProvider.options[0].value : "";
        agentBaseUrl.value = "";
        agentApiKey.value = "";
        agentModel.value = "";
    }
    applyAgentModelMode();

    agentCallable.checked = agent ? !!agent.callable : false;
    callableFields.style.display = agentCallable.checked ? "block" : "none";
    agentSlug.value = agent ? (agent.slug || "") : "";
    agentWhenToCall.value = agent ? (agent.when_to_call || "") : "";

    agentCustomToggle.onchange = applyAgentModelMode;
    agentProvider.onchange = onAgentProviderChange;
}

async function buildAgentSavedModelList(agent) {
    let customModels = [];
    try {
        const resp = await fetch("/api/custom-models");
        if (resp.ok) customModels = await resp.json();
    } catch (e) {}
    agentSavedModel.innerHTML = '<option value="">跟随当前模型</option>';
    customModels.forEach(m => {
        const key = m.provider + "|" + m.model;
        const opt = document.createElement("option");
        opt.value = key;
        opt.dataset.baseUrl = m.base_url || "";
        opt.textContent = m.name || m.model;
        agentSavedModel.appendChild(opt);
    });
    if (agent && agent.model) {
        const wantKey = (agent.provider || "") + "|" + agent.model;
        const match = Array.from(agentSavedModel.options).find(o => o.value === wantKey);
        agentSavedModel.value = match ? wantKey : "";
    } else {
        agentSavedModel.value = "";
    }
}

function applyAgentModelMode() {
    const custom = agentCustomToggle.checked;
    agentCustomWrap.style.display = custom ? "block" : "none";
    agentSavedModelWrap.style.display = custom ? "none" : "block";
    if (custom) onAgentProviderChange();
}

function onAgentProviderChange() {
    const key = agentProvider.value;
    const p = providers[key];
    if (p && p.base_url && !agentBaseUrl.value.trim()) {
        agentBaseUrl.value = p.base_url;
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
        provider: "",
        model: "",
        base_url: "",
        callable: callable,
        slug: slug,
        when_to_call: whenToCall
    };

    if (agentCustomToggle.checked) {
        const cProvider = agentProvider.value;
        const cModel = agentModel.value.trim();
        const cBaseUrl = agentBaseUrl.value.trim();
        const cKey = agentApiKey.value.trim();
        if (!cModel) { showToast("请填写模型名称", "error"); return; }
        if (!cBaseUrl) { showToast("请填写 API 地址", "error"); return; }
        const p = providers[cProvider];
        const providerName = p ? p.name : cProvider;
        const regBody = { provider: cProvider, model: cModel, base_url: cBaseUrl, name: providerName + " / " + cModel };
        if (cKey) regBody.api_key = cKey;
        try {
            const regResp = await fetch("/api/custom-models", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(regBody)
            });
            if (!regResp.ok && regResp.status !== 409) {
                const err = await regResp.json();
                showToast(err.error || "保存模型失败", "error");
                return;
            }
            if (cKey && regResp.status === 409) {
                await fetch("/api/settings", {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ provider: cProvider, api_key: cKey })
                });
            }
        } catch (e) {
            showToast("保存模型失败: " + e.message, "error");
            return;
        }
        await buildQuickModelList();
        payload.provider = cProvider;
        payload.model = cModel;
        payload.base_url = cBaseUrl;
    } else {
        const val = agentSavedModel.value;
        if (val) {
            const [sProvider, sModel] = val.split("|", 2);
            const selOpt = agentSavedModel.selectedOptions[0];
            payload.provider = sProvider;
            payload.model = sModel;
            payload.base_url = selOpt && selOpt.dataset.baseUrl ? selOpt.dataset.baseUrl : "";
        }
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

    await syncQuickModelToAgent();
}

async function onQuickModelChange() {
    if (quickModel.disabled) return;
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

async function syncQuickModelToAgent() {
    const agent = currentAgentId ? cachedAgents.find(a => a.id === currentAgentId) : null;
    const locked = !!(agent && agent.model);
    if (locked) {
        const wantKey = (agent.provider || "") + "|" + agent.model;
        let opt = Array.from(quickModel.options).find(o => o.value === wantKey);
        if (!opt) {
            opt = document.createElement("option");
            opt.value = wantKey;
            opt.dataset.baseUrl = agent.base_url || "";
            opt.dataset.agentTemp = "1";
            opt.textContent = agent.model;
            quickModel.appendChild(opt);
        }
        quickModel.value = wantKey;
        quickModel.disabled = true;
        quickModel.title = "当前模型已由智能体「" + agent.name + "」指定，不可修改";
        try {
            const body = { provider: agent.provider || "", model: agent.model };
            const baseUrl = opt.dataset.baseUrl || agent.base_url || "";
            if (baseUrl) body.base_url = baseUrl;
            await fetch("/api/model", {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
        } catch (e) {}
    } else {
        quickModel.disabled = false;
        quickModel.title = "";
        Array.from(quickModel.options).filter(o => o.dataset.agentTemp === "1").forEach(o => o.remove());
    }
}

async function openManageModels() {
    if (Object.keys(providers).length === 0) await loadProviders();
    addProvider.innerHTML = "";
    for (const [key, val] of providerEntriesCustomFirst()) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        addProvider.appendChild(opt);
    }
    addProvider.value = providers["deepseek"] ? "deepseek" : (addProvider.options.length ? addProvider.options[0].value : "deepseek");
    btnSaveApiConfig.dataset.editingKey = "";
    btnSaveApiConfig.textContent = "保存配置";
    modelConfigTitle.textContent = "新增模型";
    await onAddProviderChange();
    modelManageOverlay.classList.add("active");
}

function closeManageModels() {
    modelManageOverlay.classList.remove("active");
    btnSaveApiConfig.dataset.fromList = "";
}

async function openModelList() {
    await renderCustomModelList();
    modelListOverlay.classList.add("active");
}

function closeModelList() { modelListOverlay.classList.remove("active"); }

async function onAddProviderChange() {
    const key = addProvider.value;
    const p = providers[key];
    if (!p) return;
    setBaseUrl.value = p.base_url || "";
    addModel.innerHTML = "";
    if (p.models && p.models.length > 0) {
        p.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            addModel.appendChild(opt);
        });
    }
    const hasPreset = p.models && p.models.length > 0;
    if (hasPreset) {
        const customOpt = document.createElement("option");
        customOpt.value = "__custom__";
        customOpt.textContent = "-- 自定义模型名 --";
        addModel.appendChild(customOpt);
        addModel.style.display = "";
        addModelCustom.style.display = (addModel.value === "__custom__") ? "block" : "none";
    } else {
        const customOpt = document.createElement("option");
        customOpt.value = "__custom__";
        customOpt.textContent = "-- 自定义模型名 --";
        addModel.appendChild(customOpt);
        addModel.value = "__custom__";
        addModel.style.display = "none";
        addModelCustom.style.display = "block";
    }
    addModelCustom.value = "";
    setApiKey.value = "";
    try {
        const r = await fetch("/api/provider-key-status?provider=" + encodeURIComponent(key));
        const d = r.ok ? await r.json() : { has_api_key: false };
        keyStatus.textContent = d.has_api_key ? "\u2713 \u5df2\u914d\u7f6e API Key\uff08\u53ef\u4e0d\u586b\uff0c\u7559\u7a7a\u5219\u6cbf\u7528\uff09" : "\u2717 \u672a\u914d\u7f6e API Key";
        keyStatus.className = "key-status " + (d.has_api_key ? "ok" : "no");
    } catch (e) {
        keyStatus.textContent = "\u2717 \u672a\u914d\u7f6e API Key";
        keyStatus.className = "key-status no";
    }
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
        item.querySelector(".btn-edit-model").addEventListener("click", async () => {
            await openManageModels();
            btnSaveApiConfig.dataset.fromList = "1";
            addProvider.value = m.provider;
            await onAddProviderChange();
            setBaseUrl.value = m.base_url || "";
            if (addModel.querySelector('option[value="' + m.model + '"]')) {
                addModel.value = m.model;
                addModel.style.display = "";
                addModelCustom.style.display = "none";
            } else {
                addModel.value = "__custom__";
                addModelCustom.value = m.model;
                addModelCustom.style.display = "block";
                const ep = providers[m.provider];
                addModel.style.display = (ep && ep.models && ep.models.length > 0) ? "" : "none";
            }
            btnSaveApiConfig.dataset.editingKey = m.provider + "|" + m.model;
            btnSaveApiConfig.textContent = "保存修改";
            modelConfigTitle.textContent = "编辑模型";
        });
        item.querySelector(".btn-remove-model").addEventListener("click", async () => {
            const ok = await confirmDialog("确定要删除模型「" + (m.name || m.model) + "」吗？此操作不可恢复。", { title: "删除模型", icon: "\u{1F5D1}\uFE0F", okText: "删除" });
            if (!ok) return;
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
    if (apiKeyVal) payload.api_key = apiKeyVal;
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
        if (apiKeyVal) {
            keyStatus.textContent = "✓ 已配置 API Key";
            keyStatus.className = "key-status ok";
        }
        await buildQuickModelList();
        const fromList = btnSaveApiConfig.dataset.fromList === "1";
        btnSaveApiConfig.dataset.fromList = "";
        modelManageOverlay.classList.remove("active");
        if (fromList) {
            await renderCustomModelList();
        } else {
            await openModelList();
        }
    } catch (err) {
        showToast("保存失败: " + err.message, "error");
    }
}



// ==================== 对话管理 ====================
let convCache = [];
let projectsCache = [];
let editingProjectId = null;
let expandedProjects = {};
let convSearchKeyword = "";

const CONV_MENU_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16"><circle cx="5" cy="12" r="1.6"></circle><circle cx="12" cy="12" r="1.6"></circle><circle cx="19" cy="12" r="1.6"></circle></svg>';

async function loadConversations() {
    const [convResp, projResp] = await Promise.all([
        fetch("/api/conversations"),
        fetch("/api/projects")
    ]);
    const list = await convResp.json();
    projectsCache = projResp.ok ? await projResp.json() : [];
    convCache = list;
    renderConvList(list);
}

function closeConvMenus() {
    document.querySelectorAll(".conv-menu.open").forEach(m => m.classList.remove("open"));
}

if (convList) {
    convList.addEventListener("scroll", () => {
        if (document.querySelector(".conv-menu.open")) closeConvMenus();
    });
}

function buildConvItem(c) {
    const item = document.createElement("div");
    item.className = "conv-item" + (c.id === currentConvId ? " active" : "");
    item.dataset.id = c.id;
    const inProject = !!(c.project_id && projectsCache.some(p => p.id === c.project_id));
    let menuHtml =
        '<button class="conv-menu-item" data-act="rename">重命名</button>' +
        '<button class="conv-menu-item" data-act="share">分享</button>';
    if (!inProject) {
        menuHtml += '<button class="conv-menu-item" data-act="pin">' + (c.pinned ? "取消置顶" : "置顶") + '</button>';
    }
    menuHtml +=
        '<div class="conv-menu-sub-wrap">' +
        '<button class="conv-menu-item has-submenu" data-act="move">移动<span class="submenu-arrow">\u203A</span></button>' +
        '<div class="conv-submenu"></div>' +
        '</div>';
    if (inProject) {
        menuHtml += '<button class="conv-menu-item" data-act="moveout">移出项目</button>';
    }
    menuHtml += '<button class="conv-menu-item danger" data-act="delete">删除</button>';
    item.innerHTML =
        '<span class="conv-item-icon">💬</span>' +
        '<span class="conv-item-title">' + escapeHtml(c.title) + '</span>' +
        '<button class="conv-item-more" title="更多">' + CONV_MENU_SVG + '</button>' +
        '<div class="conv-menu">' + menuHtml + '</div>';
    item.addEventListener("click", e => {
        if (e.target.closest(".conv-item-more") || e.target.closest(".conv-menu")) return;
        switchConversation(c.id);
    });
    const moreBtn = item.querySelector(".conv-item-more");
    const menu = item.querySelector(".conv-menu");
    moreBtn.addEventListener("click", e => {
        e.stopPropagation();
        const wasOpen = menu.classList.contains("open");
        closeConvMenus();
        if (!wasOpen) {
            fillMoveSubmenu(menu, c);
            menu.classList.add("open");
            const btnRect = moreBtn.getBoundingClientRect();
            menu.style.visibility = "hidden";
            const menuRect = menu.getBoundingClientRect();
            let left = btnRect.right + 6;
            let top = btnRect.top;
            if (left + menuRect.width > window.innerWidth - 8) {
                left = btnRect.left - menuRect.width - 6;
            }
            if (top + menuRect.height > window.innerHeight - 8) {
                top = window.innerHeight - menuRect.height - 8;
            }
            if (top < 8) top = 8;
            if (left < 8) left = 8;
            menu.style.left = left + "px";
            menu.style.top = top + "px";
            menu.style.visibility = "";
        }
    });
    menu.querySelectorAll(".conv-menu-item").forEach(btn => {
        btn.addEventListener("click", async e => {
            e.stopPropagation();
            if (btn.dataset.act === "move") return;
            closeConvMenus();
            const act = btn.dataset.act;
            if (act === "rename") await renameConversation(c);
            else if (act === "share") await shareConversation(c);
            else if (act === "pin") await togglePinConversation(c);
            else if (act === "moveout") await moveConversationTo(c, "");
            else if (act === "delete") await deleteConversation(c.id);
        });
    });
    return item;
}

function renderProjects(groupedConvs, kw) {
    if (projectsCache.length === 0) return;
    const byProject = {};
    groupedConvs.forEach(c => {
        (byProject[c.project_id] = byProject[c.project_id] || []).push(c);
    });
    projectsCache.forEach(p => {
        const items = (byProject[p.id] || []).slice()
            .sort((a, b) => (b.updated || 0) - (a.updated || 0));
        if (kw && items.length === 0) return;
        const expanded = expandedProjects[p.id] !== false;

        const group = document.createElement("div");
        group.className = "project-group";

        const head = document.createElement("div");
        head.className = "project-head";
        head.innerHTML =
            '<span class="project-caret' + (expanded ? " open" : "") + '">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="9 18 15 12 9 6"></polyline></svg>' +
            '</span>' +
            '<span class="project-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg></span>' +
            '<span class="project-name" title="' + escapeHtml(p.name) + '">' + escapeHtml(p.name) + '</span>' +
            '<button class="project-add" title="在此项目新建对话"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg></button>' +
            '<button class="conv-item-more project-more" title="更多">' + CONV_MENU_SVG + '</button>' +
            '<div class="conv-menu">' +
            '<button class="conv-menu-item" data-act="edit">编辑项目</button>' +
            '<button class="conv-menu-item danger" data-act="delete">删除项目</button>' +
            '</div>';

        head.addEventListener("click", e => {
            if (e.target.closest(".project-add") || e.target.closest(".project-more") || e.target.closest(".conv-menu")) return;
            expandedProjects[p.id] = !expanded;
            renderConvList(convCache);
        });
        head.querySelector(".project-add").addEventListener("click", e => {
            e.stopPropagation();
            createNewConversation(p.id);
        });
        const moreBtn = head.querySelector(".project-more");
        const menu = head.querySelector(".conv-menu");
        moreBtn.addEventListener("click", e => {
            e.stopPropagation();
            const wasOpen = menu.classList.contains("open");
            closeConvMenus();
            if (!wasOpen) {
                menu.classList.add("open");
                const btnRect = moreBtn.getBoundingClientRect();
                menu.style.visibility = "hidden";
                const menuRect = menu.getBoundingClientRect();
                let left = btnRect.right + 6;
                let top = btnRect.top;
                if (left + menuRect.width > window.innerWidth - 8) left = btnRect.left - menuRect.width - 6;
                if (top + menuRect.height > window.innerHeight - 8) top = window.innerHeight - menuRect.height - 8;
                if (top < 8) top = 8;
                if (left < 8) left = 8;
                menu.style.left = left + "px";
                menu.style.top = top + "px";
                menu.style.visibility = "";
            }
        });
        menu.querySelectorAll(".conv-menu-item").forEach(btn => {
            btn.addEventListener("click", async e => {
                e.stopPropagation();
                closeConvMenus();
                const act = btn.dataset.act;
                if (act === "edit") openProjectModal(p);
                else if (act === "delete") await deleteProject(p);
            });
        });
        group.appendChild(head);

        if (expanded) {
            const body = document.createElement("div");
            body.className = "project-body";
            if (items.length === 0) {
                const hint = document.createElement("div");
                hint.className = "project-empty-hint";
                hint.textContent = "暂无对话";
                body.appendChild(hint);
            } else {
                items.forEach(c => body.appendChild(buildConvItem(c)));
            }
            group.appendChild(body);
        }
        convList.appendChild(group);
    });
}

function openProjectModal(project) {
    editingProjectId = project ? project.id : null;
    projectPanelTitle.textContent = project ? "编辑项目" : "新建项目";
    projectName.value = project ? (project.name || "") : "";
    projectPrompt.value = project ? (project.system_prompt || "") : "";

    projectProvider.innerHTML = '<option value="">使用全局模型</option>';
    for (const [key, val] of providerEntriesCustomFirst()) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        projectProvider.appendChild(opt);
    }
    projectProvider.value = project ? (project.provider || "") : "";
    onProjectProviderChange();
    if (project && project.model) projectModel.value = project.model;
    projectProvider.onchange = onProjectProviderChange;

    renderProjectKb(project);
    projectOverlay.classList.add("active");
    projectName.focus();
}

function closeProjectModal() {
    projectOverlay.classList.remove("active");
    editingProjectId = null;
}

function onProjectProviderChange() {
    const key = projectProvider.value;
    projectModel.innerHTML = '<option value="">使用全局模型</option>';
    if (!key) return;
    const p = providers[key];
    if (p && p.models) {
        p.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            projectModel.appendChild(opt);
        });
    }
}

async function saveProject() {
    const name = projectName.value.trim();
    if (!name) { showToast("请输入项目名称", "error"); return; }
    const payload = {
        name: name,
        system_prompt: projectPrompt.value,
        provider: projectProvider.value,
        model: projectModel.value,
        base_url: ""
    };
    if (payload.provider) {
        const p = providers[payload.provider];
        if (p) payload.base_url = p.base_url || "";
    }
    try {
        let resp;
        if (editingProjectId) {
            resp = await fetch("/api/projects/" + editingProjectId, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        } else {
            resp = await fetch("/api/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
        }
        if (resp.ok) {
            const saved = await resp.json().catch(() => ({}));
            const wasNew = !editingProjectId;
            showToast(wasNew ? "项目已创建" : "项目已更新", "success");
            await loadConversations();
            if (wasNew && saved && saved.id) {
                editingProjectId = saved.id;
                await renderProjectKb(saved);
                btnKbUpload.disabled = false;
                return;
            }
            closeProjectModal();
        } else {
            const err = await resp.json().catch(() => ({}));
            showToast(err.error || "保存失败", "error");
        }
    } catch (e) {
        showToast("保存失败", "error");
    }
}

async function deleteProject(p) {
    const ok = await confirmDialog("删除项目「" + (p.name || "") + "」？项目内的对话不会被删除，会移到未分组。", {
        title: "删除项目",
        icon: "\u{1F5D1}\uFE0F",
        okText: "删除"
    });
    if (!ok) return;
    const resp = await fetch("/api/projects/" + p.id, { method: "DELETE" });
    if (resp.ok) {
        showToast("项目已删除", "success");
        await loadConversations();
    } else {
        showToast("删除失败", "error");
    }
}

function formatKbSize(bytes) {
    if (bytes >= 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
    return bytes + " B";
}

function renderKbItems(files) {
    projectKbList.innerHTML = "";
    if (!files || files.length === 0) {
        const hint = document.createElement("div");
        hint.className = "project-kb-empty";
        hint.textContent = "还没有文件";
        projectKbList.appendChild(hint);
        return;
    }
    files.forEach(f => {
        const row = document.createElement("div");
        row.className = "project-kb-item";
        row.innerHTML =
            '<span class="kb-item-name" title="' + escapeHtml(f.name) + '">' + escapeHtml(f.name) + '</span>' +
            '<span class="kb-item-size">' + formatKbSize(f.size || 0) + '</span>' +
            '<button class="kb-item-del" title="删除">✕</button>';
        row.querySelector(".kb-item-del").addEventListener("click", () => deleteKbFile(f));
        projectKbList.appendChild(row);
    });
}

async function renderProjectKb(project) {
    if (!project || !project.id) {
        projectKbList.innerHTML = "";
        const hint = document.createElement("div");
        hint.className = "project-kb-empty";
        hint.textContent = "保存项目后即可上传文件";
        projectKbList.appendChild(hint);
        btnKbUpload.disabled = true;
        return;
    }
    btnKbUpload.disabled = false;
    try {
        const resp = await fetch("/api/projects/" + project.id + "/files");
        const files = resp.ok ? await resp.json() : [];
        renderKbItems(files);
    } catch (e) {
        renderKbItems([]);
    }
}

function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file, "utf-8");
    });
}

async function uploadKbFiles(fileList) {
    if (!editingProjectId) { showToast("请先保存项目", "error"); return; }
    let okCount = 0;
    for (const file of fileList) {
        try {
            const content = await readFileAsText(file);
            const resp = await fetch("/api/projects/" + editingProjectId + "/files", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: file.name, content: content })
            });
            if (resp.ok) { okCount++; }
            else {
                const err = await resp.json().catch(() => ({}));
                showToast((file.name || "文件") + "：" + (err.error || "上传失败"), "error");
            }
        } catch (e) {
            showToast((file.name || "文件") + "：读取失败", "error");
        }
    }
    if (okCount > 0) showToast("已上传 " + okCount + " 个文件", "success");
    const proj = projectsCache.find(p => p.id === editingProjectId) || { id: editingProjectId };
    await renderProjectKb(proj);
}

async function deleteKbFile(f) {
    if (!editingProjectId) return;
    const ok = await confirmDialog("删除文件「" + (f.name || "") + "」？", { title: "删除文件", okText: "删除" });
    if (!ok) return;
    const resp = await fetch("/api/projects/" + editingProjectId + "/files/" + f.id, { method: "DELETE" });
    if (resp.ok) {
        showToast("文件已删除", "success");
        const proj = projectsCache.find(p => p.id === editingProjectId) || { id: editingProjectId };
        await renderProjectKb(proj);
    } else {
        showToast("删除失败", "error");
    }
}

async function moveConversationTo(c, projectId) {
    const resp = await fetch("/api/conversations/" + c.id + "/project", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId || null })
    });
    if (resp.ok) {
        if (projectId) expandedProjects[projectId] = true;
        await loadConversations();
    } else {
        showToast("移动失败", "error");
    }
}

function fillMoveSubmenu(menu, c) {
    const sub = menu.querySelector(".conv-submenu");
    if (!sub) return;
    sub.innerHTML = "";
    if (projectsCache.length === 0) {
        const empty = document.createElement("div");
        empty.className = "conv-submenu-empty";
        empty.textContent = "暂无项目";
        sub.appendChild(empty);
        return;
    }
    projectsCache.forEach(p => {
        const b = document.createElement("button");
        b.className = "conv-menu-item";
        if (c.project_id === p.id) b.style.fontWeight = "600";
        b.textContent = p.name;
        b.addEventListener("click", async e => {
            e.stopPropagation();
            closeConvMenus();
            await moveConversationTo(c, p.id);
        });
        sub.appendChild(b);
    });
}

function renderConvList(list) {
    convList.innerHTML = "";
    const kw = convSearchKeyword.trim().toLowerCase();
    let filtered = list;
    if (kw) filtered = list.filter(c => (c.title || "").toLowerCase().includes(kw));

    const projIds = {};
    projectsCache.forEach(p => { projIds[p.id] = true; });
    const grouped = filtered.filter(c => c.project_id && projIds[c.project_id]);
    const ungrouped = filtered.filter(c => !(c.project_id && projIds[c.project_id]));

    renderProjects(grouped, kw);

    if (filtered.length === 0 && projectsCache.length === 0) {
        const empty = document.createElement("div");
        empty.className = "conv-empty-hint";
        empty.textContent = kw ? "没有匹配的对话" : "还没有对话";
        convList.appendChild(empty);
        return;
    }

    const pinned = ungrouped.filter(c => c.pinned);
    const normal = ungrouped.filter(c => !c.pinned);

    const appendSection = (label, items) => {
        if (items.length === 0) return;
        const sec = document.createElement("div");
        sec.className = "conv-section-label";
        sec.textContent = label;
        convList.appendChild(sec);
        items.forEach(c => convList.appendChild(buildConvItem(c)));
    };

    if (pinned.length > 0) {
        appendSection("置顶", pinned);
    }

    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const DAY = 86400000;
    const buckets = [
        { label: "今天", items: [] },
        { label: "昨天", items: [] },
        { label: "7 天内", items: [] },
        { label: "30 天内", items: [] },
        { label: "2 个月内", items: [] },
        { label: "3 个月内", items: [] },
        { label: "1 年内", items: [] },
        { label: "更早", items: [] }
    ];

    const sorted = normal.slice().sort((a, b) => (b.updated || 0) - (a.updated || 0));
    sorted.forEach(c => {
        const t = (c.updated || 0) * 1000;
        let idx;
        if (t >= startOfToday) idx = 0;
        else if (t >= startOfToday - DAY) idx = 1;
        else if (t >= startOfToday - 7 * DAY) idx = 2;
        else if (t >= startOfToday - 30 * DAY) idx = 3;
        else if (t >= startOfToday - 60 * DAY) idx = 4;
        else if (t >= startOfToday - 90 * DAY) idx = 5;
        else if (t >= startOfToday - 365 * DAY) idx = 6;
        else idx = 7;
        buckets[idx].items.push(c);
    });

    buckets.forEach(b => appendSection(b.label, b.items));
}

async function renameConversation(c) {
    const name = await promptDialog("重命名对话", c.title || "", { okText: "保存", placeholder: "输入对话名称" });
    if (name === null) return;
    const title = name.trim();
    if (!title || title === c.title) return;
    await fetch("/api/conversations/" + c.id + "/title", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
    });
    if (c.id === currentConvId) headerTitle.textContent = title;
    await loadConversations();
}

async function togglePinConversation(c) {
    await fetch("/api/conversations/" + c.id + "/pin", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pinned: !c.pinned })
    });
    await loadConversations();
}

async function createNewConversation(projectId) {
    // 当前有对话在后台生成时，切到新对话只断开本地观察流并复位按钮，
    // 后端那一路继续跑完并写入历史，避免空白新对话残留“中断”按钮。
    if (isGenerating && currentAbort) {
        try { currentAbort.abort(); } catch (e) {}
        currentAbort = null;
        isGenerating = false;
        generatingConvId = null;
        btnSend.style.display = "";
        btnStop.style.display = "none";
        btnSend.disabled = false;
    }
    const body = { agent_id: currentAgentId };
    if (projectId) body.project_id = projectId;
    const resp = await fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    const conv = await resp.json();
    currentConvId = conv.id;
    if (projectId) expandedProjects[projectId] = true;
    await loadConversations();
    showWelcome();
    headerTitle.textContent = conv.title;
    userInput.focus();
}

async function switchConversation(cid) {
    if (cid === currentConvId && !isGenerating) return;
    // 切走时：不中断后端生成，只断开本地这一路观察（后端会继续跑完并写入历史）
    if (isGenerating) {
        if (currentAbort) {
            try { currentAbort.abort(); } catch (e) {}
            currentAbort = null;
        }
        isGenerating = false;
        generatingConvId = null;
        btnSend.style.display = "";
        btnStop.style.display = "none";
        btnSend.disabled = false;
    }
    currentConvId = cid;
    isBatchRendering = true;
    document.querySelectorAll(".conv-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === cid);
    });
    const resp = await fetch("/api/conversations/" + cid + "/messages");
    const msgs = await resp.json();
    chatArea.innerHTML = "";
    if (typeof clearChatSearch === "function") clearChatSearch();
    if (msgs.length === 0) { showWelcome(); }
    else {
        let lastAiBubble = null;
        convUserCount = 0;
        msgs.forEach(m => {
            const role = m.role === "user" ? "user" : "ai";
            const thisUserIndex = (role === "user") ? convUserCount : undefined;
            if (role === "user") convUserCount++;
            let text = typeof m.content === "string" ? m.content : (m.content.find(c => c.type === "text") || {}).text || "";
            if (role === "user" && typeof text === "string" && text.startsWith("[[ASK_ANSWER]]")) {
                const target = lastAiBubble || addMessage("ai", "");
                renderAskSummaryCard(target, text.slice("[[ASK_ANSWER]]".length));
                return;
            }
            if (role === "ai" && typeof text === "string" && /\[ASK\][\s\S]*?\[\/ASK\]/.test(text)) {
                text = text.replace(/\[ASK\][\s\S]*?\[\/ASK\]/g, "").trim();
            }
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
            const renderedBubble = addMessage(role, text, imgs, historyDocs, thisUserIndex);
            if (role === "ai") {
                lastAiBubble = renderedBubble;
                const aiMsgDiv = renderedBubble.closest(".message");
                attachAiActions(aiMsgDiv, text, { allowRegen: false, ts: m.ts });
            }
        });
        const allMsgs = chatArea.querySelectorAll(".message.ai");
        if (allMsgs.length > 0) {
            const lastAiMsg = allMsgs[allMsgs.length - 1];
            const lastTs = lastAiMsg.dataset.ts ? parseInt(lastAiMsg.dataset.ts, 10) : undefined;
            attachAiActions(lastAiMsg, lastAiMsg.dataset.rawText || "", { allowRegen: true, ts: lastTs });
        }
    }
    isBatchRendering = false;
    chatArea.scrollTop = chatArea.scrollHeight;

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
        await syncQuickModelToAgent();
    }

    // 进入任意对话时，主动询问后端该对话是否仍在后台生成。
    // 这样不仅切对话能续接，刷新页面（JS 状态全丢、generatingConvId 归零）后
    // 重新进入该对话也能接回后台仍在运行的流。
    try {
        const act = await fetch("/api/chat/active/" + cid);
        const aj = act.ok ? await act.json() : { active: false };
        if (aj.active && aj.is_image) {
            pollImageGeneration(cid);
        } else if (aj.active) {
            attachToActiveStream(cid);
        } else if (generatingConvId === cid) {
            generatingConvId = null;
        }
    } catch (e) {
        if (generatingConvId === cid) generatingConvId = null;
    }
}

async function pollImageGeneration(cid) {
    generatingConvId = cid;
    isGenerating = true;
    btnSend.style.display = "none";
    btnStop.style.display = "";
    let made = addAiBubble();
    let bubble = made.bubble;
    if (made.cursor && made.cursor.parentNode) made.cursor.remove();
    showImageLoading(bubble, null);
    chatArea.scrollTop = chatArea.scrollHeight;
    let baseAssistantCount = 0;
    try {
        const r0 = await fetch("/api/conversations/" + cid + "/messages");
        const ms0 = await r0.json();
        baseAssistantCount = ms0.filter(m => m.role === "assistant").length;
    } catch (e) {}
    let stopped = false;
    function finishUI() {
        isGenerating = false;
        generatingConvId = null;
        btnSend.style.display = "";
        btnStop.style.display = "none";
        btnSend.disabled = false;
    }
    while (!stopped) {
        await new Promise(r => setTimeout(r, 1200));
        if (cid !== currentConvId) { finishUI(); return; }
        let done = false, content = null, ts = 0;
        try {
            const act = await fetch("/api/chat/active/" + cid);
            const aj = act.ok ? await act.json() : { active: false };
            if (!aj.active) done = true;
            const r = await fetch("/api/conversations/" + cid + "/messages");
            const ms = await r.json();
            const assistantCount = ms.filter(m => m.role === "assistant").length;
            if (assistantCount > baseAssistantCount) {
                for (let i = ms.length - 1; i >= 0; i--) {
                    if (ms[i].role === "assistant") { content = ms[i].content; ts = ms[i].ts || 0; break; }
                }
            }
        } catch (e) { continue; }
        const hasText = typeof content === "string" && content.length > 0;
        const hasMulti = Array.isArray(content) && content.length > 0;
        if (hasText || hasMulti) {
            const pollBubbleMsg = bubble.closest(".message");
            chatArea.querySelectorAll(".message.ai").forEach(el => {
                if (el !== pollBubbleMsg && el.querySelector(".msg-images")) el.remove();
            });
            removeImageLoading(bubble);
            if (pollBubbleMsg) pollBubbleMsg.remove();
            const text = typeof content === "string" ? content : (content.find(c => c.type === "text") || {}).text || "";
            const imgs = Array.isArray(content) ? content.filter(c => c.type === "image_url").map(c => c.image_url.url) : [];
            const newBubble = addMessage("ai", text, imgs);
            const newMsg = newBubble.closest(".message");
            attachAiActions(newMsg, text, { allowRegen: true, ts: ts || Math.floor(Date.now() / 1000) });
            chatArea.scrollTop = chatArea.scrollHeight;
            stopped = true;
            finishUI();
            await loadConversations();
            return;
        }
        if (done) {
            removeImageLoading(bubble);
            const aiMsg = bubble.closest(".message");
            if (aiMsg) aiMsg.remove();
            stopped = true;
            finishUI();
            await loadConversations();
            return;
        }
    }
}

async function attachToActiveStream(cid) {
    const abortCtrl = new AbortController();
    currentAbort = abortCtrl;
    isGenerating = true;
    generatingConvId = cid;
    btnSend.style.display = "none";
    btnStop.style.display = "";
    // 复用历史里已渲染的最后一条 AI 气泡，避免续接时重复出现两段回复；
    // attach 会从头重放全部事件，刚好覆盖填满这条气泡。
    let bubble, cursor;
    const aiMsgs = chatArea.querySelectorAll(".message.ai");
    const lastAiMsg = aiMsgs.length ? aiMsgs[aiMsgs.length - 1] : null;
    const existingBubble = lastAiMsg ? lastAiMsg.querySelector(".bubble") : null;
    if (existingBubble) {
        lastAiMsg.querySelectorAll(".msg-actions, .ai-actions, .btn-copy, .btn-regen, .btn-retry").forEach(el => el.remove());
        bubble = existingBubble;
        bubble.classList.add("streaming");
        bubble.innerHTML = "";
        cursor = document.createElement("span");
        cursor.className = "stream-cursor";
        bubble.appendChild(cursor);
    } else {
        const made = addAiBubble();
        bubble = made.bubble;
        cursor = made.cursor;
    }
    let fullText = "";
    let reasoningText = "";
    let isReasoning = false;
    let searchStatusText = "";
    let searchSources = [];
    let askPayload = null;
    let streamMsgTs = 0;
    let streamImages = [];
    // 续接（切回/刷新）时恢复滚动黏性：默认跟随到底，用户主动上滚才脱离
    userScrolledUp = false;
    chatArea.scrollTop = chatArea.scrollHeight;
    function rerender() {
        // 在写入新内容之前测量是否贴底，避免插入大标题块（高度增量>阈值）导致误判离底而停止跟随
        const wasAtBottom = !userScrolledUp && (chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < 30);
        if (cursor.parentNode) cursor.remove();
        let html = "";
        if (searchStatusText) html += '<div class="search-status">🌐 ' + escapeHtml(searchStatusText) + '</div>';
        if (reasoningText) {
            const summary = isReasoning ? "思考中..." : "已深度思考";
            html += '<details class="reasoning-block"' + (isReasoning ? ' open' : '') + '><summary>' + summary + '</summary><div class="reasoning-content">' + renderMarkdown(reasoningText) + '</div></details>';
        }
        if (fullText) html += renderMarkdown(fullText);
        bubble.innerHTML = html;
        bubble.appendChild(cursor);
        if (wasAtBottom) chatArea.scrollTop = chatArea.scrollHeight;
    }
    try {
        const resp = await fetch("/api/chat/attach/" + cid, { signal: abortCtrl.signal });
        if (!resp.ok) {
            const m = bubble.closest(".message");
            if (m) m.remove();
            generatingConvId = null;
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
                        removeImageLoading(bubble);
                        bubble.textContent = "";
                        const errDiv = document.createElement("div");
                        errDiv.className = "error-msg";
                        errDiv.textContent = parsed.error;
                        bubble.appendChild(errDiv);
                        appendErrorHelpLink(bubble);
                        break;
                    }
                    if (parsed.replace) { fullText = parsed.replace; rerender(); }
                    if (parsed.reasoning_start) isReasoning = true;
                    if (parsed.reasoning) { reasoningText += parsed.reasoning; rerender(); }
                    if (parsed.reasoning_end) { isReasoning = false; rerender(); }
                    if (parsed.chunk) { removeImageLoading(bubble); fullText += parsed.chunk; rerender(); }
                    if (parsed.search_status) { searchStatusText = parsed.search_status; rerender(); }
                    if (parsed.sources) searchSources = parsed.sources;
                    if (parsed.image_loading) showImageLoading(bubble, cursor);
                    if (parsed.images) { streamImages = parsed.images; removeImageLoading(bubble); }
                    if (parsed.ask) askPayload = parsed.ask;
                    if (parsed.compress) showCompressNotice(parsed.compress.threshold_kb);
                    if (parsed.ts) streamMsgTs = parsed.ts;
                } catch { fullText += data; rerender(); }
            }
        }
    } catch (err) {
        if (err.name === "AbortError") {
            if (cursor.parentNode) cursor.remove();
            return;
        }
    } finally {
        if (currentAbort === abortCtrl) {
            currentAbort = null;
            isGenerating = false;
            generatingConvId = null;
            btnSend.style.display = "";
            btnStop.style.display = "none";
            btnSend.disabled = false;
        }
        if (cursor.parentNode) cursor.remove();
    }
    if (askPayload) {
        fullText = fullText.replace(/\[ASK\][\s\S]*?\[\/ASK\]/g, "").trim();
        if (askPayload.prefix) fullText = String(askPayload.prefix);
    }
    bubble.classList.remove("streaming");
    let finalHtml = "";
    if (reasoningText) finalHtml += '<details class="reasoning-block"><summary>已深度思考</summary><div class="reasoning-content">' + renderMarkdown(reasoningText) + '</div></details>';
    if (fullText) {
        const rendered = renderCallBlocks(fullText);
        if (rendered) { const tmp = document.createElement("div"); tmp.appendChild(rendered); finalHtml += tmp.innerHTML; }
        else finalHtml += renderMarkdown(fullText);
    }
    if (searchStatusText) finalHtml = '<div class="search-status">🌐 ' + escapeHtml(searchStatusText) + '</div>' + finalHtml;
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
    if (finalHtml || (streamImages && streamImages.length)) {
        bubble.innerHTML = finalHtml;
        if (streamImages && streamImages.length) appendBubbleImages(bubble, streamImages);
        if (askPayload && askPayload.questions && askPayload.questions.length) {
            renderAskCard(bubble, askPayload.questions);
        } else {
            const aiMsgDiv = bubble.closest(".message");
            attachAiActions(aiMsgDiv, fullText, { allowRegen: true, ts: streamMsgTs || Math.floor(Date.now() / 1000) });
        }
    }
    if ((!streamImages || !streamImages.length) && cid === currentConvId) {
        try {
            const r = await fetch("/api/conversations/" + cid + "/messages");
            const ms = await r.json();
            for (let i = ms.length - 1; i >= 0; i--) {
                const mm = ms[i];
                if (mm.role !== "assistant") continue;
                if (typeof mm.content === "string") break;
                const imgs = mm.content.filter(c => c.type === "image_url").map(c => c.image_url.url);
                if (imgs.length && !bubble.querySelector(".msg-images")) {
                    appendBubbleImages(bubble, imgs);
                }
                break;
            }
        } catch (e) {}
    }
    await loadConversations();
}

async function deleteConversation(cid) {
    const conv = convCache.find(c => c.id === cid);
    const title = (conv && conv.title) ? conv.title : "该对话";
    const ok = await confirmDialog("删除对话「" + title + "」？此操作不可恢复。", {
        title: "删除对话",
        icon: "\u{1F5D1}\uFE0F",
        okText: "删除"
    });
    if (!ok) return;
    await fetch("/api/conversations/" + cid, { method: "DELETE" });
    if (currentConvId === cid) { currentConvId = null; showWelcome(); headerTitle.textContent = "AI Chat"; }
    await loadConversations();
}

function showWelcome() { chatArea.innerHTML = welcomeHTML; convUserCount = 0; }
function hideWelcome() { const w = chatArea.querySelector(".welcome"); if (w) w.remove(); }

// ==================== 消息渲染与发送 ====================
let userScrolledUp = false;
let isBatchRendering = false;

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

function _makeImgWrap(src, allSrcs) {
    const wrap = document.createElement("div");
    wrap.className = "msg-img-wrap";
    const el = document.createElement("img");
    el.src = src;
    el.addEventListener("click", () => { const allImgs = Array.from(chatArea.querySelectorAll(".msg-images img")).map(i => i.src).filter(Boolean); openImageViewer(src, allImgs.length ? allImgs : [src]); });
    const dl = document.createElement("a");
    dl.className = "msg-img-dl";
    dl.title = "下载图片";
    dl.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="14" height="14"><path d="M12 15V3"/><polyline points="7 10 12 15 17 10"/><line x1="5" y1="21" x2="19" y2="21"/></svg>';
    dl.addEventListener("click", e => {
        e.stopPropagation();
        const a = document.createElement("a");
        a.href = src;
        a.download = "image-" + Date.now() + ".png";
        a.click();
    });
    wrap.appendChild(el);
    wrap.appendChild(dl);
    return wrap;
}

function addMessage(role, content, images, docs, userIndex) {
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
        if (images && images.length > 0) {
            const imgRow = document.createElement("div");
            imgRow.className = "msg-images";
            const allSrcs = images.map(img => typeof img === "string" ? img : img.base64);
            images.forEach(img => {
                const src = typeof img === "string" ? img : img.base64;
                imgRow.appendChild(_makeImgWrap(src, allSrcs));
            });
            bubble.appendChild(imgRow);
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
            const allSrcs = images.map(img => typeof img === "string" ? img : img.base64);
            images.forEach(img => {
                const src = typeof img === "string" ? img : img.base64;
                imgRow.appendChild(_makeImgWrap(src, allSrcs));
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
    if (role === "user") {
        const uIdx = (typeof userIndex === "number") ? userIndex : convUserCount;
        appendUndoButton(div, content, images, docs, uIdx);
    }
    chatArea.appendChild(div);
    if (!isBatchRendering) chatArea.scrollTop = chatArea.scrollHeight;
    return bubble;
}

function appendBubbleImages(bubble, urls) {
    if (!urls || !urls.length) return;
    const imgRow = document.createElement("div");
    imgRow.className = "msg-images";
    const allSrcs = urls.map(u => typeof u === "string" ? u : ((u && (u.url || u.base64)) || "")).filter(Boolean);
    urls.forEach(u => {
        const src = typeof u === "string" ? u : ((u && (u.url || u.base64)) || "");
        if (!src) return;
        imgRow.appendChild(_makeImgWrap(src, allSrcs));
    });
    bubble.appendChild(imgRow);
}

function showImageLoading(bubble, cursor) {
    if (!bubble || bubble.querySelector(".img-loading")) return;
    if (cursor && cursor.parentNode) cursor.remove();
    const box = document.createElement("div");
    box.className = "img-loading";
    box.innerHTML = '<span class="img-loading-spinner"></span><span class="img-loading-text">正在生成图片，请稍候…</span>';
    bubble.appendChild(box);
}

function removeImageLoading(bubble) {
    if (!bubble) return;
    const box = bubble.querySelector(".img-loading");
    if (box) box.remove();
}

function openImageViewer(src, allSrcs) {
    const srcs = (allSrcs && allSrcs.length) ? allSrcs : [src];
    let idx = srcs.indexOf(src);
    if (idx < 0) idx = 0;

    const overlay = document.createElement("div");
    overlay.className = "image-viewer-overlay";

    const img = document.createElement("img");
    img.src = srcs[idx];

    const btnPrev = document.createElement("button");
    btnPrev.className = "image-viewer-nav prev";
    btnPrev.innerHTML = '<svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg>';
    btnPrev.addEventListener("click", e => { e.stopPropagation(); idx = (idx - 1 + srcs.length) % srcs.length; img.src = srcs[idx]; updateNav(); });

    const btnNext = document.createElement("button");
    btnNext.className = "image-viewer-nav next";
    btnNext.innerHTML = '<svg viewBox="0 0 24 24"><polyline points="9 6 15 12 9 18"/></svg>';
    btnNext.addEventListener("click", e => { e.stopPropagation(); idx = (idx + 1) % srcs.length; img.src = srcs[idx]; updateNav(); });

    const counter = document.createElement("div");
    counter.className = "image-viewer-counter";

    function updateNav() {
        if (srcs.length <= 1) {
            btnPrev.classList.add("hidden");
            btnNext.classList.add("hidden");
            counter.style.display = "none";
        } else {
            btnPrev.classList.remove("hidden");
            btnNext.classList.remove("hidden");
            counter.style.display = "";
            counter.textContent = (idx + 1) + " / " + srcs.length;
        }
    }

    overlay.appendChild(btnPrev);
    overlay.appendChild(img);
    overlay.appendChild(btnNext);
    overlay.appendChild(counter);
    updateNav();

    overlay.addEventListener("click", e => { if (e.target === overlay || e.target === img) overlay.remove(); });

    document.addEventListener("keydown", function onKey(e) {
        if (e.key === "Escape") { overlay.remove(); document.removeEventListener("keydown", onKey); }
        else if (e.key === "ArrowLeft" && srcs.length > 1) { idx = (idx - 1 + srcs.length) % srcs.length; img.src = srcs[idx]; updateNav(); }
        else if (e.key === "ArrowRight" && srcs.length > 1) { idx = (idx + 1) % srcs.length; img.src = srcs[idx]; updateNav(); }
    });

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


async function retryLastMessage(payload) {
    if (isGenerating || !currentConvId) return;
    payload = payload || {};
    const retryText = payload.text || "";
    const retryImages = Array.isArray(payload.images) ? payload.images.slice() : [];
    const retryDocs = Array.isArray(payload.docs) ? payload.docs.slice() : [];
    if (!retryText && retryImages.length === 0 && retryDocs.length === 0) return;
    // 清掉后端残留的失败用户消息，避免重发后历史里出现重复
    try {
        await fetch("/api/conversations/" + currentConvId + "/retry", { method: "POST" });
    } catch (e) {}
    // 删掉聊天区里失败的那一轮（用户气泡 + 错误气泡）
    const messages = chatArea.querySelectorAll(".message");
    if (messages.length >= 2) {
        messages[messages.length - 1].remove();
        messages[messages.length - 2].remove();
    } else if (messages.length >= 1) {
        messages[messages.length - 1].remove();
    }
    convUserCount = Math.max(0, convUserCount - 1);
    // 用失败时的原始内容直接重新发送（不退回输入框）
    pendingImages = retryImages;
    pendingDocs = retryDocs;
    if (retryImages.length === 0 && retryDocs.length === 0) {
        await sendMessage(retryText);
    } else {
        userInput.value = retryText;
        renderPreviews();
        autoResize();
        await sendMessage();
    }
}

function appendErrorHelpLink(container) {
    if (!container || container.querySelector(".error-help-link")) return;
    const link = document.createElement("a");
    link.className = "error-help-link";
    link.href = "javascript:void(0)";
    link.textContent = "为什么会出错？点击查看可能的原因";
    link.addEventListener("click", function (e) {
        e.preventDefault();
        showErrorHelp();
    });
    container.appendChild(link);
}

const ERROR_HELP_SECTIONS = [
    {
        title: "服务器返回的报错（带数字代码）",
        desc: "提示里出现类似 [400] [413] [429] 这样的数字，说明请求已经发到 AI 服务那边，但被拒绝了。下面是常见数字的可能原因：",
        items: [
            ["400 / 422", "请求格式或参数被拒绝。多半是模型名填错、消息内容不被该模型支持，或带了它不认识的参数。可换个模型再试。"],
            ["401 / 403", "鉴权没通过。API Key 填错、过期、被封，或这个 Key 没有调用该模型的权限。请到设置里核对或更换 Key。"],
            ["402", "账户欠费 / 余额不足 / 额度用尽。请到对应服务商充值或检查套餐。"],
            ["404", "找不到模型或接口地址。多半是模型名拼错，或 API 地址（base url）填错了。"],
            ["408 / 504", "服务器响应超时。一般是对方繁忙或网络拥堵，稍等一会儿重试通常就好。"],
            ["413", "发送的内容太大（Payload Too Large）。常见于一次性发了过大的图片或过长的文本/文档，缩小图片、删减内容或分批发送即可。"],
            ["429", "请求太频繁或达到调用上限。降低发送频率、稍后再试，或检查服务商的限速与配额。"],
            ["500 / 502 / 503", "服务商自己那边出故障了，和你的设置无关，通常过一会儿会自动恢复，重试即可。"]
        ]
    },
    {
        title: "网络连接问题（连不上 / 超时）",
        desc: "提示里出现“连接超时”“无法连接”“网络错误”等字样，说明请求没能正常发出去或没收到回复，问题多在本机网络或地址：",
        items: [
            ["连接超时 / 无法连接", "连不上服务器。检查本机网络是否正常，确认 API 地址填写正确且能访问（有些地址需要代理）。"],
            ["读取超时", "已经连上了，但等回复等太久。可能模型生成慢或服务繁忙，稍后重试，或换个更快的模型。"],
            ["SSL / 证书错误", "加密连接握手失败。检查 API 地址是否正确、系统时间是否准、代理设置是否异常。"],
            ["代理错误", "走了代理但代理不通。检查本机代理设置，或先关闭代理再试。"]
        ]
    },
    {
        title: "发送前就被拦下的提示",
        desc: "这类提示在请求还没发出去时就出现，通常是配置或操作问题，按提示处理即可：",
        items: [
            ["未配置 API Key", "还没在设置里填 Key，去「设置」填入有效的 API Key。"],
            ["未选择模型", "当前没选模型，在右下角选一个，或先在设置里添加模型。"],
            ["消息不能为空", "没输入内容也没带图片就点了发送，输入后再发。"],
            ["对话正在生成中", "上一条还没生成完又发了新消息，等它结束或点停止后再发。"],
            ["对话不存在", "当前对话可能已被删除或状态过期，刷新页面后重新进入或新建对话。"]
        ]
    },
    {
        title: "实在排查不出时",
        desc: "可以按下面顺序逐项排查：",
        items: [
            ["1. 先点重试", "很多错误（超时、服务商抖动）重试一下就好。"],
            ["2. 查网络", "确认能正常打开其它网页。"],
            ["3. 查设置", "核对 API Key、API 地址、模型名是否正确。"],
            ["4. 换模型", "换个模型再试，排除某个模型本身的问题。"],
            ["5. 查图片", "如果带了图片，确认所用模型支持图片输入。"]
        ]
    }
];

function showErrorHelp() {
    let overlay = document.getElementById("error-help-overlay");
    if (!overlay) {
        overlay = document.createElement("div");
        overlay.id = "error-help-overlay";
        overlay.className = "error-help-overlay";
        const dialog = document.createElement("div");
        dialog.className = "error-help-dialog";

        const head = document.createElement("div");
        head.className = "error-help-head";
        const h = document.createElement("div");
        h.className = "error-help-title";
        h.textContent = "报错原因速查";
        const closeBtn = document.createElement("button");
        closeBtn.className = "error-help-close";
        closeBtn.innerHTML = "&times;";
        closeBtn.setAttribute("aria-label", "关闭");
        head.appendChild(h);
        head.appendChild(closeBtn);

        const body = document.createElement("div");
        body.className = "error-help-body";
        ERROR_HELP_SECTIONS.forEach(sec => {
            const secEl = document.createElement("div");
            secEl.className = "error-help-section";
            const st = document.createElement("h4");
            st.textContent = sec.title;
            secEl.appendChild(st);
            if (sec.desc) {
                const sd = document.createElement("p");
                sd.className = "error-help-desc";
                sd.textContent = sec.desc;
                secEl.appendChild(sd);
            }
            sec.items.forEach(pair => {
                const row = document.createElement("div");
                row.className = "error-help-row";
                const k = document.createElement("span");
                k.className = "error-help-key";
                k.textContent = pair[0];
                const v = document.createElement("span");
                v.className = "error-help-val";
                v.textContent = pair[1];
                row.appendChild(k);
                row.appendChild(v);
                secEl.appendChild(row);
            });
            body.appendChild(secEl);
        });

        dialog.appendChild(head);
        dialog.appendChild(body);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        function close() { overlay.classList.remove("active"); }
        closeBtn.addEventListener("click", close);
        overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
        document.addEventListener("keydown", e => {
            if (e.key === "Escape" && overlay.classList.contains("active")) close();
        });
    }
    overlay.classList.add("active");
}

function appendRetryButton(msgDiv, text, images, docs) {
    const existing = msgDiv.querySelector(".btn-retry");
    if (existing) existing.remove();
    const payload = {
        text: text || "",
        images: Array.isArray(images) ? images.slice() : [],
        docs: Array.isArray(docs) ? docs.slice() : []
    };
    const btn = document.createElement("button");
    btn.className = "btn-retry error-retry";
    btn.title = "重试";
    btn.innerHTML = REGEN_ICON_SVG;
    btn.addEventListener("click", () => retryLastMessage(payload));
    msgDiv.appendChild(btn);
}

function markFailedUserMessage(aiMsgDiv, text, images, docs) {
    if (!aiMsgDiv) return;
    let userMsg = aiMsgDiv.previousElementSibling;
    while (userMsg && !userMsg.classList.contains("user")) {
        userMsg = userMsg.previousElementSibling;
    }
    if (!userMsg) return;
    userMsg.dataset.failed = "1";
    const payload = {
        text: text || "",
        images: Array.isArray(images) ? images.slice() : [],
        docs: Array.isArray(docs) ? docs.slice() : []
    };
    const existing = userMsg.querySelector(".btn-undo");
    if (existing) existing.remove();
    const btn = document.createElement("button");
    btn.className = "btn-undo";
    btn.title = "撤回这条未发送成功的消息（内容退回输入框）";
    btn.innerHTML = UNDO_ICON_SVG;
    btn.addEventListener("click", async () => {
        const ok = await confirmDialog("撤回这条未发送成功的消息？内容将退回输入框。", {
            title: "撤回消息",
            icon: "\u21A9\uFE0F",
            okText: "撤回",
            cancelText: "取消"
        });
        if (!ok) return;
        undoFailedMessage(userMsg, aiMsgDiv, payload);
    });
    userMsg.appendChild(btn);
}

function undoFailedMessage(userMsg, aiMsgDiv, payload) {
    if (aiMsgDiv && aiMsgDiv.parentNode) aiMsgDiv.remove();
    if (userMsg && userMsg.parentNode) userMsg.remove();
    if (chatArea.querySelectorAll(".message").length === 0) {
        showWelcome();
    }
    convUserCount = chatArea.querySelectorAll(".message.user").length;

    const hasStructuredDocs = Array.isArray(payload.docs)
        && payload.docs.length > 0
        && payload.docs.every(d => d && typeof d.text === "string" && d.text.length > 0);

    let restoredText;
    if (hasStructuredDocs) {
        pendingDocs = payload.docs.map(d => ({
            name: d.name,
            text: d.text,
            charCount: typeof d.charCount === "number" ? d.charCount : d.text.length,
            truncated: !!d.truncated,
            loading: false
        }));
        restoredText = payload.text != null ? String(payload.text) : "";
    } else {
        restoredText = restorePendingFromText(payload.text || "");
        if (!restoredText && pendingDocs.length === 0 && Array.isArray(payload.docs) && payload.docs.length > 0) {
            pendingDocs = payload.docs.slice();
        }
    }

    if (Array.isArray(payload.images) && payload.images.length > 0) {
        pendingImages = payload.images.map((img, i) => ({
            name: "image_" + i,
            base64: (typeof img === "string" ? img : img.base64)
        }));
    } else {
        pendingImages = [];
    }
    renderPreviews();

    userInput.value = restoredText;
    autoResize();
    userInput.focus();
}

const UNDO_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><path d="M9 14L4 9l5-5"></path><path d="M4 9h11a5 5 0 0 1 5 5v0a5 5 0 0 1-5 5H9"></path></svg>';

function appendUndoButton(msgDiv, userText, images, docs, userIndex) {
    const existing = msgDiv.querySelector(".btn-undo");
    if (existing) existing.remove();
    if (typeof userIndex === "number") {
        msgDiv.dataset.userIndex = String(userIndex);
    }
    const btn = document.createElement("button");
    btn.className = "btn-undo";
    btn.title = "撤回这条消息（会遗忘其后的对话，内容退回输入框）";
    btn.innerHTML = UNDO_ICON_SVG;
    btn.addEventListener("click", async () => {
        const ok = await confirmDialog("撤回这条消息会遗忘其后的所有对话，消息内容将退回输入框。确定撤回吗？", {
            title: "撤回消息",
            icon: "\u21A9\uFE0F",
            okText: "撤回",
            cancelText: "取消"
        });
        if (!ok) return;
        undoMessage(msgDiv, userText, images, docs);
    });
    msgDiv.appendChild(btn);
}

function userMessageIndexOf(msgDiv) {
    const userMsgs = Array.from(chatArea.querySelectorAll(".message.user"));
    return userMsgs.indexOf(msgDiv);
}

function restorePendingFromText(rawText) {
    let text = String(rawText == null ? "" : rawText);
    pendingDocs = [];
    const docRegex = /\[文档: (.+?)\]\n([\s\S]*?)(?=\n\n\[文档:|$)/g;
    let dm;
    const restoredDocs = [];
    while ((dm = docRegex.exec(text)) !== null) {
        const name = dm[1];
        const body = dm[2] || "";
        restoredDocs.push({
            name: name,
            text: body,
            charCount: body.length,
            truncated: false,
            loading: false
        });
    }
    if (restoredDocs.length > 0) {
        const firstDoc = text.indexOf("[文档:");
        if (firstDoc === 0) {
            const afterDocs = text.replace(/^(\[文档: .+?\]\n[\s\S]*?)(\n\n(?!\[文档:)[\s\S]*)?$/, "$2").replace(/^\n\n/, "");
            text = afterDocs || "";
        }
        pendingDocs = restoredDocs;
    }
    return text;
}

async function undoMessage(msgDiv, fallbackText, fallbackImages, fallbackDocs) {
    if (isGenerating || !currentConvId) return;

    const visibleIndex = userMessageIndexOf(msgDiv);

    let images = (fallbackImages || []).slice();
    const hasStructuredDocs = Array.isArray(fallbackDocs)
        && fallbackDocs.length > 0
        && fallbackDocs.every(d => d && typeof d.text === "string" && d.text.length > 0);

    let serverUserMessage = null;
    let serverImages = null;
    try {
        const resp = await fetch("/api/conversations/" + currentConvId + "/undo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ visible_index: visibleIndex })
        });
        if (resp.ok) {
            const data = await resp.json();
            if (typeof data.user_message === "string") serverUserMessage = data.user_message;
            if (Array.isArray(data.images)) serverImages = data.images;
        }
    } catch (e) {
    }

    const allMsgs = Array.from(chatArea.querySelectorAll(".message"));
    const startIdx = allMsgs.indexOf(msgDiv);
    if (startIdx >= 0) {
        for (let i = allMsgs.length - 1; i >= startIdx; i--) {
            allMsgs[i].remove();
        }
    }
    if (chatArea.querySelectorAll(".message").length === 0) {
        showWelcome();
    }

    convUserCount = chatArea.querySelectorAll(".message.user").length;

    let restoredText;
    if (hasStructuredDocs) {
        pendingDocs = fallbackDocs.map(d => ({
            name: d.name,
            text: d.text,
            charCount: typeof d.charCount === "number" ? d.charCount : d.text.length,
            truncated: !!d.truncated,
            loading: false
        }));
        restoredText = (fallbackText != null) ? String(fallbackText) : "";
    } else {
        const sourceText = (serverUserMessage != null) ? serverUserMessage : (fallbackText || "");
        restoredText = restorePendingFromText(sourceText);
        if (!restoredText && pendingDocs.length === 0 && Array.isArray(fallbackDocs) && fallbackDocs.length > 0) {
            pendingDocs = fallbackDocs.slice();
        }
    }

    if (serverImages && serverImages.length > 0) {
        images = serverImages;
    }
    if (images && images.length > 0) {
        pendingImages = images.map((url, i) => ({ name: "image_" + i, base64: (typeof url === "string" ? url : url.base64) }));
    } else {
        pendingImages = [];
    }
    renderPreviews();

    userInput.value = restoredText;
    autoResize();
    userInput.focus();

    await loadConversations();
}

function renderAskSummaryCard(bubble, answerText) {
    const card = document.createElement("div");
    card.className = "ask-card answered collapsed";

    const head = document.createElement("div");
    head.className = "ask-head";
    const caret = document.createElement("span");
    caret.className = "ask-caret";
    caret.textContent = "\u25B8";
    const headTitle = document.createElement("span");
    headTitle.className = "ask-head-title";
    headTitle.textContent = "\u63D0\u95EE";
    const headProg = document.createElement("span");
    headProg.className = "ask-head-prog";
    headProg.textContent = "\u5DF2\u56DE\u7B54";
    head.appendChild(caret);
    head.appendChild(headTitle);
    head.appendChild(headProg);
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "ask-body";
    const wrap = document.createElement("div");
    wrap.className = "ask-summary";

    const lines = String(answerText).split("\n").filter(l => l.trim() && !l.startsWith("\u3010"));
    lines.forEach(line => {
        const row = document.createElement("div");
        row.className = "ask-sum-row";
        const arrow = line.indexOf("\u2192");
        let q = line, a = "";
        if (arrow >= 0) {
            q = line.slice(0, arrow).trim();
            a = line.slice(arrow + 1).trim();
        } else if (line.startsWith("\u8865\u5145\uFF1A")) {
            q = "\u8865\u5145";
            a = line.slice(3).trim();
        }
        const qEl = document.createElement("div");
        qEl.className = "ask-sum-q";
        qEl.textContent = q;
        const aEl = document.createElement("div");
        aEl.className = "ask-sum-a";
        aEl.textContent = a;
        row.appendChild(qEl);
        if (a) row.appendChild(aEl);
        wrap.appendChild(row);
    });
    body.appendChild(wrap);
    card.appendChild(body);

    head.addEventListener("click", () => {
        const collapsed = card.classList.toggle("collapsed");
        caret.textContent = collapsed ? "\u25B8" : "\u25BE";
    });

    bubble.appendChild(card);
}

function renderAskCard(bubble, questions) {
    // 组装页：原始问题 + 末尾“补充”页
    const pages = questions.map(q => ({
        type: q.type,
        q: q.q || "",
        options: q.options || [],
        optional: false,
        selected: null,
        otherText: "",
        textVal: ""
    }));
    pages.push({
        type: "text",
        q: "还有什么需要补充的吗？",
        options: [],
        optional: true,
        selected: null,
        otherText: "",
        textVal: ""
    });

    let cur = 0;
    let answered = false;

    const card = document.createElement("div");
    card.className = "ask-card";

    // 头部（可折叠）
    const head = document.createElement("div");
    head.className = "ask-head";
    const caret = document.createElement("span");
    caret.className = "ask-caret";
    caret.textContent = "▾";
    const headTitle = document.createElement("span");
    headTitle.className = "ask-head-title";
    headTitle.textContent = "提问";
    const headProg = document.createElement("span");
    headProg.className = "ask-head-prog";
    head.appendChild(caret);
    head.appendChild(headTitle);
    head.appendChild(headProg);
    card.appendChild(head);

    // 主体（分页内容）
    const body = document.createElement("div");
    body.className = "ask-body";
    card.appendChild(body);

    // 底部操作
    const foot = document.createElement("div");
    foot.className = "ask-foot";
    const btnPrev = document.createElement("button");
    btnPrev.type = "button";
    btnPrev.className = "ask-btn ask-btn-ghost";
    btnPrev.textContent = "上一步";
    const btnNext = document.createElement("button");
    btnNext.type = "button";
    btnNext.className = "ask-btn ask-btn-primary";
    btnNext.textContent = "下一步";
    foot.appendChild(btnPrev);
    foot.appendChild(btnNext);
    card.appendChild(foot);

    head.addEventListener("click", () => {
        const collapsed = card.classList.toggle("collapsed");
        caret.textContent = collapsed ? "▸" : "▾";
    });

    function renderSummary() {
        const wrap = document.createElement("div");
        wrap.className = "ask-summary";
        pages.forEach((p, i) => {
            let ans = "";
            if (p.type === "choice") {
                ans = (p.selected === "其他") ? (p.otherText.trim() || "（其他）") : (p.selected || "（未答）");
            } else {
                ans = p.textVal.trim() || (p.optional ? "（无补充）" : "（未答）");
            }
            const row = document.createElement("div");
            row.className = "ask-sum-row";
            const qEl = document.createElement("div");
            qEl.className = "ask-sum-q";
            qEl.textContent = (p.optional ? "补充" : (i + 1) + ". " + p.q);
            const aEl = document.createElement("div");
            aEl.className = "ask-sum-a";
            aEl.textContent = ans;
            row.appendChild(qEl);
            row.appendChild(aEl);
            wrap.appendChild(row);
        });
        return wrap;
    }

    function renderPage() {
        body.innerHTML = "";
        const p = pages[cur];
        headProg.textContent = (cur + 1) + " / " + pages.length;

        const qTitle = document.createElement("div");
        qTitle.className = "ask-q-title";
        qTitle.textContent = (p.optional ? "" : (cur + 1) + ". ") + p.q + (p.optional ? "（可留空）" : "");
        body.appendChild(qTitle);

        if (p.type === "choice") {
            const opts = (p.options || []).concat(["其他"]);
            const optWrap = document.createElement("div");
            optWrap.className = "ask-options";
            const otherInput = document.createElement("input");
            otherInput.type = "text";
            otherInput.className = "ask-other-input";
            otherInput.placeholder = "请描述你的答案…";
            otherInput.value = p.otherText;
            otherInput.style.display = (p.selected === "其他") ? "" : "none";
            otherInput.addEventListener("input", () => { p.otherText = otherInput.value; });
            opts.forEach(opt => {
                const isOther = (opt === "其他");
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "ask-opt" + (p.selected === opt ? " active" : "");
                btn.textContent = opt;
                btn.addEventListener("click", () => {
                    optWrap.querySelectorAll(".ask-opt").forEach(b => b.classList.remove("active"));
                    btn.classList.add("active");
                    p.selected = opt;
                    otherInput.style.display = isOther ? "" : "none";
                    if (isOther) setTimeout(() => otherInput.focus(), 20);
                });
                optWrap.appendChild(btn);
            });
            body.appendChild(optWrap);
            body.appendChild(otherInput);
        } else {
            const ta = document.createElement("textarea");
            ta.className = "ask-text-input";
            ta.rows = 3;
            ta.placeholder = p.optional ? "补充说明（选填）…" : "输入你的回答…";
            ta.value = p.textVal;
            ta.addEventListener("input", () => { p.textVal = ta.value; });
            body.appendChild(ta);
        }

        btnPrev.style.visibility = (cur === 0) ? "hidden" : "visible";
        btnNext.textContent = (cur === pages.length - 1) ? "提交回答" : "下一步";
    }

    btnPrev.addEventListener("click", () => {
        if (cur > 0) { cur--; renderPage(); }
    });

    btnNext.addEventListener("click", () => {
        if (cur < pages.length - 1) {
            cur++;
            renderPage();
            return;
        }
        // 提交
        answered = true;
        card.classList.add("answered");
        headProg.textContent = "已回答";
        foot.remove();
        body.innerHTML = "";
        body.appendChild(renderSummary());
        card.classList.add("collapsed");
        caret.textContent = "▸";

        const lines = [];
        let anyAnswered = false;
        pages.forEach((p, i) => {
            if (p.optional) {
                const sup = p.textVal.trim();
                if (sup) { lines.push("补充：" + sup); anyAnswered = true; }
                return;
            }
            let ans = "";
            if (p.type === "choice") {
                ans = (p.selected === "其他") ? p.otherText.trim() : (p.selected || "");
            } else {
                ans = p.textVal.trim();
            }
            if (ans) {
                anyAnswered = true;
                lines.push((i + 1) + ". " + p.q + " → " + ans);
            } else {
                lines.push((i + 1) + ". " + p.q + " → （未回答，请你自行判断）");
            }
        });
        const head = anyAnswered
            ? "【我对你的提问的回答】（未回答的项请你自行判断、合理猜测，无需再追问）\n"
            : "【我跳过了你的全部提问】请你自行判断、合理猜测后直接继续，无需再追问。\n";
        const answerText = head + lines.join("\n");
        sendMessage(answerText, { askAnswer: true });
    });

    renderPage();
    bubble.appendChild(card);
    if (shouldAutoScroll()) chatArea.scrollTop = chatArea.scrollHeight;
}

function stopGeneration() {
    const cid = generatingConvId || currentConvId;
    if (cid) {
        fetch("/api/chat/stop/" + cid, { method: "POST" }).catch(() => {});
    }
    if (currentAbort) {
        currentAbort.abort();
        currentAbort = null;
    }
    isGenerating = false;
    generatingConvId = null;
    btnSend.style.display = "";
    btnStop.style.display = "none";
    btnSend.disabled = false;
}

async function sendMessage(presetText, opts) {
    userScrolledUp = false;
    const isPreset = (presetText != null);
    const isAskAnswer = !!(opts && opts.askAnswer);
    const text = isPreset ? String(presetText) : userInput.value.trim();
    const hasDoc = !isPreset && pendingDocs.some(d => !d.loading && d.text);
    if (isPreset) {
        if (!text || isGenerating) return;
    } else if ((!text && pendingImages.length === 0 && !hasDoc) || isGenerating) {
        return;
    }
    if (pendingDocs.some(d => d.loading)) {
        showToast("文档正在解析中，请稍候", "error");
        return;
    }

    if (!quickModel.value) {
        showToast("未选择模型，请先在右下角选择一个可用模型", "error");
        return;
    }
    try {
        const sResp = await fetch("/api/settings");
        if (sResp.ok) {
            const sCfg = await sResp.json();
            if (!sCfg.model) {
                showToast("未选择模型，请先在右下角选择一个可用模型", "error");
                return;
            }
            if (!sCfg.has_api_key) {
                showToast("未配置 API Key，请先在设置中配置", "error");
                return;
            }
        }
    } catch (e) {}

    if (!currentConvId) {
        await createNewConversation();
    }

    const abortCtrl = new AbortController();
    currentAbort = abortCtrl;
    isGenerating = true;
    generatingConvId = currentConvId;
    btnSend.style.display = "none";
    btnStop.style.display = "";
    const images = isPreset ? [] : pendingImages.slice();
    const docs = isPreset ? [] : pendingDocs.slice();
    if (!isPreset) {
        pendingImages = [];
        pendingDocs = [];
        renderPreviews();
        userInput.value = "";
        autoResize();
    }

    if (!isAskAnswer) {
        addMessage("user", text, images, docs, convUserCount);
    }
    convUserCount++;
    let renderPending = false;
    let streamEnded = false;
    let rafId = 0;
    let lastRenderTs = 0;
    const MIN_RENDER_INTERVAL = 60;
    function scheduleRender() {
        if (renderPending || streamEnded) return;
        renderPending = true;
        rafId = requestAnimationFrame(() => {
            const now = performance.now();
            if (now - lastRenderTs < MIN_RENDER_INTERVAL && !streamEnded) {
                rafId = requestAnimationFrame(() => { renderPending = false; rafId = 0; scheduleRender(); });
                return;
            }
            lastRenderTs = now;
            renderPending = false;
            rafId = 0;
            if (streamEnded) return;
            // 在写入新内容之前测量是否贴底，避免插入大标题块（高度增量>阈值）导致误判离底而停止跟随
            const wasAtBottom = !userScrolledUp && (chatArea.scrollHeight - chatArea.scrollTop - chatArea.clientHeight < 30);
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
            if (wasAtBottom) chatArea.scrollTop = chatArea.scrollHeight;
        });
    }
    const { bubble, cursor } = addAiBubble();
    let fullText = "";
    let reasoningText = "";
    let isReasoning = false;
    let searchStatusText = "";
    let searchSources = [];
    let askPayload = null;
    let streamMsgTs = 0;
    let streamImages = [];

    let messageText = text;
    if (docs.length > 0) {
        const docParts = docs.map(d => "[文档: " + d.name + "]\n" + d.text).join("\n\n");
        messageText = docParts + (text ? "\n\n" + text : "");
    }
    const payload = { conversation_id: currentConvId, message: messageText };
    if (isAskAnswer) {
        payload.ask_answer = true;
    }
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
            let isBusy = false;
            try {
                const errData = await resp.json();
                if (errData.error) errMsg = errData.error;
                if (errData.busy) isBusy = true;
            } catch {}
            if (isBusy || resp.status === 409) {
                const aiMsg = bubble.closest(".message");
                if (aiMsg) aiMsg.remove();
                if (!isAskAnswer) {
                    const userMsgs = chatArea.querySelectorAll(".message.user");
                    if (userMsgs.length > 0) userMsgs[userMsgs.length - 1].remove();
                    convUserCount = Math.max(0, convUserCount - 1);
                }
                if (!isPreset) {
                    userInput.value = text;
                    autoResize();
                    if (images.length > 0) {
                        pendingImages = images.slice();
                    }
                    if (docs.length > 0) {
                        pendingDocs = docs.slice();
                    }
                    renderPreviews();
                    userInput.focus();
                }
                showToast(errMsg, "error");
                return;
            }
            if (cursor.parentNode) cursor.remove();
            bubble.textContent = "";
            const errDiv = document.createElement("div");
            errDiv.className = "error-msg";
            errDiv.textContent = errMsg;
            bubble.appendChild(errDiv);
            appendErrorHelpLink(bubble);
            appendRetryButton(bubble.closest(".message"), text, images, docs);
            markFailedUserMessage(bubble.closest(".message"), text, images, docs);
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
                        appendErrorHelpLink(bubble);
                        appendRetryButton(bubble.closest(".message"), text, images, docs);
                        markFailedUserMessage(bubble.closest(".message"), text, images, docs);
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
                        removeImageLoading(bubble);
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
                    if (parsed.image_loading) {
                        showImageLoading(bubble, cursor);
                    }
                    if (parsed.images) {
                        streamImages = parsed.images;
                        removeImageLoading(bubble);
                    }
                    if (parsed.ask) {
                        askPayload = parsed.ask;
                    }
                    if (parsed.compress) {
                        showCompressNotice(parsed.compress.threshold_kb);
                    }
                    if (parsed.ts) {
                        streamMsgTs = parsed.ts;
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
            errDiv.textContent = "网络错误，未能连接到服务（" + err.message + "）";
            bubble.appendChild(errDiv);
            appendErrorHelpLink(bubble);
            appendRetryButton(bubble.closest(".message"), text, images, docs);
            markFailedUserMessage(bubble.closest(".message"), text, images, docs);
        }
    } finally {
        streamEnded = true;
        if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
        if (cursor.parentNode) cursor.remove();
        if (currentAbort === abortCtrl) {
            currentAbort = null;
        }
        if (generatingConvId === payload.conversation_id) {
            isGenerating = false;
            generatingConvId = null;
        }
        btnSend.style.display = isGenerating ? "none" : "";
        btnStop.style.display = isGenerating ? "" : "none";
        btnSend.disabled = false;
        userInput.focus();
    }
    if (askPayload) {
        fullText = fullText.replace(/\[ASK\][\s\S]*?\[\/ASK\]/g, "").trim();
        if (askPayload.prefix) fullText = String(askPayload.prefix);
    }
    if (fullText || reasoningText || askPayload || (streamImages && streamImages.length)) {
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
        if (streamImages && streamImages.length) appendBubbleImages(bubble, streamImages);
        if (askPayload && askPayload.questions && askPayload.questions.length) {
            renderAskCard(bubble, askPayload.questions);
        } else {
            const aiMsgDiv = bubble.closest(".message");
            attachAiActions(aiMsgDiv, fullText, { allowRegen: true, ts: streamMsgTs || Math.floor(Date.now() / 1000) });
        }
    }
    await loadConversations();
}

// ==================== 设置面板 ====================
async function openSettings() {
    const resp = await fetch("/api/settings");
    const cfg = resp.ok ? await resp.json() : {};
    setMaxRounds.value = cfg.max_history_rounds || 50;
    setMaxContextSize.value = cfg.max_context_size_kb || 0;
    setAutoCompress.checked = !!cfg.auto_compress;
    setCompressThreshold.value = cfg.compress_threshold_kb || 128;
    updateCompressRow();
    syncAppearanceControls();
    settingsOverlay.classList.add("active");
}

function closeSettings() { settingsOverlay.classList.remove("active"); }

function updateCompressRow() {
    if (!compressThresholdRow) return;
    compressThresholdRow.style.display = setAutoCompress.checked ? "" : "none";
}
if (setAutoCompress) {
    setAutoCompress.addEventListener("change", updateCompressRow);
}



async function saveSettings() {
    const payload = {
        max_history_rounds: parseInt(setMaxRounds.value) || 50,
        max_context_size_kb: parseInt(setMaxContextSize.value) || 0,
        auto_compress: !!setAutoCompress.checked,
        compress_threshold_kb: parseInt(setCompressThreshold.value) || 128
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

// ==================== 外观：主题 / 字号 ====================
const THEME_KEY = "uiTheme";
const FONT_SIZE_KEY = "chatFontSize";
const FONT_SIZE_MIN = 8;
const FONT_SIZE_MAX = 40;
const FONT_SIZE_DEFAULT = 14;

function applyTheme(theme) {
    if (theme === "light") {
        document.documentElement.setAttribute("data-theme", "light");
    } else {
        document.documentElement.removeAttribute("data-theme");
    }
}

function getStoredTheme() {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
}

function applyChatFontSize(px) {
    let v = parseInt(px, 10);
    if (isNaN(v)) v = FONT_SIZE_DEFAULT;
    v = Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, v));
    document.documentElement.style.setProperty("--chat-font-size", v + "px");
    return v;
}

function getStoredFontSize() {
    const v = parseInt(localStorage.getItem(FONT_SIZE_KEY), 10);
    if (isNaN(v)) return FONT_SIZE_DEFAULT;
    return Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, v));
}

function syncAppearanceControls() {
    const themeChk = document.getElementById("set-light-theme");
    if (themeChk) themeChk.checked = getStoredTheme() === "light";
    const fontRange = document.getElementById("set-chat-font-size");
    const fontVal = document.getElementById("chat-font-size-value");
    const cur = getStoredFontSize();
    if (fontRange) fontRange.value = cur;
    if (fontVal) fontVal.textContent = cur + "px";
}

(function initAppearance() {
    applyTheme(getStoredTheme());
    applyChatFontSize(getStoredFontSize());

    const themeChk = document.getElementById("set-light-theme");
    if (themeChk) {
        themeChk.addEventListener("change", () => {
            const theme = themeChk.checked ? "light" : "dark";
            localStorage.setItem(THEME_KEY, theme);
            applyTheme(theme);
        });
    }
    const fontRange = document.getElementById("set-chat-font-size");
    const fontVal = document.getElementById("chat-font-size-value");
    if (fontRange) {
        fontRange.addEventListener("input", () => {
            const v = applyChatFontSize(fontRange.value);
            if (fontVal) fontVal.textContent = v + "px";
            localStorage.setItem(FONT_SIZE_KEY, String(v));
        });
    }
    syncAppearanceControls();
})();

// ==================== 工具函数 ====================
function confirmDialog(message, opts) {
    opts = opts || {};
    return new Promise(resolve => {
        const overlay = document.getElementById("confirm-overlay");
        const titleEl = document.getElementById("confirm-title");
        const msgEl = document.getElementById("confirm-message");
        const iconEl = document.getElementById("confirm-icon");
        const okBtn = document.getElementById("confirm-ok");
        const cancelBtn = document.getElementById("confirm-cancel");
        titleEl.textContent = opts.title || "确认操作";
        msgEl.textContent = message || "";
        iconEl.textContent = opts.icon || "\u26A0\uFE0F";
        okBtn.textContent = opts.okText || "确定";
        cancelBtn.textContent = opts.cancelText || "取消";
        function cleanup(result) {
            overlay.classList.remove("active");
            okBtn.removeEventListener("click", onOk);
            cancelBtn.removeEventListener("click", onCancel);
            overlay.removeEventListener("click", onBackdrop);
            document.removeEventListener("keydown", onKey);
            resolve(result);
        }
        function onOk() { cleanup(true); }
        function onCancel() { cleanup(false); }
        function onBackdrop(e) { if (e.target === overlay) cleanup(false); }
        function onKey(e) {
            if (e.key === "Escape") cleanup(false);
            else if (e.key === "Enter") cleanup(true);
        }
        okBtn.addEventListener("click", onOk);
        cancelBtn.addEventListener("click", onCancel);
        overlay.addEventListener("click", onBackdrop);
        document.addEventListener("keydown", onKey);
        overlay.classList.add("active");
        okBtn.focus();
    });
}

function promptDialog(title, defaultValue, opts) {
    opts = opts || {};
    return new Promise(resolve => {
        const overlay = document.getElementById("prompt-overlay");
        const titleEl = document.getElementById("prompt-title");
        const input = document.getElementById("prompt-input");
        const okBtn = document.getElementById("prompt-ok");
        const cancelBtn = document.getElementById("prompt-cancel");
        titleEl.textContent = title || "输入";
        input.value = defaultValue || "";
        input.placeholder = opts.placeholder || "";
        okBtn.textContent = opts.okText || "确定";
        cancelBtn.textContent = opts.cancelText || "取消";
        function cleanup(result) {
            overlay.classList.remove("active");
            okBtn.removeEventListener("click", onOk);
            cancelBtn.removeEventListener("click", onCancel);
            overlay.removeEventListener("click", onBackdrop);
            input.removeEventListener("keydown", onKey);
            resolve(result);
        }
        function onOk() { cleanup(input.value); }
        function onCancel() { cleanup(null); }
        function onBackdrop(e) { if (e.target === overlay) cleanup(null); }
        function onKey(e) {
            if (e.key === "Escape") { e.preventDefault(); cleanup(null); }
            else if (e.key === "Enter") { e.preventDefault(); cleanup(input.value); }
        }
        okBtn.addEventListener("click", onOk);
        cancelBtn.addEventListener("click", onCancel);
        overlay.addEventListener("click", onBackdrop);
        input.addEventListener("keydown", onKey);
        overlay.classList.add("active");
        setTimeout(() => { input.focus(); input.select(); }, 30);
    });
}

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

function showCompressNotice(thresholdKb) {
    if (chatArea.lastElementChild && chatArea.lastElementChild.classList.contains("compress-notice")) return;
    const notice = document.createElement("div");
    notice.className = "compress-notice";
    const kb = thresholdKb ? ("（已超过 " + thresholdKb + "K）") : "";
    notice.textContent = "历史对话已超出上限" + kb + "，较早内容已自动压缩为「前情提要」保留。为获得更好效果，建议新建对话继续。";
    chatArea.appendChild(notice);
    if (shouldAutoScroll()) chatArea.scrollTop = chatArea.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

const COPY_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
const CHECK_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><polyline points="20 6 9 17 4 12"></polyline></svg>';
const REGEN_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>';
const DOWNLOAD_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>';

async function copyToClipboard(text) {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (e) {}
    try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return ok;
    } catch (e) {
        return false;
    }
}

function flashCopyButton(btn) {
    const original = btn.innerHTML;
    btn.classList.add("copied");
    btn.innerHTML = CHECK_ICON_SVG + (btn.dataset.label ? '<span>已复制</span>' : '');
    setTimeout(() => {
        btn.classList.remove("copied");
        btn.innerHTML = original;
    }, 1500);
}

const CODE_EXT_MAP = {
    javascript: "js", typescript: "ts", python: "py", bash: "sh", shell: "sh",
    json: "json", html: "html", xml: "xml", css: "css", java: "java",
    cpp: "cpp", c: "c", csharp: "cs", go: "go", rust: "rs", ruby: "rb",
    php: "php", sql: "sql", yaml: "yml", markdown: "md", plaintext: "txt"
};

function detectCodeLang(codeEl) {
    if (!codeEl) return "";
    const cls = codeEl.className || "";
    const m = cls.match(/language-([\w-]+)/);
    if (m) return m[1].toLowerCase();
    return "";
}

function enhanceCodeBlocks(bubble) {
    const pres = bubble.querySelectorAll("pre");
    pres.forEach(pre => {
        if (pre.classList.contains("code-block-wrap")) return;
        pre.classList.add("code-block-wrap");
        const codeEl = pre.querySelector("code");

        // 语法高亮
        let lang = detectCodeLang(codeEl);
        if (codeEl && window.hljs) {
            try {
                if (lang && hljs.getLanguage(lang)) {
                    const res = hljs.highlight(codeEl.textContent, { language: lang });
                    codeEl.innerHTML = res.value;
                    codeEl.classList.add("hljs");
                } else {
                    const res = hljs.highlightAuto(codeEl.textContent);
                    codeEl.innerHTML = res.value;
                    codeEl.classList.add("hljs");
                    if (!lang && res.language) lang = res.language;
                }
            } catch (err) { /* 高亮失败则保持原样 */ }
        }

        // 顶部栏
        const header = document.createElement("div");
        header.className = "code-header";
        const langLabel = document.createElement("span");
        langLabel.className = "code-lang";
        langLabel.textContent = lang || "code";
        const tools = document.createElement("div");
        tools.className = "code-tools";

        const copyBtn = document.createElement("button");
        copyBtn.className = "code-copy-btn";
        copyBtn.type = "button";
        copyBtn.title = "复制代码";
        copyBtn.innerHTML = COPY_ICON_SVG + '<span class="code-btn-text">复制</span>';
        copyBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const ce = pre.querySelector("code");
            const codeText = ce ? ce.innerText : pre.innerText;
            const ok = await copyToClipboard(codeText);
            if (ok) {
                copyBtn.classList.add("copied");
                copyBtn.innerHTML = CHECK_ICON_SVG + '<span class="code-btn-text">已复制</span>';
                setTimeout(() => {
                    copyBtn.classList.remove("copied");
                    copyBtn.innerHTML = COPY_ICON_SVG + '<span class="code-btn-text">复制</span>';
                }, 1500);
            } else {
                showToast("复制失败", "error");
            }
        });

        const dlBtn = document.createElement("button");
        dlBtn.className = "code-download-btn";
        dlBtn.type = "button";
        dlBtn.title = "下载代码";
        dlBtn.innerHTML = DOWNLOAD_ICON_SVG + '<span class="code-btn-text">下载</span>';
        dlBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const ce = pre.querySelector("code");
            const codeText = ce ? ce.innerText : pre.innerText;
            const ext = CODE_EXT_MAP[lang] || "txt";
            const blob = new Blob([codeText], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "code-" + Date.now() + "." + ext;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });

        tools.appendChild(copyBtn);
        tools.appendChild(dlBtn);
        header.appendChild(langLabel);
        header.appendChild(tools);
        pre.insertBefore(header, pre.firstChild);
    });
}

function formatMsgTime(tsSec) {
    if (!tsSec) return "";
    const d = new Date(tsSec * 1000);
    if (isNaN(d.getTime())) return "";
    const p = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) +
        " " + p(d.getHours()) + ":" + p(d.getMinutes());
}

function attachAiActions(msgDiv, rawText, opts) {
    if (!msgDiv) return;
    opts = opts || {};
    const bubble = msgDiv.querySelector(".bubble");
    if (bubble) {
        enhanceCodeBlocks(bubble);
        renderMathInElement_safe(bubble);
    }

    if (typeof opts.ts !== "undefined" && opts.ts) {
        msgDiv.dataset.ts = opts.ts;
    }

    let actions = msgDiv.querySelector(".msg-actions");
    if (actions) actions.remove();
    actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.className = "msg-action-btn";
    copyBtn.type = "button";
    copyBtn.title = "复制全文";
    copyBtn.innerHTML = COPY_ICON_SVG;
    copyBtn.addEventListener("click", async () => {
        const text = msgDiv.dataset.rawText || (bubble ? bubble.innerText : "");
        const ok = await copyToClipboard(text);
        if (ok) flashCopyButton(copyBtn);
        else showToast("复制失败", "error");
    });
    actions.appendChild(copyBtn);

    if (opts.allowRegen) {
        const regenBtn = document.createElement("button");
        regenBtn.className = "msg-action-btn";
        regenBtn.type = "button";
        regenBtn.title = "重新生成";
        regenBtn.innerHTML = REGEN_ICON_SVG;
        regenBtn.addEventListener("click", () => regenerateLastMessage());
        actions.appendChild(regenBtn);
    }

    if (typeof rawText === "string") {
        msgDiv.dataset.rawText = rawText;
    }

    const tsVal = msgDiv.dataset.ts ? parseInt(msgDiv.dataset.ts, 10) : 0;
    const tsText = formatMsgTime(tsVal);
    if (tsText) {
        const tsEl = document.createElement("span");
        tsEl.className = "msg-time";
        tsEl.textContent = tsText;
        actions.appendChild(tsEl);
    }

    msgDiv.appendChild(actions);
}

async function regenerateLastMessage() {
    if (isGenerating || !currentConvId) return;
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
    if (convUserCount > 0) convUserCount--;
    const userText = data.user_message || "";
    const images = (data.images || []).map((url, i) => ({ name: "image_" + i, base64: url }));
    let plainText = userText;
    const savedPendingImages = pendingImages;
    pendingImages = images;
    await sendMessage(plainText || " ");
    pendingImages = savedPendingImages.length ? savedPendingImages : pendingImages;
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

// ==================== 侧边栏宽度拖拽 ====================
(function setupSidebarResizer() {
    const resizer = document.getElementById("sidebar-resizer");
    if (!resizer) return;
    const MIN_W = 180;
    const MAX_W = 480;

    const saved = parseInt(localStorage.getItem("sidebarWidth") || "", 10);
    if (!isNaN(saved) && saved >= MIN_W && saved <= MAX_W) {
        document.documentElement.style.setProperty("--sidebar-width", saved + "px");
    }

    let dragging = false;

    function onMove(e) {
        if (!dragging) return;
        const x = e.touches ? e.touches[0].clientX : e.clientX;
        let w = x;
        if (w < MIN_W) w = MIN_W;
        if (w > MAX_W) w = MAX_W;
        document.documentElement.style.setProperty("--sidebar-width", w + "px");
    }

    function onUp() {
        if (!dragging) return;
        dragging = false;
        document.body.classList.remove("resizing");
        resizer.classList.remove("dragging");
        const cur = getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width").trim();
        const px = parseInt(cur, 10);
        if (!isNaN(px)) localStorage.setItem("sidebarWidth", String(px));
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        window.removeEventListener("touchmove", onMove);
        window.removeEventListener("touchend", onUp);
    }

    function onDown(e) {
        if (sidebar.classList.contains("collapsed")) return;
        dragging = true;
        document.body.classList.add("resizing");
        resizer.classList.add("dragging");
        window.addEventListener("mousemove", onMove);
        window.addEventListener("mouseup", onUp);
        window.addEventListener("touchmove", onMove, { passive: false });
        window.addEventListener("touchend", onUp);
        e.preventDefault();
    }

    resizer.addEventListener("mousedown", onDown);
    resizer.addEventListener("touchstart", onDown, { passive: false });
    resizer.addEventListener("dblclick", function () {
        document.documentElement.style.setProperty("--sidebar-width", "260px");
        localStorage.setItem("sidebarWidth", "260");
    });
})();

// ==================== 数据管理：导入对话 + 单对话分享导出 ====================
function _slugifyFilename(name) {
    let s = (name || "对话").replace(/[\\/:*?"<>|\n\r\t]/g, "_").trim();
    if (!s) s = "对话";
    if (s.length > 60) s = s.slice(0, 60);
    return s;
}

async function shareConversation(c) {
    if (!c || !c.id) return;
    let payloadText;
    try {
        const resp = await fetch("/api/conversations/export?id=" + encodeURIComponent(c.id));
        if (!resp.ok) {
            const d = await resp.json().catch(() => ({}));
            showToast(d.error || "导出失败", "error");
            return;
        }
        payloadText = await resp.text();
    } catch (e) {
        showToast("导出失败", "error");
        return;
    }
    const defaultName = _slugifyFilename(c.title) + ".json";

    // 优先用 showSaveFilePicker（Chrome/Edge）：弹系统目录窗口，可选任意位置+文件名
    if (window.showSaveFilePicker) {
        try {
            const handle = await window.showSaveFilePicker({
                suggestedName: defaultName,
                types: [{ description: "JSON 文件", accept: { "application/json": [".json"] } }]
            });
            const writable = await handle.createWritable();
            await writable.write(payloadText);
            await writable.close();
            showToast("已保存：" + (handle.name || defaultName), "success");
            return;
        } catch (e) {
            if (e && e.name === "AbortError") return; // 用户取消，不提示
            // 其它异常则退回普通下载
        }
    }

    // 兜底：浏览器默认下载（Firefox/Safari）
    const blob = new Blob([payloadText], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = defaultName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("已导出到下载目录", "success");
}

(function setupDataManage() {
    const btnImport = document.getElementById("btn-import-convs");
    const fileInput = document.getElementById("import-file-input");
    if (!btnImport || !fileInput) return;

    btnImport.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
        const file = fileInput.files && fileInput.files[0];
        fileInput.value = "";
        if (!file) return;
        let parsed;
        try {
            const text = await file.text();
            parsed = JSON.parse(text);
        } catch (e) {
            showToast("文件不是有效的 JSON", "error");
            return;
        }
        const ok = await confirmDialog(
            "将把文件中的对话导入到当前列表（合并方式，不会覆盖已有对话）。继续？",
            { title: "导入对话", okText: "导入", icon: "\uD83D\uDCE5" }
        );
        if (!ok) return;
        const body = (parsed && Array.isArray(parsed.conversations))
            ? { conversations: parsed.conversations, mode: "merge" }
            : (Array.isArray(parsed) ? { conversations: parsed, mode: "merge" } : null);
        if (!body) {
            showToast("文件格式不正确，找不到对话数据", "error");
            return;
        }
        try {
            const resp = await fetch("/api/conversations/import", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });
            const data = await resp.json();
            if (resp.ok) {
                showToast("已导入 " + data.imported + " 个对话" + (data.skipped ? "，跳过 " + data.skipped + " 个" : ""), "success");
                await loadConversations();
            } else {
                showToast(data.error || "导入失败", "error");
            }
        } catch (e) {
            showToast("导入失败", "error");
        }
    });
})();


// ==================== 对话内字符查找 ====================
(function setupChatSearch() {
    const supported = (typeof CSS !== "undefined" && CSS.highlights);
    const wrap = document.getElementById("header-search");
    const btnToggle = document.getElementById("btn-toggle-search");
    const input = document.getElementById("search-input");
    const countEl = document.getElementById("search-count");
    const btnPrev = document.getElementById("search-prev");
    const btnNext = document.getElementById("search-next");
    const btnClose = document.getElementById("search-close");
    if (!wrap || !btnToggle || !input) return;

    let matches = [];
    let current = -1;

    function clearHighlights() {
        if (supported) {
            CSS.highlights.delete("chat-search");
            CSS.highlights.delete("chat-search-current");
        }
        matches = [];
        current = -1;
        updateCount();
    }

    function updateCount() {
        countEl.textContent = matches.length ? (current + 1) + "/" + matches.length : "0/0";
    }

    function collectTextNodes(root) {
        const nodes = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
                const p = node.parentElement;
                if (p && p.closest(".katex, script, style")) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            }
        });
        let n;
        while ((n = walker.nextNode())) nodes.push(n);
        return nodes;
    }

    function doSearch() {
        if (!supported) return;
        const kw = input.value;
        CSS.highlights.delete("chat-search");
        CSS.highlights.delete("chat-search-current");
        matches = [];
        current = -1;
        if (!kw) { updateCount(); return; }
        const needle = kw.toLowerCase();
        const nodes = collectTextNodes(chatArea);
        nodes.forEach(node => {
            const text = node.nodeValue.toLowerCase();
            let idx = text.indexOf(needle);
            while (idx !== -1) {
                const range = new Range();
                range.setStart(node, idx);
                range.setEnd(node, idx + needle.length);
                matches.push(range);
                idx = text.indexOf(needle, idx + needle.length);
            }
        });
        if (matches.length) {
            CSS.highlights.set("chat-search", new Highlight(...matches));
            current = 0;
            focusCurrent();
        }
        updateCount();
    }

    function focusCurrent() {
        if (!supported || current < 0 || current >= matches.length) return;
        const range = matches[current];
        CSS.highlights.delete("chat-search-current");
        CSS.highlights.set("chat-search-current", new Highlight(range));
        const el = range.startContainer.parentElement;
        if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth", block: "center" });
        updateCount();
    }

    function go(delta) {
        if (!matches.length) return;
        current = (current + delta + matches.length) % matches.length;
        focusCurrent();
    }

    function openSearch() {
        wrap.classList.add("open");
        input.focus();
        input.select();
        if (input.value) doSearch();
    }

    function closeSearch() {
        wrap.classList.remove("open");
        clearHighlights();
        input.value = "";
    }

    window.clearChatSearch = function () {
        if (wrap.classList.contains("open")) doSearch();
        else clearHighlights();
    };

    btnToggle.addEventListener("click", () => {
        if (wrap.classList.contains("open")) closeSearch();
        else openSearch();
    });
    btnClose.addEventListener("click", closeSearch);
    btnPrev.addEventListener("click", () => go(-1));
    btnNext.addEventListener("click", () => go(1));

    let debounce = null;
    input.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(doSearch, 150);
    });
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); go(e.shiftKey ? -1 : 1); }
        else if (e.key === "Escape") { e.preventDefault(); closeSearch(); }
    });

    if (!supported) {
        btnToggle.style.display = "none";
    }
})();
