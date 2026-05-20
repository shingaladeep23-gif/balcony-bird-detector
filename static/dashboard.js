// ==========================================================================
// AeroSentinel Frontend Engine
// ==========================================================================

// Global State
let configState = {
    camera_url: "0",
    telegram_bot_token: "",
    telegram_chat_id: "",
    confidence_threshold: 0.5,
    cooldown_minutes: 5,
    consecutive_frames: 5,
    detection_zone: [],
    arduino_port: "",
    arduino_enabled: false
};

let drawnZonePoints = []; // Stores normalized {x, y} coordinate objects
let isDrawModeActive = false;
let canvasResizeObserver = null;

// DOM Elements
const elements = {
    cameraStatusText: document.getElementById("camera-status-text"),
    cameraDot: document.getElementById("camera-dot"),
    modelStatusText: document.getElementById("model-status-text"),
    modelDot: document.getElementById("model-dot"),
    
    // Video elements
    liveStreamFeed: document.getElementById("live-stream-feed"),
    videoWrapper: document.getElementById("video-wrapper"),
    zoneCanvas: document.getElementById("zone-drawing-canvas"),
    
    // Video buttons
    btnDrawZone: document.getElementById("btn-draw-zone"),
    btnSaveZone: document.getElementById("btn-save-zone"),
    btnClearZone: document.getElementById("btn-clear-zone"),
    toggleZoneActive: document.getElementById("toggle-zone-active"),
    
    // Settings inputs
    settingsForm: document.getElementById("settings-form"),
    cameraUrlInput: document.getElementById("camera-url-input"),
    confSlider: document.getElementById("conf-threshold-slider"),
    confVal: document.getElementById("conf-threshold-val"),
    cooldownSlider: document.getElementById("cooldown-slider"),
    cooldownVal: document.getElementById("cooldown-val"),
    consecutiveInput: document.getElementById("consecutive-frames-input"),
    telegramTokenInput: document.getElementById("telegram-token-input"),
    telegramChatIdInput: document.getElementById("telegram-chat-id-input"),
    
    // Arduino elements
    arduinoPortInput: document.getElementById("arduino-port-input"),
    toggleArduinoEnabled: document.getElementById("toggle-arduino-enabled"),
    btnTriggerSpray: document.getElementById("btn-trigger-spray"),
    arduinoStatusText: document.getElementById("arduino-status-text"),
    arduinoDot: document.getElementById("arduino-dot"),
    
    // Action buttons
    btnTestNotification: document.getElementById("btn-test-notification"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
    
    // Logs timeline
    logCount: document.getElementById("log-count"),
    logsGrid: document.getElementById("logs-grid-container"),
    noLogsPrompt: document.getElementById("no-logs-prompt"),
    
    // Lightbox modal
    lightboxModal: document.getElementById("lightbox-modal"),
    lightboxImg: document.getElementById("lightbox-img"),
    lightboxCaption: document.getElementById("lightbox-caption"),
    lightboxClose: document.getElementById("lightbox-close"),
    
    // Toast
    toastRoot: document.getElementById("toast-root")
};

// ==========================================================================
// Initialization & Mounting
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    // 1. Fetch current configs
    fetchConfig();
    
    // 2. Load logs history
    fetchLogs();
    
    // 3. Setup event listeners
    setupEventListeners();
    
    // 4. Start polling system status
    startStatusPolling();
    
    // 5. Start polling capture logs for updates
    startLogsPolling();
    
    // 6. Bind canvas resize handler
    initCanvasResizer();
});

// ==========================================================================
// Canvas drawing engine (Normalized coordinates)
// ==========================================================================
function initCanvasResizer() {
    // Resize observer ensures canvas perfectly aligns with video img dimensions
    canvasResizeObserver = new ResizeObserver(() => {
        resizeCanvasToMatchVideo();
    });
    canvasResizeObserver.observe(elements.liveStreamFeed);
}

function resizeCanvasToMatchVideo() {
    const videoWidth = elements.liveStreamFeed.clientWidth;
    const videoHeight = elements.liveStreamFeed.clientHeight;
    
    elements.zoneCanvas.width = videoWidth;
    elements.zoneCanvas.height = videoHeight;
    
    // Redraw after resizing
    drawZoneOnCanvas();
}

