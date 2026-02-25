const API_BASE = 'http://localhost:8000/api';

let tasks = [];
let selectedTasks = new Set();
let pendingFiles = [];
let currentTheme = localStorage.getItem('theme') || 'light';
let pollInterval = null;

const elements = {
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    tasksList: document.getElementById('tasksList'),
    emptyState: document.getElementById('emptyState'),
    selectAll: document.getElementById('selectAll'),
    batchDownloadBtn: document.getElementById('batchDownloadBtn'),
    batchDeleteBtn: document.getElementById('batchDeleteBtn'),
    themeToggle: document.getElementById('themeToggle'),
    themeIcon: document.getElementById('themeIcon'),
    settingsBtn: document.getElementById('settingsBtn'),
    taskOptionsModal: document.getElementById('taskOptionsModal'),
    closeOptionsModal: document.getElementById('closeOptionsModal'),
    modalTitle: document.getElementById('modalTitle'),
    fileList: document.getElementById('fileList'),
    generateOutline: document.getElementById('generateOutline'),
    outlineOptions: document.getElementById('outlineOptions'),
    outlineModeRadios: document.querySelectorAll('input[name="outlineMode"]'),
    tocOptions: document.getElementById('tocOptions'),
    manualTocPages: document.getElementById('manualTocPages'),
    pageRangeInputs: document.getElementById('pageRangeInputs'),
    tocPageStart: document.getElementById('tocPageStart'),
    tocPageEnd: document.getElementById('tocPageEnd'),
    pageOffset: document.getElementById('pageOffset'),
    embedOutline: document.getElementById('embedOutline'),
    cancelOptions: document.getElementById('cancelOptions'),
    confirmOptions: document.getElementById('confirmOptions'),
    settingsModal: document.getElementById('settingsModal'),
    closeSettingsModal: document.getElementById('closeSettingsModal'),
    apiKey: document.getElementById('apiKey'),
    baseUrl: document.getElementById('baseUrl'),
    model: document.getElementById('model'),
    testConnection: document.getElementById('testConnection'),
    saveSettings: document.getElementById('saveSettings'),
    connectionStatus: document.getElementById('connectionStatus'),
    uploadStorage: document.getElementById('uploadStorage'),
    outputStorage: document.getElementById('outputStorage'),
    totalStorage: document.getElementById('totalStorage'),
    cleanupOld: document.getElementById('cleanupOld'),
    cleanupAll: document.getElementById('cleanupAll'),
    snackbar: document.getElementById('snackbar')
};

function init() {
    applyTheme(currentTheme);
    setupEventListeners();
    loadTasks();
    loadLLMConfig();
    startPolling();
}

function setupEventListeners() {
    elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', handleFileSelect);
    
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('dragleave', handleDragLeave);
    elements.uploadArea.addEventListener('drop', handleDrop);
    
    elements.themeToggle.addEventListener('click', toggleTheme);
    elements.settingsBtn.addEventListener('click', openSettingsModal);
    
    elements.selectAll.addEventListener('change', handleSelectAll);
    elements.batchDownloadBtn.addEventListener('click', handleBatchDownload);
    elements.batchDeleteBtn.addEventListener('click', handleBatchDelete);
    
    elements.closeOptionsModal.addEventListener('click', closeOptionsModal);
    elements.cancelOptions.addEventListener('click', closeOptionsModal);
    elements.confirmOptions.addEventListener('click', confirmUpload);
    
    elements.generateOutline.addEventListener('change', toggleOutlineOptions);
    elements.outlineModeRadios.forEach(radio => {
        radio.addEventListener('change', handleOutlineModeChange);
    });
    elements.manualTocPages.addEventListener('change', togglePageRangeInputs);
    
    elements.closeSettingsModal.addEventListener('click', closeSettingsModal);
    elements.testConnection.addEventListener('click', handleTestConnection);
    elements.saveSettings.addEventListener('click', handleSaveSettings);
    elements.cleanupOld.addEventListener('click', handleCleanupOld);
    elements.cleanupAll.addEventListener('click', handleCleanupAll);
    
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            const modal = e.target.closest('.task-options-modal, .settings-modal');
            if (modal) modal.classList.add('hidden');
        });
    });
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    elements.themeIcon.textContent = theme === 'dark' ? 'light_mode' : 'dark_mode';
    localStorage.setItem('theme', theme);
    currentTheme = theme;
}

