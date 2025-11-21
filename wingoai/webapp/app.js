class WinGoPredictionApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.predictions = {
            '30sec': null,
            '1min': null,
            '3min': null,
            '5min': null
        };
        this.history = {
            '30sec': [],
            '1min': [],
            '3min': [],
            '5min': []
        };
        this.telegramId = null;
        
        this.init();
    }
    
    init() {
        this.setupWebSocket();
        this.loadUserStatus();
        this.loadRecentPredictions();
        this.setupEventListeners();
        this.setupGameTabs();
    }
    
    setupEventListeners() {
        // Check if user is authenticated via Telegram
        this.checkTelegramAuth();
    }
    
    setupGameTabs() {
        const tabs = document.querySelectorAll('.game-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const gameType = e.target.dataset.game;
                this.switchGameTab(gameType);
            });
        });
    }
    
    switchGameTab(gameType) {
        // Update active tab
        document.querySelectorAll('.game-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`.game-tab[data-game="${gameType}"]`).classList.add('active');
        
        // Show corresponding prediction section
        document.querySelectorAll('.prediction-section').forEach(section => {
            section.style.display = 'none';
        });
        document.getElementById(`prediction-${gameType}`).style.display = 'block';
        
        // Update current prediction display
        this.updateCurrentPredictionDisplay(gameType);
    }
    
    checkTelegramAuth() {
        // In a real implementation, this would come from Telegram WebApp
        // For now, we'll simulate
        this.telegramId = localStorage.getItem('tg_id') || null;
        if (!this.telegramId) {
            // Try to get from URL params if available
            const urlParams = new URLSearchParams(window.location.search);
            this.telegramId = urlParams.get('tg_id');
            if (this.telegramId) {
                localStorage.setItem('tg_id', this.telegramId);
            }
        }
        
        if (this.telegramId) {
            document.getElementById('user-status').textContent = `TG ID: ${this.telegramId}`;
        } else {
            document.getElementById('user-status').textContent = 'Not authenticated';
        }
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('Connected to WebSocket');
                this.isConnected = true;
                document.getElementById('connection-status').textContent = 'Connected';
                document.getElementById('connection-status').style.color = 'green';
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('Disconnected from WebSocket');
                this.isConnected = false;
                document.getElementById('connection-status').textContent = 'Disconnected';
                document.getElementById('connection-status').style.color = 'red';
                
                // Try to reconnect after 5 seconds
                setTimeout(() => {
                    this.setupWebSocket();
                }, 5000);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                document.getElementById('connection-status').textContent = 'Error';
                document.getElementById('connection-status').style.color = 'red';
            };
        } catch (error) {
            console.error('Failed to connect to WebSocket:', error);
        }
    }
    
    handleWebSocketMessage(data) {
        const gameType = data.game_type;
        
        // Update current prediction
        this.predictions[gameType] = data;
        this.updateCurrentPredictionDisplay(gameType);
        
        // Add to history
        this.addPredictionToHistory(gameType, data);
    }
    
    async loadUserStatus() {
        if (!this.telegramId) return;
        
        try {
            const response = await fetch(`/user/status/${this.telegramId}`);
            const data = await response.json();
            
            if (data.status === 'verified') {
                document.getElementById('user-status').textContent = `Verified: ${this.telegramId}`;
                document.getElementById('user-status').style.color = 'green';
            } else if (data.status === 'not_verified') {
                document.getElementById('user-status').textContent = `Pending: ${this.telegramId}`;
                document.getElementById('user-status').style.color = 'orange';
            } else {
                document.getElementById('user-status').textContent = `Not verified: ${this.telegramId}`;
                document.getElementById('user-status').style.color = 'red';
            }
        } catch (error) {
            console.error('Error loading user status:', error);
        }
    }
    
    async loadRecentPredictions() {
        try {
            const response = await fetch('/predict');
            const predictions = await response.json();
            
            // Load predictions
            Object.keys(predictions).forEach(gameType => {
                if (predictions[gameType] && !predictions[gameType].message) {
                    this.predictions[gameType] = predictions[gameType];
                    this.updateCurrentPredictionDisplay(gameType);
                }
            });
            
            // Load history for each game type
            for (const gameType of Object.keys(this.history)) {
                const historyResponse = await fetch(`/admin/predictions/${gameType}?limit=10`);
                const historyData = await historyResponse.json();
                this.history[gameType] = historyData;
                this.renderPredictionHistory(gameType);
            }
        } catch (error) {
            console.error('Error loading recent predictions:', error);
        }
    }
    
    updateCurrentPredictionDisplay(gameType) {
        const prediction = this.predictions[gameType];
        if (!prediction) return;
        
        const periodEl = document.getElementById(`${gameType}-period`);
        const colorEl = document.getElementById(`${gameType}-color`);
        const confidenceFillEl = document.getElementById(`${gameType}-confidence-fill`);
        const confidenceValueEl = document.getElementById(`${gameType}-confidence-value`);
        const statusEl = document.getElementById(`${gameType}-status`);
        
        if (periodEl) periodEl.textContent = prediction.period;
        if (colorEl) colorEl.textContent = prediction.color;
        
        const confidencePercent = Math.round(prediction.confidence * 100);
        if (confidenceValueEl) confidenceValueEl.textContent = `${confidencePercent}%`;
        if (confidenceFillEl) confidenceFillEl.style.width = `${confidencePercent}%`;
        
        const statusText = prediction.safe ? 'SAFE TO PLAY' : 'AVOID';
        const statusClass = prediction.safe ? 'status safe' : 'status avoid';
        
        if (statusEl) {
            statusEl.textContent = statusText;
            statusEl.className = statusClass;
        }
    }
    
    addPredictionToHistory(gameType, prediction) {
        this.history[gameType].unshift(prediction);
        // Keep only last 10 predictions
        if (this.history[gameType].length > 10) {
            this.history[gameType] = this.history[gameType].slice(0, 10);
        }
        
        this.renderPredictionHistory(gameType);
    }
    
    renderPredictionHistory(gameType) {
        const container = document.getElementById(`history-${gameType}`);
        if (!container) return;
        
        container.innerHTML = '';
        
        this.history[gameType].forEach(pred => {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            const confidencePercent = Math.round(pred.confidence * 100);
            const statusClass = pred.safe ? 'safe' : 'avoid';
            const statusText = pred.safe ? 'SAFE' : 'AVOID';
            
            item.innerHTML = `
                <div class="history-period">${pred.period}</div>
                <div class="history-color ${pred.color.toLowerCase()}">${pred.color}</div>
                <div class="history-confidence">${confidencePercent}%</div>
                <div class="history-status ${statusClass}">${statusText}</div>
                <div class="history-time">${new Date(pred.timestamp).toLocaleTimeString()}</div>
            `;
            
            container.appendChild(item);
        });
    }
}

// Initialize the app when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new WinGoPredictionApp();
});