function drawZoneOnCanvas() {
    const ctx = elements.zoneCanvas.getContext("2d");
    const w = elements.zoneCanvas.width;
    const h = elements.zoneCanvas.height;
    
    ctx.clearRect(0, 0, w, h);
    
    // Don't draw zone if disabled by toggle (unless in active draw editing mode)
    if (!elements.toggleZoneActive.checked && !isDrawModeActive) {
        return;
    }
    
    const points = isDrawModeActive ? drawnZonePoints : configState.detection_zone;
    
    if (!points || points.length === 0) return;
    
    // Draw semi-transparent area fill
    ctx.fillStyle = isDrawModeActive ? "rgba(99, 102, 241, 0.2)" : "rgba(241, 102, 99, 0.15)";
    ctx.strokeStyle = isDrawModeActive ? "#6366f1" : "#f16663";
    ctx.lineWidth = 2.5;
    
    ctx.beginPath();
    const firstPt = points[0];
    ctx.moveTo(firstPt.x * w, firstPt.y * h);
    
    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x * w, points[i].y * h);
    }
    
    if (points.length > 2) {
        ctx.closePath();
    }
    
    ctx.fill();
    ctx.stroke();
    
    // Draw small nodes/circles for clicked coordinate positions
    ctx.fillStyle = "#ffffff";
    points.forEach((pt, index) => {
        ctx.beginPath();
        ctx.arc(pt.x * w, pt.y * h, 4.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        
        // Number nodes in draw mode to help structure ordering
        if (isDrawModeActive) {
            ctx.fillStyle = "#ffffff";
            ctx.font = "10px Inter";
            ctx.fillText(index + 1, (pt.x * w) + 8, (pt.y * h) - 4);
            ctx.fillStyle = "#6366f1";
        }
    });
}

function enterDrawMode() {
    isDrawModeActive = true;
    drawnZonePoints = [...configState.detection_zone]; // Load existing zone
    elements.zoneCanvas.style.pointerEvents = "auto"; // Enable clicks
    elements.zoneCanvas.style.cursor = "crosshair";
    
    elements.btnDrawZone.innerHTML = "<i class='fa-solid fa-ban'></i> Cancel Drawing";
    elements.btnDrawZone.classList.replace("btn-outline", "btn-danger");
    elements.btnSaveZone.classList.remove("btn-hidden");
    elements.btnClearZone.classList.remove("btn-hidden");
    
    showToast("Edit Zone Mode", "Click on the video stream to drop points defining the landing zone polygon.", "warning");
    drawZoneOnCanvas();
}

function exitDrawMode() {
    isDrawModeActive = false;
    elements.zoneCanvas.style.pointerEvents = "none"; // Disable clicks
    elements.zoneCanvas.style.cursor = "default";
    
    elements.btnDrawZone.innerHTML = "<i class='fa-solid fa-pen-ruler'></i> Draw Detection Zone";
    elements.btnDrawZone.classList.replace("btn-danger", "btn-outline");
    elements.btnSaveZone.classList.add("btn-hidden");
    elements.btnClearZone.classList.add("btn-hidden");
    
    drawZoneOnCanvas();
}

// ==========================================================================
// Event Bindings
// ==========================================================================
function setupEventListeners() {
    // Slider values synchronization
    elements.confSlider.addEventListener("input", (e) => {
        elements.confVal.textContent = `${Math.round(e.target.value * 100)}%`;
    });
    
    elements.cooldownSlider.addEventListener("input", (e) => {
        elements.cooldownVal.textContent = `${e.target.value}m`;
    });
    
    // Apply Settings
    elements.settingsForm.addEventListener("submit", (e) => {
        e.preventDefault();
        saveConfigToServer();
    });
    
    // Draw Zone Button toggle
    elements.btnDrawZone.addEventListener("click", () => {
        if (isDrawModeActive) {
            exitDrawMode();
        } else {
            enterDrawMode();
        }
    });
    
    // Click on canvas to add points
    elements.zoneCanvas.addEventListener("click", (e) => {
        if (!isDrawModeActive) return;
        
        const rect = elements.zoneCanvas.getBoundingClientRect();
        const normX = e.offsetX / rect.width;
        const normY = e.offsetY / rect.height;
        
        // Limit to sane number of points (e.g. 12 sides)
        if (drawnZonePoints.length >= 12) {
            showToast("Limit Reached", "A maximum of 12 vertices is allowed.", "warning");
            return;
        }
        
        drawnZonePoints.push({ x: Number(normX.toFixed(4)), y: Number(normY.toFixed(4)) });
        drawZoneOnCanvas();
    });
    
    // Save zone points
    elements.btnSaveZone.addEventListener("click", () => {
        if (drawnZonePoints.length < 3) {
            showToast("Invalid Shape", "Please draw a polygon with at least 3 points.", "error");
            return;
        }
        
        configState.detection_zone = [...drawnZonePoints];
        saveConfigToServer(() => {
            exitDrawMode();
            showToast("Zone Saved", "Interactive detection zone mask active.", "success");
        });
    });
    
    // Clear zone coordinates
    elements.btnClearZone.addEventListener("click", () => {
        drawnZonePoints = [];
        configState.detection_zone = [];
        saveConfigToServer(() => {
            exitDrawMode();
            showToast("Zone Cleared", "The entire frame is now monitored.", "success");
        });
    });
    
    // Toggle Zone Visibility
    elements.toggleZoneActive.addEventListener("change", () => {
        drawZoneOnCanvas();
    });
    
    // Send test Telegram notification
    elements.btnTestNotification.addEventListener("click", triggerTestNotification);
    
    // Trigger manual spray override
    elements.btnTriggerSpray.addEventListener("click", triggerManualSpray);
    
    // Auto-save Arduino enable toggle change instantly
    elements.toggleArduinoEnabled.addEventListener("change", () => {
        saveConfigToServer();
    });
    
    // Lightbox modal close
    elements.lightboxClose.addEventListener("click", () => {
        elements.lightboxModal.classList.remove("show");
    });
    
    elements.lightboxModal.addEventListener("click", (e) => {
        if (e.target === elements.lightboxModal) {
            elements.lightboxModal.classList.remove("show");
        }
    });
}