function toggleTheme() {
    applyTheme(currentTheme === 'light' ? 'dark' : 'light');
}

function handleDragOver(e) {
    e.preventDefault();
    elements.uploadArea.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('dragover');
}

function isPdfFile(file) {
    const validTypes = ['application/pdf', 'application/x-pdf'];
    const hasPdfExtension = file.name.toLowerCase().endsWith('.pdf');
    return validTypes.includes(file.type) || hasPdfExtension;
}

function handleDrop(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('dragover');
    
    const files = Array.from(e.dataTransfer.files).filter(isPdfFile);
    
    if (files.length === 0) {
        showSnackbar('请选择 PDF 文件');
        return;
    }
    
    pendingFiles = files;
    openOptionsModal();
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    
    console.log('Selected files count:', files.length);
    console.log('Files:', files.map(f => f.name));
    
    if (files.length === 0) return;
    
    const invalidFiles = files.filter(file => !isPdfFile(file));
    if (invalidFiles.length > 0) {
        showSnackbar('只支持 PDF 文件');
        return;
    }
    
    pendingFiles = files;
    openOptionsModal();
    e.target.value = '';
}

function openOptionsModal() {
    resetOptionsForm();
    console.log('Opening modal with', pendingFiles.length, 'files');
    
    if (pendingFiles.length === 1) {
        elements.modalTitle.textContent = `任务选项`;
    } else {
        elements.modalTitle.textContent = `批量上传 - ${pendingFiles.length} 个文件`;
    }
    
    const fileListHtml = pendingFiles.map((file, index) => 
        `<div class="file-list-item">${index + 1}. ${escapeHtml(file.name)}</div>`
    ).join('');
    elements.fileList.innerHTML = fileListHtml;
    
    elements.taskOptionsModal.classList.remove('hidden');
}

function closeOptionsModal() {
    elements.taskOptionsModal.classList.add('hidden');
    pendingFiles = [];
}

function resetOptionsForm() {
    elements.generateOutline.checked = false;
    elements.outlineOptions.style.display = 'none';
    document.querySelector('input[name="outlineMode"][value="auto"]').checked = true;
    elements.tocOptions.style.display = 'none';
    elements.manualTocPages.checked = false;
    elements.pageRangeInputs.style.display = 'none';
    elements.tocPageStart.value = 1;
    elements.tocPageEnd.value = 1;
    elements.pageOffset.value = 0;
    elements.embedOutline.checked = false;
    elements.embedOutline.disabled = true;
}

function toggleOutlineOptions() {
    const isChecked = elements.generateOutline.checked;
    elements.outlineOptions.style.display = isChecked ? 'block' : 'none';
    elements.embedOutline.disabled = !isChecked;
    if (isChecked) {
        elements.embedOutline.checked = true;
    } else {
        elements.embedOutline.checked = false;
    }
    handleOutlineModeChange();
}

function handleOutlineModeChange() {
    const selectedMode = document.querySelector('input[name="outlineMode"]:checked').value;
    elements.tocOptions.style.display = selectedMode === 'toc_page' ? 'block' : 'none';
}

function togglePageRangeInputs() {
    elements.pageRangeInputs.style.display = elements.manualTocPages.checked ? 'block' : 'none';
}

async function confirmUpload() {
    if (pendingFiles.length === 0) {
        showSnackbar('没有选择文件');
        return;
    }
    
    const filesToUpload = [...pendingFiles];
    const options = getTaskOptions();
    
    console.log('Uploading', filesToUpload.length, 'files');
    
    elements.taskOptionsModal.classList.add('hidden');
    pendingFiles = [];
    
    for (const file of filesToUpload) {
        console.log('Uploading:', file.name);
        await uploadFile(file, options);
    }
    
    console.log('All uploads completed');
}

