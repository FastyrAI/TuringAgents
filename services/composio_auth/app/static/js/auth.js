/**
 * Authentication Management
 * Handles user authentication state and navigation
 */

class AuthManager {
    constructor() {
        this.currentUser = null;
        this.authInitialized = false;
        this.authReadyCallbacks = [];
        this.init();
    }

    /**
     * Initialize authentication
     */
    async init() {
        // Show loading state during auth check
        this.showAuthLoading(true);
        
        if (api.isAuthenticated()) {
            try {
                // Add timeout for /me API call
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error('Authentication timeout')), 10000)
                );
                
                this.currentUser = await Promise.race([
                    api.getCurrentUser(),
                    timeoutPromise
                ]);
                
                this.updateNavigation(true);
                
                // If user was remembered and we're on login/signup page, redirect to actions
                const isRemembered = localStorage.getItem('remember_user') === 'true';
                const currentHash = window.location.hash.substr(1);
                
                if (isRemembered && (currentHash === 'login' || currentHash === 'signup' || currentHash === '' || currentHash === 'home')) {
                    navigateTo('actions');
                }
            } catch (error) {
                console.error('Failed to get current user:', error);
                // Silent cleanup - don't show logout message during initialization
                this.currentUser = null;
                localStorage.removeItem('remember_user');
                api.clearToken();
                this.updateNavigation(false);
            }
        } else {
            this.updateNavigation(false);
        }
        
        // Hide loading state
        this.showAuthLoading(false);
        
        // Signal that auth initialization is complete
        this.authInitialized = true;
        this.triggerAuthReady();
    }

    /**
     * Update navigation based on auth state
     */
    updateNavigation(isAuthenticated) {
        const loginLink = document.getElementById('login-link');
        const signupLink = document.getElementById('signup-link');
        const actionsLink = document.getElementById('actions-link');
        const connectionsLink = document.getElementById('connections-link');
        const openaiKeysLink = document.getElementById('openai-keys-link');
        const logoutBtn = document.getElementById('logout-btn');

        if (isAuthenticated) {
            loginLink.classList.add('d-none');
            signupLink.classList.add('d-none');
            actionsLink.classList.remove('d-none');
            connectionsLink.classList.remove('d-none');
            openaiKeysLink.classList.remove('d-none');
            logoutBtn.classList.remove('d-none');
        } else {
            loginLink.classList.remove('d-none');
            signupLink.classList.remove('d-none');
            actionsLink.classList.add('d-none');
            connectionsLink.classList.add('d-none');
            openaiKeysLink.classList.add('d-none');
            logoutBtn.classList.add('d-none');
        }
    }

    /**
     * Login user
     */
    async login(credentials, rememberMe = false) {
        try {
            const response = await api.login(credentials);
            
            if (response.success) {
                // Handle "remember me" functionality
                if (rememberMe) {
                    localStorage.setItem('remember_user', 'true');
                    // Store token with longer expiry in localStorage (already done by API client)
                } else {
                    localStorage.removeItem('remember_user');
                    // Could implement sessionStorage for shorter sessions in the future
                }

                this.currentUser = await api.getCurrentUser();
                this.updateNavigation(true);
                
                // Welcome message with user name
                const userName = this.currentUser.name || this.currentUser.email;
                showAlert(`🎉 Welcome back, ${userName}!`, 'success');
                
                // Redirect to intended page or actions page
                setTimeout(() => {
                    this.handlePostLoginRedirect();
                }, 1500);
                
                return true;
            } else {
                showAlert(response.message || 'Login failed', 'danger');
                return false;
            }
        } catch (error) {
            // Handle specific error cases
            let errorMessage = 'Login failed';
            
            if (error.message.includes('401') || error.message.includes('Invalid email or password')) {
                errorMessage = 'Invalid email or password. Please check your credentials.';
            } else if (error.message.includes('423') || error.message.includes('locked')) {
                errorMessage = 'Account temporarily locked due to failed attempts. Please try again later.';
            } else if (error.message.includes('network') || error.message.includes('fetch')) {
                errorMessage = 'Network error. Please check your connection and try again.';
            } else {
                errorMessage = error.message || 'Login failed. Please try again.';
            }
            
            showAlert(errorMessage, 'danger');
            return false;
        }
    }

    /**
     * Signup user
     */
    async signup(userData) {
        try {
            const response = await api.signup(userData);
            
            if (response.success) {
                showAlert('🎉 Registration successful! Redirecting to login...', 'success');
                
                // Auto-redirect to login after a short delay
                setTimeout(() => {
                    navigateTo('login');
                }, 2000);
                
                return true;
            } else {
                showAlert(response.message || 'Registration failed', 'danger');
                return false;
            }
        } catch (error) {
            // Handle specific error cases
            let errorMessage = 'Registration failed';
            
            if (error.message.includes('email')) {
                errorMessage = 'Email address is already registered or invalid';
            } else if (error.message.includes('username')) {
                errorMessage = 'Username is already taken';
            } else if (error.message.includes('password')) {
                errorMessage = 'Password does not meet security requirements';
            } else if (error.message.includes('validation')) {
                errorMessage = 'Please check your input and try again';
            } else {
                errorMessage = error.message || 'Registration failed';
            }
            
            showAlert(errorMessage, 'danger');
            return false;
        }
    }

    /**
     * Logout user
     */
    async logout() {
        try {
            await api.logout();
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear user state and remember me preference
            this.currentUser = null;
            localStorage.removeItem('remember_user');
            
            this.updateNavigation(false);
            showAlert('👋 Logged out successfully', 'info');
            navigateTo('login');
        }
    }

    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        return !!this.currentUser && api.isAuthenticated();
    }

    /**
     * Get current user
     */
    getCurrentUser() {
        return this.currentUser;
    }

    /**
     * Handle token expiry (called by API client)
     */
    handleTokenExpiry() {
        this.currentUser = null;
        localStorage.removeItem('remember_user');
        this.updateNavigation(false);
        
        showAlert('🕐 Your session has expired. Please login again.', 'warning');
        navigateTo('login');
    }

    /**
     * Require authentication for protected routes
     */
    requireAuth() {
        if (!this.isAuthenticated()) {
            const currentPage = window.location.hash.substr(1) || 'home';
            
            // Store the intended destination for post-login redirect
            if (currentPage !== 'login' && currentPage !== 'signup') {
                localStorage.setItem('intended_route', currentPage);
            }
            
            showAlert('🔒 Please login to access this page', 'warning');
            navigateTo('login');
            return false;
        }
        return true;
    }

    /**
     * Handle post-login redirect to intended route
     */
    handlePostLoginRedirect() {
        const intendedRoute = localStorage.getItem('intended_route');
        
        if (intendedRoute && intendedRoute !== 'login' && intendedRoute !== 'signup') {
            localStorage.removeItem('intended_route');
            navigateTo(intendedRoute);
        } else {
            navigateTo('actions');
        }
    }

    /**
     * Get session information
     */
    getSessionInfo() {
        if (!this.isAuthenticated()) {
            return null;
        }

        const timeUntilExpiry = api.getTimeUntilExpiry();
        const isRemembered = localStorage.getItem('remember_user') === 'true';

        return {
            user: this.currentUser,
            timeUntilExpiry: timeUntilExpiry,
            isRemembered: isRemembered,
            expiryWarning: timeUntilExpiry <= 5 && timeUntilExpiry > 0
        };
    }

    /**
     * Extend session (placeholder for future implementation)
     */
    async extendSession() {
        try {
            // In the future, this could call a refresh token endpoint
            // For now, we'll just show a message
            showAlert('Session extension not implemented yet. Please save your work.', 'info');
            return false;
        } catch (error) {
            console.error('Failed to extend session:', error);
            return false;
        }
    }

    /**
     * Show/hide authentication loading state
     */
    showAuthLoading(show) {
        const loadingElement = document.getElementById('loading');
        if (loadingElement) {
            if (show) {
                loadingElement.classList.remove('d-none');
            } else {
                loadingElement.classList.add('d-none');
            }
        }
    }

    /**
     * Check if authentication is initialized
     */
    isAuthInitialized() {
        return this.authInitialized;
    }

    /**
     * Wait for authentication to be initialized
     */
    async waitForAuthReady() {
        if (this.authInitialized) {
            return Promise.resolve();
        }
        
        return new Promise((resolve) => {
            this.authReadyCallbacks.push(resolve);
        });
    }

    /**
     * Trigger auth ready callbacks
     */
    triggerAuthReady() {
        this.authReadyCallbacks.forEach(callback => callback());
        this.authReadyCallbacks = [];
    }
}

// Global auth manager instance
const auth = new AuthManager();

// Make auth available globally for API client callbacks
window.auth = auth;
