const chatArea = document.getElementById("chat-area");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
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

const setProvider = document.getElementById("set-provider");
const setBaseUrl = document.getElementById("set-base-url");
const setModel = document.getElementById("set-model");
const setModelCustom = document.getElementById("set-model-custom");
const setApiKey = document.getElementById("set-api-key");
const setKeyFile = document.getElementById("set-key-file");
const keyStatus = document.getElementById("key-status");
const setMaxRounds = document.getElementById("set-max-rounds");
const quickModel = document.getElementById("quick-model");

const btnManageModels = document.getElementById("btn-manage-models");
const modelManageOverlay = document.getElementById("model-manage-overlay");
const btnCloseManage = document.getElementById("btn-close-manage");
const customModelListEl = document.getElementById("custom-model-list");
const addProvider = document.getElementById("add-provider");
const addModel = document.getElementById("add-model");
const addModelCustom = document.getElementById("add-model-custom");
const btnAddModel = document.getElementById("btn-add-model");

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

let isGenerating = false;
let currentConvId = null;
let welcomeHTML = welcome ? welcome.outerHTML : "";
let providers = {};
let currentAgentId = null;
let editingAgentId = null;
let agentAvatarUrl = "";
let cachedAgents = [];

const DEFAULT_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const SMALL_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const DROPDOWN_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CARD_AVATAR_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
const CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>';

btnToggleSidebar.addEventListener("click", () => sidebar.classList.toggle("collapsed"));
btnNewChat.addEventListener("click", createNewConversation);
btnSend.addEventListener("click", sendMessage);
btnClear.addEventListener("click", clearCurrentConversation);
userInput.addEventListener("input", autoResize);
userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

btnSettings.addEventListener("click", openSettings);
btnCloseSettings.addEventListener("click", closeSettings);
settingsOverlay.addEventListener("click", e => { if (e.target === settingsOverlay) closeSettings(); });
btnSaveSettings.addEventListener("click", saveSettings);
setProvider.addEventListener("change", onProviderChange);
setModel.addEventListener("change", () => {
    if (setModel.value === "__custom__") { setModelCustom.style.display = "block"; setModelCustom.focus(); }
    else { setModelCustom.style.display = "none"; }
});

quickModel.addEventListener("change", onQuickModelChange);
btnManageModels.addEventListener("click", openManageModels);
btnCloseManage.addEventListener("click", closeManageModels);
modelManageOverlay.addEventListener("click", e => { if (e.target === modelManageOverlay) closeManageModels(); });
addProvider.addEventListener("change", onAddProviderChange);
addModel.addEventListener("change", () => {
    if (addModel.value === "__custom__") { addModelCustom.style.display = "block"; addModelCustom.focus(); }
    else { addModelCustom.style.display = "none"; }
});
btnAddModel.addEventListener("click", addCustomModel);

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
        card.innerHTML = avatarHTML +
            '<div class="agent-card-name">' + escapeHtml(a.name) + '</div>' +
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

    const payload = {
        name: name,
        avatar: agentAvatarUrl,
        system_prompt: agentPrompt.value,
        provider: agentProvider.value,
        model: agentModel.value,
        base_url: ""
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
    const seen = new Set();

    const activeOpt = document.createElement("option");
    activeOpt.value = activeKey;
    activeOpt.textContent = active.model || "未配置";
    activeOpt.selected = true;
    quickModel.appendChild(activeOpt);
    seen.add(activeKey);

    customModels.forEach(m => {
        const key = m.provider + "|" + m.model;
        if (seen.has(key)) return;
        seen.add(key);
        const opt = document.createElement("option");
        opt.value = key;
        opt.dataset.baseUrl = m.base_url || "";
        opt.textContent = m.name || m.model;
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
    onAddProviderChange();
    await renderCustomModelList();
    modelManageOverlay.classList.add("active");
}

function closeManageModels() { modelManageOverlay.classList.remove("active"); }

function onAddProviderChange() {
    const key = addProvider.value;
    const p = providers[key];
    if (!p) return;
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
        customModelListEl.innerHTML = '<div class="empty-hint">还没有添加模型，使用下方选择器添加</div>';
        return;
    }
    customModels.forEach(m => {
        const isActive = m.provider === active.provider && m.model === active.model;
        const item = document.createElement("div");
        item.className = "custom-model-item" + (isActive ? " is-active" : "");
        item.innerHTML =
            '<span class="model-name">' + escapeHtml(m.model) + '</span>' +
            '<span class="model-provider">' + escapeHtml(m.name || m.provider) + '</span>' +
            '<button class="btn-remove-model" title="移除">✕</button>';
        item.querySelector(".btn-remove-model").addEventListener("click", async () => {
            await fetch("/api/custom-models", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ provider: m.provider, model: m.model })
            });
            await renderCustomModelList();
            await buildQuickModelList();
        });
        customModelListEl.appendChild(item);
    });
}