function getTaskOptions() {
    return {
        generate_outline: elements.generateOutline.checked,
        outline_mode: document.querySelector('input[name="outlineMode"]:checked').value,
        toc_page_start: elements.manualTocPages.checked ? parseInt(elements.tocPageStart.value) : null,
        toc_page_end: elements.manualTocPages.checked ? parseInt(elements.tocPageEnd.value) : null,
        page_offset: parseInt(elements.pageOffset.value),
        embed_outline: elements.embedOutline.checked
    };
}

async function uploadFile(file, options) {
    const formData = new FormData();
    formData.append('file', file);
    
    const params = new URLSearchParams({
        generate_outline: options.generate_outline,
        outline_mode: options.outline_mode,
        page_offset: options.page_offset,
        embed_outline: options.embed_outline
    });
    
    if (options.toc_page_start) params.append('toc_page_start', options.toc_page_start);
    if (options.toc_page_end) params.append('toc_page_end', options.toc_page_end);
    
    try {
        showSnackbar(`正在上传 "${file.name}"...`);
        
        const response = await fetch(`${API_BASE}/upload?${params}`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '上传失败');
        }
        
        const task = await response.json();
        showSnackbar(`文件 "${file.name}" 上传成功`);
        await loadTasks();
    } catch (error) {
        showSnackbar(`上传失败: ${error.message}`);
    }
}

async function loadTasks() {
    try {
        const response = await fetch(`${API_BASE}/tasks`);
        tasks = await response.json();
        renderTasks();
    } catch (error) {
        console.error('加载任务失败:', error);
    }
}

function renderTasks() {
    if (tasks.length === 0) {
        elements.emptyState.classList.remove('hidden');
        elements.tasksList.innerHTML = '';
        elements.tasksList.appendChild(elements.emptyState);
        return;
    }
    
    elements.emptyState.classList.add('hidden');
    
    const tasksHTML = tasks.map(task => createTaskCard(task)).join('');
    elements.tasksList.innerHTML = tasksHTML;
    
    tasks.forEach(task => {
        const checkbox = document.getElementById(`task-${task.id}`);
        if (checkbox) {
            checkbox.addEventListener('change', () => handleTaskSelect(task.id));
        }
        
        const downloadBtn = document.getElementById(`download-${task.id}`);
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => downloadTask(task.id));
        }
        
        const downloadTextBtn = document.getElementById(`download-text-${task.id}`);
        if (downloadTextBtn) {
            downloadTextBtn.addEventListener('click', () => downloadText(task.id));
        }
        
        const deleteBtn = document.getElementById(`delete-${task.id}`);
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => deleteTask(task.id));
        }
    });
    
    updateBatchActions();
}

