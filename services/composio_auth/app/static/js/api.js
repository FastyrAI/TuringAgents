/**
 * API Communication Utility
 * Handles all API calls with authentication and error handling
 */

class ApiClient {
    constructor() {
        this.baseURL = '';  // Same origin
        this.token = localStorage.getItem('auth_token');
        this.tokenExpiry = localStorage.getItem('token_expiry');
        this.refreshTimer = null;
        
        // Initialize token expiry monitoring
        this.initTokenMonitoring();
    }

    /**
     * Initialize token expiry monitoring
     */
    initTokenMonitoring() {
        if (this.token && this.tokenExpiry) {
            const expiryTime = parseInt(this.tokenExpiry);
            const currentTime = Date.now();
            const timeUntilExpiry = expiryTime - currentTime;
            
            if (timeUntilExpiry > 0) {
                // Set a timer to warn about expiry 5 minutes before
                const warningTime = Math.max(timeUntilExpiry - (5 * 60 * 1000), 1000);
                this.setExpiryWarning(warningTime);
                
                // Set a timer to auto-logout at expiry
                this.setAutoLogout(timeUntilExpiry);
            } else {
                // Token already expired - clean up silently (don't show logout message)
                this.clearToken();
            }
        }
    }

    /**
     * Set expiry warning timer
     */
    setExpiryWarning(delay) {
        setTimeout(() => {
            // The auth manager will handle the warning display
            if (window.auth) {
                window.auth.handleTokenExpiry();
            }
        }, delay);
    }

    /**
     * Set auto-logout timer
     */
    setAutoLogout(delay) {
        setTimeout(() => {
            this.handleTokenExpiry();
        }, delay);
    }

    /**
     * Handle token expiry
     */
    handleTokenExpiry(silent = false) {
        this.clearToken();
        
        // Only show logout message and redirect if this is an active session expiry
        if (!silent && window.auth) {
            window.auth.handleTokenExpiry();
        }
    }