async function addCustomModel() {
    const provider = addProvider.value;
    const model = addModel.value === "__custom__" ? addModelCustom.value.trim() : addModel.value;
    if (!model) { showToast("请选择或输入模型名称", "error"); return; }
    const p = providers[provider];
    const base_url = p ? p.base_url : "";
    const name = (p ? p.name : provider) + " / " + model;
    try {
        const resp = await fetch("/api/custom-models", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider, model, base_url, name })
        });
        if (resp.ok) {
            showToast("已添加 " + model, "success");
            await renderCustomModelList();
            await buildQuickModelList();
        } else {
            const err = await resp.json();
            showToast(err.error || "添加失败", "error");
        }
    } catch (err) {
        showToast("添加失败", "error");
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
    if (isGenerating) return;
    currentConvId = cid;
    document.querySelectorAll(".conv-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === cid);
    });
    const resp = await fetch("/api/conversations/" + cid + "/messages");
    const msgs = await resp.json();
    chatArea.innerHTML = "";
    if (msgs.length === 0) { showWelcome(); }
    else { msgs.forEach(m => addMessage(m.role === "user" ? "user" : "ai", m.content)); }

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
    if (!currentConvId || isGenerating) return;
    await fetch("/api/conversations/" + currentConvId + "/clear", { method: "POST" });
    chatArea.innerHTML = "";
    showWelcome();
}

function showWelcome() { chatArea.innerHTML = welcomeHTML; }
function hideWelcome() { const w = chatArea.querySelector(".welcome"); if (w) w.remove(); }

// ==================== 消息渲染与发送 ====================
function addMessage(role, content) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "message " + role;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "U" : "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = content;
    div.appendChild(avatar);
    div.appendChild(bubble);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return bubble;
}

function addAiBubble() {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "message ai";
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const cursor = document.createElement("span");
    cursor.className = "typing-cursor";
    bubble.appendChild(cursor);
    div.appendChild(avatar);
    div.appendChild(bubble);
    chatArea.appendChild(div);
    chatArea.scrollTop = chatArea.scrollHeight;
    return { bubble, cursor };
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text || isGenerating) return;

    if (!currentConvId) {
        await createNewConversation();
    }

    isGenerating = true;
    btnSend.disabled = true;
    userInput.value = "";
    autoResize();

    addMessage("user", text);
    const { bubble, cursor } = addAiBubble();
    let fullText = "";

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ conversation_id: currentConvId, message: text })
        });

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
                        break;
                    }
                } catch {
                    fullText += data;
                    if (cursor.parentNode) cursor.remove();
                    bubble.textContent = fullText;
                    bubble.appendChild(cursor);
                    chatArea.scrollTop = chatArea.scrollHeight;
                }
            }
        }
    } catch (err) {
        if (cursor.parentNode) cursor.remove();
        bubble.textContent = "";
        const errDiv = document.createElement("div");
        errDiv.className = "error-msg";
        errDiv.textContent = "网络错误: " + err.message;
        bubble.appendChild(errDiv);
    }

    if (cursor.parentNode) cursor.remove();
    isGenerating = false;
    btnSend.disabled = false;
    userInput.focus();
    await loadConversations();
}

// ==================== 设置面板 ====================
async function openSettings() {
    if (Object.keys(providers).length === 0) await loadProviders();
    setProvider.innerHTML = "";
    for (const [key, val] of Object.entries(providers)) {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.name;
        setProvider.appendChild(opt);
    }
    const resp = await fetch("/api/settings");
    const cfg = resp.ok ? await resp.json() : {};
    setProvider.value = cfg.provider || "deepseek";
    onProviderChange();
    setBaseUrl.value = cfg.base_url || "";
    setMaxRounds.value = cfg.max_history_rounds || 50;
    setApiKey.value = "";
    setKeyFile.value = cfg.key_file_path || "";
    if (cfg.model) {
        if (setModel.querySelector('option[value="' + cfg.model + '"]')) {
            setModel.value = cfg.model;
            setModelCustom.style.display = "none";
        } else {
            setModel.value = "__custom__";
            setModelCustom.value = cfg.model;
            setModelCustom.style.display = "block";
        }
    }
    keyStatus.textContent = cfg.has_api_key ? "✓ 已配置 API Key" : "✗ 未配置 API Key";
    keyStatus.className = "key-status " + (cfg.has_api_key ? "ok" : "no");
    settingsOverlay.classList.add("active");
}

function closeSettings() { settingsOverlay.classList.remove("active"); }

function onProviderChange() {
    const key = setProvider.value;
    const p = providers[key];
    if (!p) return;
    if (p.base_url) setBaseUrl.value = p.base_url;
    setModel.innerHTML = "";
    if (p.models && p.models.length > 0) {
        p.models.forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            setModel.appendChild(opt);
        });
    }
    const customOpt = document.createElement("option");
    customOpt.value = "__custom__";
    customOpt.textContent = "-- 自定义模型名 --";
    setModel.appendChild(customOpt);
    setModelCustom.style.display = "none";
    setModelCustom.value = "";
}

async function saveSettings() {
    const payload = {
        provider: setProvider.value,
        base_url: setBaseUrl.value.trim(),
        model: setModel.value === "__custom__" ? setModelCustom.value.trim() : setModel.value,
        max_history_rounds: parseInt(setMaxRounds.value) || 50
    };
    const apiKeyVal = setApiKey.value.trim();
    const keyFileVal = setKeyFile.value.trim();
    if (apiKeyVal) payload.api_key = apiKeyVal;
    if (keyFileVal) payload.key_file_path = keyFileVal;
    if (!payload.base_url) { showToast("请填写 API 地址", "error"); return; }
    if (!payload.model) { showToast("请选择或输入模型名称", "error"); return; }
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
            await buildQuickModelList();
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
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 2500);
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 初始化 ====================
loadConversations();
buildQuickModelList();
loadAgentBar();