function createTaskCard(task) {
    const statusInfo = getStatusInfo(task.status);
    const isSelected = selectedTasks.has(task.id);
    const canDownload = task.status === 'completed';
    const progress = task.progress?.progress || 0;
    
    return `
        <div class="task-card" data-task-id="${task.id}">
            <div class="task-header">
                <div class="task-info">
                    <div class="task-checkbox">
                        <input type="checkbox" id="task-${task.id}" ${isSelected ? 'checked' : ''}>
                    </div>
                    <div class="task-details">
                        <div class="task-filename">${escapeHtml(task.original_filename)}</div>
                        <div class="task-status">
                            <span class="status-badge ${task.status}">
                                <span class="material-icons-round ${statusInfo.spinning ? 'loading-spinner' : ''}">${statusInfo.icon}</span>
                                ${statusInfo.text}
                            </span>
                            ${task.queue_position ? `<span style="margin-left: 8px;">队列位置: ${task.queue_position}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="task-actions">
                    ${canDownload ? `
                        <button class="text-button" id="download-${task.id}" title="下载 PDF">
                            <span class="material-icons-round">picture_as_pdf</span>
                            PDF
                        </button>
                        <button class="text-button" id="download-text-${task.id}" title="下载文本">
                            <span class="material-icons-round">description</span>
                            文本
                        </button>
                    ` : ''}
                    <button class="text-button danger" id="delete-${task.id}">
                        <span class="material-icons-round">delete</span>
                        删除
                    </button>
                </div>
            </div>
            ${task.status !== 'completed' && task.status !== 'failed' ? `
                <div class="task-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                    <div class="progress-message">${task.progress?.message || ''}</div>
                </div>
            ` : ''}
            ${task.error ? `<div class="progress-message" style="color: var(--md-sys-color-error); margin-top: 8px;">错误: ${escapeHtml(task.error)}</div>` : ''}
        </div>
    `;
}

function getStatusInfo(status) {
    const statusMap = {
        pending: { icon: 'schedule', text: '等待中', spinning: false },
        uploading: { icon: 'cloud_upload', text: '上传中', spinning: true },
        queued: { icon: 'schedule', text: '排队中', spinning: false },
        processing: { icon: 'hourglass_empty', text: '处理中', spinning: true },
        ocr_processing: { icon: 'document_scanner', text: 'OCR 处理中', spinning: true },
        outline_generating: { icon: 'auto_awesome', text: '生成大纲中', spinning: true },
        completed: { icon: 'check_circle', text: '已完成', spinning: false },
        failed: { icon: 'error', text: '失败', spinning: false }
    };
    return statusMap[status] || { icon: 'help', text: status, spinning: false };
}

function handleTaskSelect(taskId) {
    if (selectedTasks.has(taskId)) {
        selectedTasks.delete(taskId);
    } else {
        selectedTasks.add(taskId);
    }
    updateBatchActions();
}

function handleSelectAll() {
    if (elements.selectAll.checked) {
        tasks.forEach(task => selectedTasks.add(task.id));
    } else {
        selectedTasks.clear();
    }
    renderTasks();
}

function updateBatchActions() {
    const completedTasks = tasks.filter(t => t.status === 'completed' && selectedTasks.has(t.id));
    elements.batchDownloadBtn.disabled = completedTasks.length === 0;
    elements.batchDeleteBtn.disabled = selectedTasks.size === 0;
    elements.selectAll.checked = tasks.length > 0 && selectedTasks.size === tasks.length;
}

async function downloadTask(taskId) {
    window.location.href = `${API_BASE}/download/${taskId}`;
}

async function downloadText(taskId) {
    window.location.href = `${API_BASE}/download/text/${taskId}`;
}

async function handleBatchDownload() {
    const taskIds = Array.from(selectedTasks).filter(id => {
        const task = tasks.find(t => t.id === id);
        return task && task.status === 'completed';
    });
    
    if (taskIds.length === 0) {
        showSnackbar('没有可下载的文件');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/download/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskIds)
        });
        
        if (!response.ok) throw new Error('下载失败');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'OCR_PDFs.zip';
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        showSnackbar(`批量下载失败: ${error.message}`);
    }
}

async function handleBatchDelete() {
    const taskIds = Array.from(selectedTasks);
    
    for (const taskId of taskIds) {
        await deleteTask(taskId, false);
    }
    
    selectedTasks.clear();
    await loadTasks();
}

async function deleteTask(taskId, reload = true) {
    try {
        const response = await fetch(`${API_BASE}/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('删除失败');
        
        selectedTasks.delete(taskId);
        
        if (reload) {
            await loadTasks();
        }
        
        showSnackbar('任务已删除');
    } catch (error) {
        showSnackbar(`删除失败: ${error.message}`);
    }
}

function openSettingsModal() {
    elements.settingsModal.classList.remove('hidden');
    elements.connectionStatus.innerHTML = '';
    elements.connectionStatus.className = 'connection-status';
    loadStorageInfo();
}