// ==========================================================================
// REST Backend Integrations
// ==========================================================================
async function fetchConfig() {
    try {
        const response = await fetch("/api/config");
        if (!response.ok) throw new Error("Network configuration fetch failed.");
        
        configState = await response.json();
        
        // Sync values to DOM inputs
        elements.cameraUrlInput.value = configState.camera_url;
        elements.confSlider.value = configState.confidence_threshold;
        elements.confVal.textContent = `${Math.round(configState.confidence_threshold * 100)}%`;
        elements.cooldownSlider.value = configState.cooldown_minutes;
        elements.cooldownVal.textContent = `${configState.cooldown_minutes}m`;
        elements.consecutiveInput.value = configState.consecutive_frames;
        elements.telegramTokenInput.value = configState.telegram_bot_token;
        elements.telegramChatIdInput.value = configState.telegram_chat_id;
        
        // Arduino loading
        elements.arduinoPortInput.value = configState.arduino_port || "";
        elements.toggleArduinoEnabled.checked = !!configState.arduino_enabled;
        
        // Redraw zone
        drawZoneOnCanvas();
    } catch (e) {
        showToast("Error", "Could not retrieve settings from FastAPI server.", "error");
        console.error(e);
    }
}

async function saveConfigToServer(callback = null) {
    try {
        // Collect current input states
        const payload = {
            camera_url: elements.cameraUrlInput.value.trim(),
            confidence_threshold: parseFloat(elements.confSlider.value),
            cooldown_minutes: parseInt(elements.cooldownSlider.value),
            consecutive_frames: parseInt(elements.consecutiveInput.value),
            telegram_bot_token: elements.telegramTokenInput.value.trim(),
            telegram_chat_id: elements.telegramChatIdInput.value.trim(),
            detection_zone: configState.detection_zone,
            arduino_port: elements.arduinoPortInput.value.trim(),
            arduino_enabled: elements.toggleArduinoEnabled.checked
        };

        const response = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("Failed to write configs.");
        const result = await response.json();
        
        // Update local memory state
        configState = { ...configState, ...payload };
        
        if (callback) {
            callback();
        } else {
            showToast("Settings Updated", "Configurations written to disk & updated in-memory.", "success");
        }
        
        drawZoneOnCanvas();
    } catch (e) {
        showToast("Save Error", "Could not commit configuration modifications.", "error");
        console.error(e);
    }
}

async function fetchLogs() {
    try {
        const response = await fetch("/api/logs");
        if (!response.ok) throw new Error("Could not retrieve capture logs.");
        const logs = await response.json();
        
        renderLogsTimeline(logs);
    } catch (e) {
        console.error("Failed loading visitor log timeline", e);
    }
}

async function triggerTestNotification() {
    const originalText = elements.btnTestNotification.innerHTML;
    elements.btnTestNotification.disabled = true;
    elements.btnTestNotification.innerHTML = "<i class='fa-solid fa-circle-notch fa-spin'></i> Sending test...";

    try {
        const response = await fetch("/api/test-notification", { method: "POST" });
        const result = await response.json();
        
        if (response.ok) {
            showToast("Notification Sent", result.message || "Alert delivered to Telegram!", "success");
        } else {
            showToast("Delivery Failed", result.message || "Check your credentials.", "error");
        }
    } catch (e) {
        showToast("Error", "API test notification connection failure.", "error");
        console.error(e);
    } finally {
        elements.btnTestNotification.disabled = false;
        elements.btnTestNotification.innerHTML = originalText;
    }
}