    /**
     * Clear refresh timer
     */
    clearRefreshTimer() {
        if (this.refreshTimer) {
            clearTimeout(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    /**
     * Show token expiry warning
     */
    showExpiryWarning() {
        if (window.showAlert) {
            showAlert('⚠️ Your session will expire in 5 minutes. Please save your work.', 'warning');
        }
    }

    /**
     * Get authentication headers
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };
        
        if (this.token && !this.isTokenExpired()) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }

    /**
     * Check if token is expired
     */
    isTokenExpired() {
        if (!this.tokenExpiry) return false;
        
        const expiryTime = parseInt(this.tokenExpiry);
        const currentTime = Date.now();
        
        return currentTime >= expiryTime;
    }

    /**
     * Set authentication token with expiry
     */
    setToken(token, expiresIn = 7200) { // Default 2 hours in seconds
        this.token = token;
        
        if (token) {
            // Calculate expiry time (convert seconds to milliseconds)
            const expiryTime = Date.now() + (expiresIn * 1000);
            
            localStorage.setItem('auth_token', token);
            localStorage.setItem('token_expiry', expiryTime.toString());
            
            this.tokenExpiry = expiryTime.toString();
            
            // Restart token monitoring
            this.clearRefreshTimer();
            this.initTokenMonitoring();
        } else {
            this.clearToken();
        }
    }

    /**
     * Clear authentication token
     */
    clearToken() {
        this.token = null;
        this.tokenExpiry = null;
        
        localStorage.removeItem('auth_token');
        localStorage.removeItem('token_expiry');
        
        this.clearRefreshTimer();
    }

    /**
     * Make HTTP request with enhanced error handling
     */
    async request(endpoint, options = {}) {
        // Check token expiry before making request
        if (this.token && this.isTokenExpired()) {
            this.handleTokenExpiry();
            throw new Error('Session expired. Please login again.');
        }

        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: this.getHeaders(),
            ...options
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                // Handle specific HTTP status codes
                if (response.status === 401) {
                    // Unauthorized - token might be invalid or expired
                    this.handleTokenExpiry();
                    throw new Error('Authentication failed. Please login again.');
                } else if (response.status === 403) {
                    throw new Error('Access denied. You do not have permission for this action.');
                } else if (response.status === 429) {
                    throw new Error('Too many requests. Please wait a moment and try again.');
                } else if (response.status >= 500) {
                    throw new Error('Server error. Please try again later.');
                }
                
                throw new Error(data.message || data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API Request failed:', error);
            
            // Handle network errors
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Network error. Please check your connection.');
            }
            
            throw error;
        }
    }

    /**
     * GET request
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    // Authentication endpoints
    async signup(userData) {
        const response = await this.post('/api/v1/auth/signup', userData);
        if (response.success && response.data.access_token) {
            const expiresIn = response.data.expires_in || 28800; // Default 8 hours
            this.setToken(response.data.access_token, expiresIn);
        }
        return response;
    }

    async login(credentials) {
        const response = await this.post('/api/v1/auth/login', credentials);
        if (response.success && response.data.access_token) {
            const expiresIn = response.data.expires_in || 28800; // Default 8 hours
            this.setToken(response.data.access_token, expiresIn);
        }
        return response;
    }

    async logout() {
        try {
            await this.post('/api/v1/auth/logout', {});
        } finally {
            this.clearToken();
        }
    }

    async getCurrentUser() {
        return this.get('/api/v1/auth/me');
    }

    // Composio endpoints
    async getProviders() {
        return this.get('/api/v1/composio/providers');
    }

    async getConnections() {
        return this.get('/api/v1/composio/connections');
    }

    async getAuthUrl(provider) {
        return this.get(`/api/v1/composio/auth/provider/?provider=${provider}`);
    }

    async connectWithOAuth(provider) {
        // Call the /auth/provider/ endpoint with oauth2 auth_type
        // Send form data with empty api_key
        const formData = 'api_key=';
        
        const response = await fetch(`/api/v1/composio/auth/provider/?provider=${provider}&auth_type=oauth2`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || data.detail || 'Request failed');
        }
        return data;
    }

    async getProviderAuthType(provider) {
        return this.get(`/api/v1/composio/auth/type/${provider}`);
    }

    async connectWithApiKey(provider, apiKey) {
        // Call the /auth/provider/ endpoint with api_key auth_type
        const formData = new FormData();
        formData.append('api_key', apiKey);
        
        const response = await fetch(`/api/v1/composio/auth/provider/?provider=${provider}&auth_type=api_key`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || data.detail || 'Request failed');
        }
        return data;
    }

    async executeAction(prompt) {
        // Send as form data since the endpoint expects form parameter
        const formData = new FormData();
        formData.append('prompt', prompt);
        
        const response = await fetch('/api/v1/composio/action', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            },
            body: formData
        });
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || data.detail || 'Request failed');
        }
        return data;
    }

    // OpenAI Key endpoints
    async createOpenAIKey(apiKey) {
        return this.post('/api/v1/openai-keys/', { api_key: apiKey });
    }

    async getOpenAIKey() {
        return this.get('/api/v1/openai-keys/');
    }

    async updateOpenAIKey(updateData) {
        return this.put('/api/v1/openai-keys/', updateData);
    }

    async deleteOpenAIKey() {
        return this.delete('/api/v1/openai-keys/');
    }

    async toggleOpenAIKey() {
        return this.post('/api/v1/openai-keys/toggle', {});
    }

    /**
     * Check if user is authenticated and token is valid
     */
    isAuthenticated() {
        return !!this.token && !this.isTokenExpired();
    }

    /**
     * Get time until token expiry (in minutes)
     */
    getTimeUntilExpiry() {
        if (!this.tokenExpiry) return 0;
        
        const expiryTime = parseInt(this.tokenExpiry);
        const currentTime = Date.now();
        const timeLeft = expiryTime - currentTime;
        
        return Math.max(0, Math.floor(timeLeft / (1000 * 60))); // Convert to minutes
    }
}

// Global API client instance
const api = new ApiClient();