function closeSettingsModal() {
    elements.settingsModal.classList.add('hidden');
}

async function loadStorageInfo() {
    try {
        const response = await fetch(`${API_BASE}/storage`);
        const data = await response.json();
        
        elements.uploadStorage.textContent = `${data.upload_dir.size_mb} MB (${data.upload_dir.files} 个文件)`;
        elements.outputStorage.textContent = `${data.output_dir.size_mb} MB (${data.output_dir.files} 个文件)`;
        elements.totalStorage.textContent = `${data.total_size_mb} MB (${data.total_files} 个文件)`;
    } catch (error) {
        console.error('加载存储信息失败:', error);
    }
}

async function handleCleanupOld() {
    try {
        elements.cleanupOld.disabled = true;
        const response = await fetch(`${API_BASE}/cleanup`, { method: 'POST' });
        const data = await response.json();
        showSnackbar(data.message);
        await loadStorageInfo();
        await loadTasks();
    } catch (error) {
        showSnackbar(`清理失败: ${error.message}`);
    } finally {
        elements.cleanupOld.disabled = false;
    }
}

async function handleCleanupAll() {
    if (!confirm('确定要清理全部文件吗？这将删除所有上传和输出的文件。')) {
        return;
    }
    
    try {
        elements.cleanupAll.disabled = true;
        const response = await fetch(`${API_BASE}/cleanup/all`, { method: 'POST' });
        const data = await response.json();
        showSnackbar(data.message);
        await loadStorageInfo();
        await loadTasks();
    } catch (error) {
        showSnackbar(`清理失败: ${error.message}`);
    } finally {
        elements.cleanupAll.disabled = false;
    }
}

async function loadLLMConfig() {
    try {
        const response = await fetch(`${API_BASE}/llm/config`);
        const config = await response.json();
        
        elements.baseUrl.value = config.base_url || '';
        elements.model.value = config.model || '';
        elements.apiKey.value = '';
        elements.apiKey.placeholder = config.has_api_key ? '已配置 (输入以更新)' : '输入 API Key';
    } catch (error) {
        console.error('加载配置失败:', error);
    }
}

async function handleTestConnection() {
    const config = {
        api_key: elements.apiKey.value,
        base_url: elements.baseUrl.value,
        model: elements.model.value
    };
    
    if (!config.api_key) {
        showSnackbar('请输入 API Key');
        return;
    }
    
    elements.testConnection.disabled = true;
    elements.connectionStatus.innerHTML = '测试中...';
    elements.connectionStatus.className = 'connection-status';
    
    try {
        const response = await fetch(`${API_BASE}/llm/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        elements.connectionStatus.innerHTML = result.message;
        elements.connectionStatus.className = `connection-status ${result.success ? 'success' : 'error'}`;
    } catch (error) {
        elements.connectionStatus.innerHTML = `测试失败: ${error.message}`;
        elements.connectionStatus.className = 'connection-status error';
    } finally {
        elements.testConnection.disabled = false;
    }
}

async function handleSaveSettings() {
    const config = {
        api_key: elements.apiKey.value,
        base_url: elements.baseUrl.value,
        model: elements.model.value
    };
    
    try {
        const response = await fetch(`${API_BASE}/llm/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) throw new Error('保存失败');
        
        showSnackbar('设置已保存');
        closeSettingsModal();
        await loadLLMConfig();
    } catch (error) {
        showSnackbar(`保存失败: ${error.message}`);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    
    pollInterval = setInterval(async () => {
        const hasActiveTasks = tasks.some(t => 
            t.status !== 'completed' && t.status !== 'failed'
        );
        
        if (hasActiveTasks) {
            await loadTasks();
        }
    }, 2000);
}

function showSnackbar(message) {
    const snackbar = elements.snackbar;
    snackbar.querySelector('.snackbar-message').textContent = message;
    snackbar.classList.add('show');
    
    setTimeout(() => {
        snackbar.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', init);