async function triggerManualSpray() {
    const originalText = elements.btnTriggerSpray.innerHTML;
    elements.btnTriggerSpray.disabled = true;
    elements.btnTriggerSpray.innerHTML = "<i class='fa-solid fa-circle-notch fa-spin'></i> Spraying...";

    try {
        const response = await fetch("/api/trigger-spray", { method: "POST" });
        const result = await response.json();
        
        if (response.ok) {
            showToast("Spray Activated", result.message || "Water spray triggered successfully!", "success");
        } else {
            showToast("Spray Failed", result.message || "Could not trigger water gun.", "error");
        }
    } catch (e) {
        showToast("Error", "Deterrent system connection failure.", "error");
        console.error(e);
    } finally {
        elements.btnTriggerSpray.disabled = false;
        elements.btnTriggerSpray.innerHTML = originalText;
    }
}

// ==========================================================================
// Real-time UI Polling & Syncing
// ==========================================================================
function startStatusPolling() {
    setInterval(async () => {
        try {
            const response = await fetch("/api/status");
            if (!response.ok) return;
            const status = await response.json();
            
            // Sync camera stream stats
            elements.cameraStatusText.textContent = status.camera_status;
            elements.cameraDot.className = "status-dot " + (
                status.camera_status === "Connected" ? "active" :
                status.camera_status === "Error" ? "disconnected" : "loading"
            );
            
            // Sync model stats
            elements.modelStatusText.textContent = status.model_status;
            elements.modelDot.className = "status-dot " + (
                status.model_status === "Active" ? "active" :
                status.model_status.startsWith("Error") ? "disconnected" : "loading"
            );
            
            // Sync Arduino stats
            elements.arduinoStatusText.textContent = status.arduino_status;
            elements.arduinoDot.className = "status-dot " + (
                status.arduino_status === "Connected" ? "cyan" :
                status.arduino_status.startsWith("Error") ? "disconnected" : "loading"
            );
        } catch (e) {
            // Silently fail connection errors during dev reload cycles
        }
    }, 2000);
}

function startLogsPolling() {
    setInterval(() => {
        // Poll logs timeline for updates without reloading entire page
        fetchLogs();
    }, 5000);
}

function renderLogsTimeline(logs) {
    elements.logCount.textContent = logs.length;
    
    if (!logs || logs.length === 0) {
        elements.noLogsPrompt.style.display = "flex";
        elements.logsGrid.style.display = "none";
        return;
    }
    
    elements.noLogsPrompt.style.display = "none";
    elements.logsGrid.style.display = "grid";
    
    // Build cards list dynamically
    // Avoid resetting DOM structure entirely if items are unchanged to prevent flickering
    const currentCardCount = elements.logsGrid.children.length;
    if (currentCardCount === logs.length) {
        // Assume identical for now or fast skip
        return;
    }
    
    elements.logsGrid.innerHTML = ""; // Hard reset since numbers differ
    
    logs.forEach(log => {
        const card = document.createElement("div");
        card.className = "log-item";
        card.innerHTML = `
            <div class="log-thumb-wrapper">
                <img class="log-thumb" src="${log.image_path}" alt="Captured Visitor" loading="lazy">
                <span class="log-badge-conf">${Math.round(log.confidence * 100)}% Match</span>
            </div>
            <div class="log-details">
                <span class="log-title"><i class="fa-solid fa-kiwi-bird"></i> Visitor Logged</span>
                <span class="log-time">${log.timestamp}</span>
            </div>
        `;
        
        // Open fullscreen lightbox on card click
        card.addEventListener("click", () => {
            elements.lightboxImg.src = log.image_path;
            elements.lightboxCaption.innerHTML = `
                🐦 <b>Bird Landing Registered</b><br>
                🕒 <b>Time:</b> ${log.timestamp} | 🎯 <b>Confidence:</b> ${Math.round(log.confidence * 100)}%
            `;
            elements.lightboxModal.classList.add("show");
        });
        
        elements.logsGrid.appendChild(card);
    });
}

// ==========================================================================
// Toast Alerts Module
// ==========================================================================
function showToast(title, message, type = "success") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    let iconClass = "fa-circle-check";
    if (type === "error") iconClass = "fa-circle-xmark";
    if (type === "warning") iconClass = "fa-triangle-exclamation";
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass} toast-icon"></i>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-msg">${message}</div>
        </div>
        <button class="toast-close">&times;</button>
    `;
    
    // Bind close click
    toast.querySelector(".toast-close").addEventListener("click", () => {
        dismissToast(toast);
    });
    
    elements.toastRoot.appendChild(toast);
    
    // Automatic dismissal after 4 seconds
    setTimeout(() => {
        dismissToast(toast);
    }, 4000);
}

function dismissToast(toast) {
    toast.style.animation = "fade-out 0.3s forwards";
    setTimeout(() => {
        if (toast.parentNode === elements.toastRoot) {
            elements.toastRoot.removeChild(toast);
        }
    }, 300);
}
