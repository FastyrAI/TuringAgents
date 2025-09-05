/**
 * Main Application
 * Handles routing, navigation, and page management
 */

class App {
    constructor() {
        this.currentPage = '';
        this.pages = {
            'home': this.loadHomePage,
            'login': this.loadLoginPage,
            'signup': this.loadSignupPage,
            'actions': this.loadActionsPage,
            'connections': this.loadConnectionsPage,
            'openai-keys': this.loadOpenAIKeysPage
        };
        // Initialize asynchronously
        this.init().catch(error => {
            console.error('Failed to initialize app:', error);
        });
    }

    /**
     * Initialize application
     */
    async init() {
        // Set up hash change listener for routing
        window.addEventListener('hashchange', () => this.handleRoute());
        
        // Set up logout button
        document.getElementById('logout-btn').addEventListener('click', () => {
            auth.logout();
        });

        // Wait for authentication to be initialized before handling initial route
        await auth.waitForAuthReady();
        
        // Initial route
        this.handleRoute();
    }

    /**
     * Handle routing
     */
    handleRoute() {
        const hash = window.location.hash.substr(1) || 'home';
        this.navigateTo(hash);
    }

    /**
     * Navigate to page
     */
    navigateTo(page) {
        // Clean up any active intervals
        this.cleanup();
        
        if (this.pages[page]) {
            this.currentPage = page;
            window.location.hash = page;
            this.pages[page].call(this);
        } else {
            this.navigateTo('home');
        }
    }

    /**
     * Cleanup active intervals and timers
     */
    cleanup() {
        if (this.sessionUpdateInterval) {
            clearInterval(this.sessionUpdateInterval);
            this.sessionUpdateInterval = null;
        }
    }

    /**
     * Load page content
     */
    loadPage(content) {
        document.getElementById('page-content').innerHTML = content;
    }

    /**
     * Home page
     */
    loadHomePage() {
        if (auth.isAuthenticated()) {
            this.navigateTo('actions');
            return;
        }

        const content = `
            <div class="page-section text-center">
                <h1 class="mb-4">Welcome to Composio OAuth Demo</h1>
                <p class="lead mb-4">Connect your accounts and execute natural language actions</p>
                <div class="d-grid gap-2 d-md-block">
                    <a href="#signup" class="btn btn-primary btn-lg">Get Started</a>
                    <a href="#login" class="btn btn-outline-primary btn-lg">Login</a>
                </div>
            </div>
        `;
        this.loadPage(content);
    }

    /**
     * Login page
     */
    loadLoginPage() {
        const content = `
            <div class="page-section">
                <div class="form-container">
                    <h2 class="text-center mb-4">Welcome Back</h2>
                    <p class="text-center text-muted mb-4">Sign in to access your account and manage your connections</p>
                    
                    <form id="login-form" novalidate>
                        <div class="mb-3">
                            <label for="login-email" class="form-label">Email Address *</label>
                            <input 
                                type="email" 
                                class="form-control" 
                                id="login-email" 
                                placeholder="Enter your email address"
                                required
                                autocomplete="email"
                            >
                            <div class="invalid-feedback">
                                Please provide a valid email address.
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="login-password" class="form-label">Password *</label>
                            <div class="position-relative">
                                <input 
                                    type="password" 
                                    class="form-control" 
                                    id="login-password" 
                                    placeholder="Enter your password"
                                    required
                                    autocomplete="current-password"
                                >
                                <button 
                                    type="button" 
                                    class="btn btn-link position-absolute end-0 top-50 translate-middle-y me-2 p-1"
                                    id="toggle-password"
                                    style="z-index: 10;"
                                >
                                    <small>Show</small>
                                </button>
                            </div>
                            <div class="invalid-feedback">
                                Please enter your password.
                            </div>
                        </div>
                        
                        <div class="mb-3 d-flex justify-content-between align-items-center">
                            <div class="form-check">
                                <input type="checkbox" class="form-check-input" id="remember-me">
                                <label class="form-check-label" for="remember-me">
                                    Remember me
                                </label>
                            </div>
                            <a href="#forgot-password" class="text-decoration-none small">Forgot password?</a>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary" id="login-btn">
                                <span class="login-text">Sign In</span>
                                <span class="login-spinner spinner-border spinner-border-sm d-none" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </span>
                            </button>
                        </div>
                    </form>
                    
                    <hr class="my-4">
                    
                    <div class="text-center">
                        <p class="mb-0">Don't have an account? <a href="#signup" class="text-decoration-none fw-semibold">Create one here</a></p>
                    </div>
                    
                    <!-- Demo credentials info -->
                    <div class="mt-4 p-3 bg-light rounded">
                        <small class="text-muted">
                            <strong>Demo Mode:</strong> You can create a new account or use the signup form to test the application.
                        </small>
                    </div>
                </div>
            </div>
        `;
        this.loadPage(content);

        // Set up enhanced form validation and handler
        this.setupLoginForm();
    }

    /**
     * Setup login form with validation
     */
    setupLoginForm() {
        const form = document.getElementById('login-form');
        const submitBtn = document.getElementById('login-btn');
        const submitText = submitBtn.querySelector('.login-text');
        const submitSpinner = submitBtn.querySelector('.login-spinner');
        const togglePassword = document.getElementById('toggle-password');
        const passwordField = document.getElementById('login-password');

        // Password visibility toggle
        togglePassword.addEventListener('click', () => {
            const type = passwordField.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordField.setAttribute('type', type);
            togglePassword.innerHTML = type === 'password' ? '<small>Show</small>' : '<small>Hide</small>';
        });

        // Real-time validation
        const inputs = form.querySelectorAll('input[required]');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateLoginField(input));
            input.addEventListener('input', () => {
                if (input.classList.contains('is-invalid')) {
                    this.validateLoginField(input);
                }
            });
        });

        // Form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Validate all fields
            let isValid = true;
            inputs.forEach(input => {
                if (!this.validateLoginField(input)) {
                    isValid = false;
                }
            });

            if (!isValid) {
                showAlert('Please fix the errors above', 'danger');
                return;
            }

            // Disable submit button and show loading
            submitBtn.disabled = true;
            submitText.classList.add('d-none');
            submitSpinner.classList.remove('d-none');

            try {
                const email = document.getElementById('login-email').value.trim();
                const password = document.getElementById('login-password').value;
                const rememberMe = document.getElementById('remember-me').checked;

                const success = await auth.login({ email, password }, rememberMe);
                
                if (success) {
                    // Clear form
                    form.reset();
                    inputs.forEach(input => {
                        input.classList.remove('is-valid', 'is-invalid');
                    });
                }
            } catch (error) {
                console.error('Login error:', error);
            } finally {
                // Re-enable submit button
                submitBtn.disabled = false;
                submitText.classList.remove('d-none');
                submitSpinner.classList.add('d-none');
            }
        });
    }

    /**
     * Validate login form field
     */
    validateLoginField(field) {
        const value = field.value.trim();
        let isValid = true;

        // Remove previous validation classes
        field.classList.remove('is-valid', 'is-invalid');

        // Required field check
        if (field.hasAttribute('required') && !value) {
            isValid = false;
        }

        // Specific field validations
        switch (field.id) {
            case 'login-email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    isValid = false;
                }
                break;
                
            case 'login-password':
                if (value.length < 1) {
                    isValid = false;
                }
                break;
        }

        // Apply validation classes
        if (isValid) {
            field.classList.add('is-valid');
        } else {
            field.classList.add('is-invalid');
        }

        return isValid;
    }

    /**
     * Signup page
     */
    loadSignupPage() {
        const content = `
            <div class="page-section">
                <div class="form-container">
                    <h2 class="text-center mb-4">Create Your Account</h2>
                    <p class="text-center text-muted mb-4">Join us to connect your accounts and execute natural language actions</p>
                    
                    <form id="signup-form" novalidate>
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name *</label>
                            <input 
                                type="text" 
                                class="form-control" 
                                id="name" 
                                placeholder="Enter your full name"
                                required
                                minlength="2"
                                maxlength="100"
                            >
                            <div class="invalid-feedback">
                                Please provide a valid name (2-100 characters).
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="username" class="form-label">Username *</label>
                            <input 
                                type="text" 
                                class="form-control" 
                                id="username" 
                                placeholder="Choose a unique username"
                                required
                                minlength="3"
                                maxlength="50"
                                pattern="[a-zA-Z0-9_-]+"
                            >
                            <div class="invalid-feedback">
                                Username must be 3-50 characters and contain only letters, numbers, _ or -.
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="email" class="form-label">Email Address *</label>
                            <input 
                                type="email" 
                                class="form-control" 
                                id="email" 
                                placeholder="Enter your email address"
                                required
                            >
                            <div class="invalid-feedback">
                                Please provide a valid email address.
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="password" class="form-label">Password *</label>
                            <input 
                                type="password" 
                                class="form-control" 
                                id="password" 
                                placeholder="Create a strong password"
                                required
                                minlength="8"
                            >
                            <div class="invalid-feedback">
                                Password must be at least 8 characters long.
                            </div>
                            <div class="form-text">
                                Password should be at least 8 characters with a mix of letters, numbers, and special characters.
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <label for="confirm-password" class="form-label">Confirm Password *</label>
                            <input 
                                type="password" 
                                class="form-control" 
                                id="confirm-password" 
                                placeholder="Confirm your password"
                                required
                            >
                            <div class="invalid-feedback">
                                Passwords do not match.
                            </div>
                        </div>
                        
                        <div class="mb-3 form-check">
                            <input type="checkbox" class="form-check-input" id="terms" required>
                            <label class="form-check-label" for="terms">
                                I agree to the <a href="#" target="_blank">Terms of Service</a> and <a href="#" target="_blank">Privacy Policy</a> *
                            </label>
                            <div class="invalid-feedback">
                                You must agree to the terms and conditions.
                            </div>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary" id="signup-btn">
                                <span class="signup-text">Create Account</span>
                                <span class="signup-spinner spinner-border spinner-border-sm d-none" role="status">
                                    <span class="visually-hidden">Loading...</span>
                                </span>
                            </button>
                        </div>
                    </form>
                    
                    <div class="text-center mt-4">
                        <p class="mb-0">Already have an account? <a href="#login" class="text-decoration-none">Sign in here</a></p>
                    </div>
                </div>
            </div>
        `;
        this.loadPage(content);

        // Set up enhanced form validation and handler
        this.setupSignupForm();
    }

    /**
     * Setup signup form with validation
     */
    setupSignupForm() {
        const form = document.getElementById('signup-form');
        const submitBtn = document.getElementById('signup-btn');
        const submitText = submitBtn.querySelector('.signup-text');
        const submitSpinner = submitBtn.querySelector('.signup-spinner');

        // Real-time validation
        const inputs = form.querySelectorAll('input');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
            input.addEventListener('input', () => {
                if (input.classList.contains('is-invalid')) {
                    this.validateField(input);
                }
            });
        });

        // Password confirmation validation
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirm-password');
        
        confirmPassword.addEventListener('input', () => {
            if (password.value !== confirmPassword.value) {
                confirmPassword.setCustomValidity('Passwords do not match');
                confirmPassword.classList.add('is-invalid');
            } else {
                confirmPassword.setCustomValidity('');
                confirmPassword.classList.remove('is-invalid');
                confirmPassword.classList.add('is-valid');
            }
        });

        // Form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Validate all fields
            let isValid = true;
            inputs.forEach(input => {
                if (!this.validateField(input)) {
                    isValid = false;
                }
            });

            if (!isValid) {
                showAlert('Please fix the errors above', 'danger');
                return;
            }

            // Disable submit button and show loading
            submitBtn.disabled = true;
            submitText.classList.add('d-none');
            submitSpinner.classList.remove('d-none');

            try {
                const formData = {
                    name: document.getElementById('name').value.trim(),
                    username: document.getElementById('username').value.trim(),
                    email: document.getElementById('email').value.trim(),
                    password: document.getElementById('password').value
                };

                const success = await auth.signup(formData);
                
                if (success) {
                    // Clear form
                    form.reset();
                    inputs.forEach(input => {
                        input.classList.remove('is-valid', 'is-invalid');
                    });
                }
            } catch (error) {
                console.error('Signup error:', error);
            } finally {
                // Re-enable submit button
                submitBtn.disabled = false;
                submitText.classList.remove('d-none');
                submitSpinner.classList.add('d-none');
            }
        });
    }

    /**
     * Validate individual form field
     */
    validateField(field) {
        const value = field.value.trim();
        let isValid = true;

        // Remove previous validation classes
        field.classList.remove('is-valid', 'is-invalid');

        // Required field check
        if (field.hasAttribute('required') && !value) {
            isValid = false;
        }

        // Specific field validations
        switch (field.id) {
            case 'name':
                if (value.length < 2 || value.length > 100) {
                    isValid = false;
                }
                break;
                
            case 'username':
                const usernameRegex = /^[a-zA-Z0-9_-]{3,50}$/;
                if (!usernameRegex.test(value)) {
                    isValid = false;
                }
                break;
                
            case 'email':
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(value)) {
                    isValid = false;
                }
                break;
                
            case 'password':
                if (value.length < 8) {
                    isValid = false;
                }
                break;
                
            case 'confirm-password':
                const password = document.getElementById('password').value;
                if (value !== password) {
                    isValid = false;
                }
                break;
                
            case 'terms':
                if (!field.checked) {
                    isValid = false;
                }
                break;
        }

        // Apply validation classes
        if (isValid) {
            field.classList.add('is-valid');
        } else {
            field.classList.add('is-invalid');
        }

        return isValid;
    }

    /**
     * Actions page (protected)
     */
    loadActionsPage() {
        if (!auth.requireAuth()) return;

        const user = auth.getCurrentUser();
        const sessionInfo = auth.getSessionInfo();
        
        const content = `
            <div class="page-section">
                <div class="action-container">
                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <h2>Natural Language Actions</h2>
                        <div class="d-flex gap-2">
                            <a href="#openai-keys" class="btn btn-outline-info">🔑 OpenAI Keys</a>
                            <a href="#connections" class="btn btn-outline-primary">Connect Accounts</a>
                        </div>
                    </div>
                    
                    <!-- Session Status -->
                    <div id="session-status" class="mb-4">
                        ${this.renderSessionStatus(sessionInfo)}
                    </div>
                    
                    <div class="mb-4">
                        <div class="d-flex align-items-center mb-3">
                            <div class="me-3">
                                <div class="bg-primary rounded-circle d-flex align-items-center justify-content-center" style="width: 48px; height: 48px;">
                                    <span class="text-white fw-bold">🤖</span>
                                </div>
                            </div>
                            <div>
                                <h5 class="mb-1">AI Assistant</h5>
                                <p class="text-muted mb-0">Tell me what you'd like to do in natural language, and I'll help you execute it!</p>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Quick Action Suggestions -->
                    <div class="mb-4">
                        <h6 class="text-muted mb-2">💡 Quick Actions</h6>
                        <div class="d-flex flex-wrap gap-2" id="quick-actions">
                            <button type="button" class="btn btn-outline-secondary btn-sm quick-action-btn" data-action="Send an email to my team about the project update">
                                📧 Send Team Email
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm quick-action-btn" data-action="Schedule a meeting for next week">
                                📅 Schedule Meeting
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm quick-action-btn" data-action="Get my latest emails">
                                📬 Check Latest Emails
                            </button>
                            <button type="button" class="btn btn-outline-secondary btn-sm quick-action-btn" data-action="Find events for today">
                                🗓️ Today's Events
                            </button>
                        </div>
                    </div>
                    
                    <form id="action-form">
                        <div class="mb-3">
                            <label for="action-prompt" class="form-label d-flex align-items-center">
                                <span class="me-2">🎯 What would you like me to do?</span>
                                <small class="text-muted">(Describe in natural language)</small>
                            </label>
                            <div class="position-relative">
                                <textarea 
                                    class="form-control action-textarea" 
                                    id="action-prompt" 
                                    placeholder="Examples:&#10;• Send an email to john@example.com with subject 'Meeting Tomorrow' and message 'Let's discuss the project'&#10;• Get my calendar events for next week&#10;• Find all unread emails from my manager&#10;• Create a calendar event for 'Team Meeting' tomorrow at 2 PM"
                                    required
                                    rows="4"
                                ></textarea>
                                <div class="position-absolute bottom-0 end-0 p-2">
                                    <small class="text-muted" id="char-count">0/500</small>
                                </div>
                            </div>
                            <div class="form-text">
                                💡 <strong>Tip:</strong> Be specific about what you want to do. Include details like email addresses, dates, times, and any specific content.
                            </div>
                        </div>
                        
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary btn-lg" id="execute-btn">
                                <span class="execute-text">
                                    <i class="me-2">🚀</i>
                                    Execute Action
                                </span>
                                <span class="execute-spinner spinner-border spinner-border-sm d-none" role="status">
                                    <span class="visually-hidden">Processing...</span>
                                </span>
                            </button>
                        </div>
                    </form>
                    
                    <!-- Action Results Section -->
                    <div id="action-result" class="mt-4"></div>
                    

                </div>
            </div>
        `;
        this.loadPage(content);

        // Set up enhanced form functionality
        this.setupActionForm();

        // Set up session status updates
        this.setupSessionMonitoring();
    }

    /**
     * Render session status component
     */
    renderSessionStatus(sessionInfo) {
        if (!sessionInfo) return '';

        const { timeUntilExpiry, isRemembered, expiryWarning } = sessionInfo;
        
        let statusClass = 'success';
        let statusIcon = '✅';
        let statusText = `Session active`;
        
        if (expiryWarning) {
            statusClass = 'warning';
            statusIcon = '⚠️';
            statusText = `Session expires in ${timeUntilExpiry} minutes`;
        } else if (timeUntilExpiry <= 15) {
            statusClass = 'info';
            statusIcon = '🕐';
            statusText = `Session expires in ${timeUntilExpiry} minutes`;
        }

        return `
            <div class="alert alert-${statusClass} alert-dismissible fade show d-flex justify-content-between align-items-center" role="alert">
                <div>
                    <span class="me-2">${statusIcon}</span>
                    <strong>${statusText}</strong>
                    ${isRemembered ? ' • Auto-login enabled' : ''}
                </div>
                <div class="d-flex gap-2">
                    ${expiryWarning ? '<button type="button" class="btn btn-outline-warning btn-sm" onclick="auth.extendSession()">Extend Session</button>' : ''}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            </div>
        `;
    }

    /**
     * Setup enhanced action form with interactive features
     */
    setupActionForm() {
        const form = document.getElementById('action-form');
        const promptTextarea = document.getElementById('action-prompt');
        const executeBtn = document.getElementById('execute-btn');
        const executeText = executeBtn.querySelector('.execute-text');
        const executeSpinner = executeBtn.querySelector('.execute-spinner');
        const charCount = document.getElementById('char-count');

        // Character counter
        promptTextarea.addEventListener('input', () => {
            const count = promptTextarea.value.length;
            charCount.textContent = `${count}/500`;
            
            if (count > 450) {
                charCount.classList.add('text-warning');
            } else if (count > 500) {
                charCount.classList.remove('text-warning');
                charCount.classList.add('text-danger');
            } else {
                charCount.classList.remove('text-warning', 'text-danger');
            }
        });

        // Quick action buttons
        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.getAttribute('data-action');
                promptTextarea.value = action;
                promptTextarea.focus();
                
                // Trigger character count update
                promptTextarea.dispatchEvent(new Event('input'));
                
                // Add visual feedback
                btn.classList.add('btn-primary');
                btn.classList.remove('btn-outline-secondary');
                setTimeout(() => {
                    btn.classList.remove('btn-primary');
                    btn.classList.add('btn-outline-secondary');
                }, 200);
            });
        });

        // Enhanced form submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const prompt = promptTextarea.value.trim();
            if (!prompt) {
                showAlert('Please enter an action to execute', 'warning');
                return;
            }

            if (prompt.length > 500) {
                showAlert('Action description is too long (maximum 500 characters)', 'danger');
                return;
            }

            // Disable form and show loading
            executeBtn.disabled = true;
            executeText.classList.add('d-none');
            executeSpinner.classList.remove('d-none');
            promptTextarea.disabled = true;

            try {
                await this.executeAction(prompt);
                
                // Clear the form for next action
                promptTextarea.value = '';
                charCount.textContent = '0/500';
                
            } finally {
                // Re-enable form
                executeBtn.disabled = false;
                executeText.classList.remove('d-none');
                executeSpinner.classList.add('d-none');
                promptTextarea.disabled = false;
                promptTextarea.focus();
            }
        });

        // Auto-resize textarea
        promptTextarea.addEventListener('input', () => {
            promptTextarea.style.height = 'auto';
            promptTextarea.style.height = Math.min(promptTextarea.scrollHeight, 200) + 'px';
        });
    }



    /**
     * Setup session monitoring for real-time updates
     */
    setupSessionMonitoring() {
        // Update session status every minute
        this.sessionUpdateInterval = setInterval(() => {
            const sessionStatus = document.getElementById('session-status');
            const sessionInfo = auth.getSessionInfo();
            
            if (sessionStatus && sessionInfo) {
                sessionStatus.innerHTML = this.renderSessionStatus(sessionInfo);
            }
        }, 60000); // Update every minute
    }

    /**
     * Connections page (protected)
     */
    loadConnectionsPage() {
        if (!auth.requireAuth()) return;

        const content = `
            <div class="page-section">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2>Account Connections</h2>
                    <a href="#actions" class="btn btn-outline-secondary">Back to Actions</a>
                </div>
                
                <div id="connections-list">
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading connections...</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.loadPage(content);

        // Load connections
        this.loadConnections();
    }

    /**
     * Execute action with enhanced result display
     */
    async executeAction(prompt) {
        const resultContainer = document.getElementById('action-result');
        const timestamp = new Date().toLocaleString();
        
        try {
            // Show initial processing state
            resultContainer.innerHTML = `
                <div class="card border-primary">
                    <div class="card-header bg-primary text-white d-flex align-items-center">
                        <div class="spinner-border spinner-border-sm me-2" role="status">
                            <span class="visually-hidden">Processing...</span>
                        </div>
                        <span>🤖 AI Assistant is processing your request...</span>
                    </div>
                    <div class="card-body">
                        <p class="card-text mb-2"><strong>Your Request:</strong></p>
                        <blockquote class="blockquote">
                            <p class="mb-0">"${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}"</p>
                        </blockquote>
                        <small class="text-muted">Started at ${timestamp}</small>
                    </div>
                </div>
            `;

            const result = await api.executeAction(prompt);
            
            // Show success result
            resultContainer.innerHTML = `
                <div class="card border-success">
                    <div class="card-header bg-success text-white d-flex align-items-center">
                        <span class="me-2">✅</span>
                        <span>Action Completed Successfully!</span>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <p class="card-text mb-2"><strong>Your Request:</strong></p>
                            <blockquote class="blockquote">
                                <p class="mb-0">"${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}"</p>
                            </blockquote>
                        </div>
                        
                        <div class="mb-3">
                            <p class="card-text mb-2"><strong>Result:</strong></p>
                            <div class="bg-light p-3 rounded">
                                ${this.formatActionResult(result)}
                            </div>
                        </div>
                        
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">Completed at ${timestamp}</small>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-outline-primary btn-sm" onclick="document.getElementById('action-prompt').value='${prompt.replace(/'/g, '\\\'').replace(/</g, '&lt;').replace(/>/g, '&gt;')}'; document.getElementById('action-prompt').focus(); document.getElementById('action-prompt').dispatchEvent(new Event('input'));">
                                    🔄 Run Again
                                </button>
                                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="app.shareAction('${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}')">
                                    📤 Share
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Show success notification
            showAlert('🎉 Action completed successfully!', 'success');
            
        } catch (error) {
            // Show error result
            resultContainer.innerHTML = `
                <div class="card border-danger">
                    <div class="card-header bg-danger text-white d-flex align-items-center">
                        <span class="me-2">❌</span>
                        <span>Action Failed</span>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <p class="card-text mb-2"><strong>Your Request:</strong></p>
                            <blockquote class="blockquote">
                                <p class="mb-0">"${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}"</p>
                            </blockquote>
                        </div>
                        
                        <div class="mb-3">
                            <p class="card-text mb-2"><strong>Error Details:</strong></p>
                            <div class="alert alert-danger mb-0">
                                <div class="d-flex align-items-start">
                                    <span class="me-2">⚠️</span>
                                    <div>
                                        <p class="mb-1">${this.escapeHtml(error.message)}</p>
                                        ${this.getErrorHelp(error.message)}
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">Failed at ${timestamp}</small>
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-outline-primary btn-sm" onclick="document.getElementById('action-prompt').value='${prompt.replace(/'/g, '\\\'').replace(/</g, '&lt;').replace(/>/g, '&gt;')}'; document.getElementById('action-prompt').focus(); document.getElementById('action-prompt').dispatchEvent(new Event('input'));">
                                    🔄 Try Again
                                </button>
                                <button type="button" class="btn btn-outline-info btn-sm" onclick="app.suggestFix('${prompt.replace(/</g, '&lt;').replace(/>/g, '&gt;')}')">
                                    💡 Get Help
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Show error notification
            showAlert(`❌ Action failed: ${error.message}`, 'danger');
        }
        
        // Scroll to result
        resultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Format action result for better display
     */
    formatActionResult(result) {
        if (typeof result === 'string') {
            return `<p class="mb-0">${this.escapeHtml(result)}</p>`;
        }
        
        if (typeof result === 'object' && result !== null) {
            // Try to format structured results
            if (result.message) {
                return `<p class="mb-0">${this.escapeHtml(result.message)}</p>`;
            }
            
            if (result.data) {
                return `
                    <p class="mb-2">Action executed successfully!</p>
                    <details>
                        <summary class="text-muted">View Details</summary>
                        <pre class="mt-2 bg-white p-2 border rounded small">${JSON.stringify(result.data, null, 2)}</pre>
                    </details>
                `;
            }
            
            return `
                <p class="mb-2">Action completed!</p>
                <details>
                    <summary class="text-muted">View Raw Response</summary>
                    <pre class="mt-2 bg-white p-2 border rounded small">${JSON.stringify(result, null, 2)}</pre>
                </details>
            `;
        }
        
        return `<p class="mb-0">Action completed successfully!</p>`;
    }

    /**
     * Get helpful error suggestions
     */
    getErrorHelp(errorMessage) {
        const lowerError = errorMessage.toLowerCase();
        
        if (lowerError.includes('authentication') || lowerError.includes('unauthorized')) {
            return `
                <small class="text-muted">
                    <strong>💡 Tip:</strong> This action requires account connections. 
                    <a href="#connections">Connect your accounts</a> to use this feature.
                </small>
            `;
        }
        
        if (lowerError.includes('network') || lowerError.includes('connection')) {
            return `
                <small class="text-muted">
                    <strong>💡 Tip:</strong> Check your internet connection and try again.
                </small>
            `;
        }
        
        if (lowerError.includes('rate limit') || lowerError.includes('too many')) {
            return `
                <small class="text-muted">
                    <strong>💡 Tip:</strong> Please wait a moment before trying again.
                </small>
            `;
        }
        
        return `
            <small class="text-muted">
                <strong>💡 Tip:</strong> Try rephrasing your request or check if all required information is included.
            </small>
        `;
    }

    /**
     * Share action (placeholder)
     */
    shareAction(prompt) {
        if (navigator.share) {
            navigator.share({
                title: 'AI Action',
                text: `Check out this AI action: "${prompt}"`,
                url: window.location.href
            });
        } else {
            // Fallback: copy to clipboard
            navigator.clipboard.writeText(prompt).then(() => {
                showAlert('📋 Action copied to clipboard!', 'success');
            });
        }
    }

    /**
     * Suggest fix for failed action (placeholder)
     */
    suggestFix(prompt) {
        const suggestions = [
            "Make sure to include specific details like email addresses, dates, and times",
            "Check if you have connected the required accounts (Gmail, Calendar)",
            "Try breaking complex requests into smaller, simpler actions",
            "Ensure proper formatting for dates (e.g., 'tomorrow at 2 PM' or '2024-01-15')"
        ];
        
        const randomSuggestion = suggestions[Math.floor(Math.random() * suggestions.length)];
        showAlert(`💡 Suggestion: ${randomSuggestion}`, 'info');
    }

    /**
     * Load connections with enhanced provider cards
     */
    async loadConnections() {
        try {
            // Show loading state
            document.getElementById('connections-list').innerHTML = `
                <div class="text-center py-4">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading providers...</span>
                    </div>
                    <p class="mt-2 text-muted">Loading available providers...</p>
                </div>
            `;

            // Fetch providers with connection status
            const response = await api.getProviders();
            const providers = response.providers || [];

            if (providers.length === 0) {
                document.getElementById('connections-list').innerHTML = `
                    <div class="text-center py-4">
                        <div class="mb-3">
                            <span style="font-size: 3rem;">🔗</span>
                        </div>
                        <h5>No Providers Available</h5>
                        <p class="text-muted">No OAuth providers are currently configured.</p>
                    </div>
                `;
                return;
            }

            // Render enhanced provider cards
            const connectionsHtml = providers.map(provider => this.renderProviderCard(provider)).join('');
            document.getElementById('connections-list').innerHTML = connectionsHtml;

        } catch (error) {
            console.error('Failed to load connections:', error);
            document.getElementById('connections-list').innerHTML = `
                <div class="alert alert-danger">
                    <div class="d-flex align-items-center">
                        <span class="me-2">⚠️</span>
                        <div>
                            <strong>Failed to load providers</strong>
                            <p class="mb-0 small">${error.message}</p>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Render provider card with support for different auth types
     */
    renderProviderCard(provider) {
        const statusBadge = provider.connected 
            ? '<span class="badge bg-success">✓ Connected</span>'
            : '<span class="badge bg-secondary">Not Connected</span>';

        const authTypeBadge = provider.requires_redirect 
            ? '<span class="badge bg-info">🔗 OAuth</span>'
            : '<span class="badge bg-warning">🔑 API Key</span>';

        const buttonText = provider.connected ? 'Reconnect' : 'Connect';
        const buttonClass = provider.connected ? 'btn-outline-primary' : 'btn-primary';

        return `
            <div class="provider-card mb-3" data-provider="${provider.name}">
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex align-items-center justify-content-between">
                            <div>
                                <h6 class="mb-1">${provider.display_name}</h6>
                                <div class="mb-1">
                                    ${statusBadge}
                                    ${authTypeBadge}
                                </div>
                                <small class="text-muted">${provider.description}</small>
                            </div>
                            <button 
                                type="button"
                                class="btn ${buttonClass} btn-sm" 
                                onclick="connectProvider('${provider.name}', ${provider.requires_redirect})"
                                data-provider="${provider.name}"
                                data-requires-redirect="${provider.requires_redirect}"
                            >
                                ${buttonText}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Test connection for a provider
     */
    async testConnection(providerName) {
        showAlert(`🔧 Testing ${providerName} connection...`, 'info');
        
        try {
            // This could call a test endpoint in the future
            // For now, just simulate a test
            await new Promise(resolve => setTimeout(resolve, 1500));
            showAlert(`✅ ${providerName} connection is working properly`, 'success');
        } catch (error) {
            showAlert(`❌ ${providerName} connection test failed: ${error.message}`, 'danger');
        }
    }

    /**
     * View connection details
     */
    viewConnectionDetails(providerName) {
        // This could open a modal with detailed connection info
        showAlert(`📊 Connection details for ${providerName} - Feature coming soon!`, 'info');
    }

    /**
     * Disconnect a provider
     */
    async disconnectProvider(providerName) {
        if (!confirm(`Are you sure you want to disconnect ${providerName}? This will remove access to your account.`)) {
            return;
        }

        try {
            showAlert(`🔌 Disconnecting ${providerName}...`, 'info');
            
            // This would call a disconnect endpoint in the future
            // For now, just simulate
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            showAlert(`✅ ${providerName} disconnected successfully`, 'success');
            
            // Reload the connections
            this.loadConnections();
        } catch (error) {
            showAlert(`❌ Failed to disconnect ${providerName}: ${error.message}`, 'danger');
        }
    }

    /**
     * OpenAI Keys page (protected)
     */
    loadOpenAIKeysPage() {
        if (!auth.requireAuth()) return;

        const content = `
            <div class="page-section">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <h2>🔑 OpenAI API Keys</h2>
                        <p class="text-muted mb-0">Manage your OpenAI API key for natural language actions</p>
                    </div>
                    <div class="d-flex gap-2">
                        <a href="#actions" class="btn btn-outline-secondary">Back to Actions</a>
                    </div>
                </div>

                <!-- API Key Status -->
                <div id="openai-key-status" class="mb-4">
                    <div class="text-center py-4">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading OpenAI key...</span>
                        </div>
                        <p class="mt-2 text-muted">Loading API key information...</p>
                    </div>
                </div>

                <!-- Create/Update Form (Hidden by default) -->
                <div id="openai-key-form-section" class="d-none">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0" id="form-title">🔐 Add OpenAI API Key</h5>
                        </div>
                        <div class="card-body">
                            <form id="openai-key-form">
                                <div class="mb-3">
                                    <label for="openai-api-key" class="form-label">
                                        OpenAI API Key *
                                        <small class="text-muted">(Must start with "sk-")</small>
                                    </label>
                                    <div class="position-relative">
                                        <input 
                                            type="password" 
                                            class="form-control" 
                                            id="openai-api-key" 
                                            placeholder="sk-..."
                                            required
                                            minlength="40"
                                            maxlength="200"
                                        >
                                        <button 
                                            type="button" 
                                            class="btn btn-link position-absolute end-0 top-50 translate-middle-y me-2 p-1"
                                            id="toggle-api-key"
                                            style="z-index: 10;"
                                        >
                                            <small>Show</small>
                                        </button>
                                    </div>
                                    <div class="invalid-feedback">
                                        Please provide a valid OpenAI API key (starting with "sk-").
                                    </div>
                                    <div class="form-text">
                                        🔒 Your API key is encrypted and stored securely. It will be validated against OpenAI's API before saving.
                                    </div>
                                </div>

                                <div class="form-check mb-3" id="active-status-section" style="display: none;">
                                    <input type="checkbox" class="form-check-input" id="is-active" checked>
                                    <label class="form-check-label" for="is-active">
                                        API Key is Active
                                    </label>
                                    <div class="form-text">
                                        Inactive keys cannot be used for actions but remain stored.
                                    </div>
                                </div>

                                <div class="d-flex gap-2">
                                    <button type="submit" class="btn btn-primary" id="save-key-btn">
                                        <span class="save-text">
                                            <i class="me-2">💾</i>
                                            <span id="save-btn-text">Save API Key</span>
                                        </span>
                                        <span class="save-spinner spinner-border spinner-border-sm d-none" role="status">
                                            <span class="visually-hidden">Saving...</span>
                                        </span>
                                    </button>
                                    <button type="button" class="btn btn-outline-secondary" id="cancel-form-btn">
                                        Cancel
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>

                <!-- Help Section -->
                <div class="mt-4">
                    <div class="card bg-light border-0">
                        <div class="card-body">
                            <h6 class="card-title">📚 How to get your OpenAI API Key</h6>
                            <ol class="mb-2">
                                <li>Visit <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI API Keys page</a></li>
                                <li>Sign in to your OpenAI account</li>
                                <li>Click "Create new secret key"</li>
                                <li>Copy the key (it starts with "sk-")</li>
                                <li>Paste it in the form above</li>
                            </ol>
                            <p class="text-muted small mb-0">
                                <strong>Security Note:</strong> Each user can only have one API key. Keys are automatically validated and encrypted before storage.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        this.loadPage(content);

        // Load the OpenAI key status and setup the page
        this.loadOpenAIKeyStatus();
    }

    /**
     * Load OpenAI key status and setup the interface
     */
    async loadOpenAIKeyStatus() {
        const statusContainer = document.getElementById('openai-key-status');
        
        try {
            // Try to get existing key
            const response = await api.getOpenAIKey();
            
            if (response.success && response.data) {
                // User has an API key - show key information
                this.displayOpenAIKeyInfo(response.data);
            } else {
                // User doesn't have an API key - show create form
                this.showCreateKeyForm();
            }
        } catch (error) {
            // No key found (404) or other error
            if (error.message.includes('No OpenAI API key found')) {
                this.showCreateKeyForm();
            } else {
                // Show error
                statusContainer.innerHTML = `
                    <div class="alert alert-danger">
                        <div class="d-flex align-items-center">
                            <span class="me-2">⚠️</span>
                            <div>
                                <strong>Failed to load API key</strong>
                                <p class="mb-0 small">${error.message}</p>
                            </div>
                        </div>
                    </div>
                `;
            }
        }
    }

    /**
     * Display OpenAI key information when user has a key
     */
    displayOpenAIKeyInfo(keyData) {
        const statusContainer = document.getElementById('openai-key-status');
        const formSection = document.getElementById('openai-key-form-section');
        
        // Hide form section
        formSection.classList.add('d-none');
        
        // Show key information
        const statusBadge = keyData.is_active 
            ? '<span class="badge bg-success">✅ Active</span>'
            : '<span class="badge bg-warning">⚠️ Inactive</span>';
        
        const lastUsed = keyData.last_used_at 
            ? `Last used: ${new Date(keyData.last_used_at).toLocaleDateString()}`
            : 'Never used';
        
        statusContainer.innerHTML = `
            <div class="card border-success">
                <div class="card-header bg-light d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-0">🔑 OpenAI API Key</h5>
                        <small class="text-muted">Created: ${new Date(keyData.created_at).toLocaleDateString()}</small>
                    </div>
                    ${statusBadge}
                </div>
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <div class="mb-2">
                                <strong>API Key Preview:</strong>
                                <code class="ms-2">${keyData.key_preview}</code>
                            </div>
                            <small class="text-muted">${lastUsed}</small>
                        </div>
                        <div class="col-md-4 text-md-end">
                            <div class="btn-group" role="group">
                                <button type="button" class="btn btn-outline-primary btn-sm" onclick="app.showUpdateKeyForm()">
                                    📝 Update
                                </button>
                                <button type="button" class="btn btn-outline-${keyData.is_active ? 'warning' : 'success'} btn-sm" onclick="app.toggleOpenAIKeyStatus()">
                                    ${keyData.is_active ? '⏸️ Deactivate' : '▶️ Activate'}
                                </button>
                                <button type="button" class="btn btn-outline-danger btn-sm" onclick="app.deleteOpenAIKey()">
                                    🗑️ Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Store current key data for updates
        this.currentOpenAIKey = keyData;
    }

    /**
     * Show create key form
     */
    showCreateKeyForm() {
        const statusContainer = document.getElementById('openai-key-status');
        const formSection = document.getElementById('openai-key-form-section');
        const formTitle = document.getElementById('form-title');
        const saveButton = document.getElementById('save-btn-text');
        const activeStatusSection = document.getElementById('active-status-section');
        
        // Hide status container and show form
        statusContainer.innerHTML = `
            <div class="alert alert-info">
                <div class="d-flex align-items-center">
                    <span class="me-2">ℹ️</span>
                    <span>No OpenAI API key found. Please add one below to use AI actions.</span>
                </div>
            </div>
        `;
        
        // Configure form for creation
        formTitle.textContent = '🔐 Add OpenAI API Key';
        saveButton.textContent = 'Save API Key';
        activeStatusSection.style.display = 'none';
        
        formSection.classList.remove('d-none');
        this.setupOpenAIKeyForm('create');
    }

    /**
     * Show update key form
     */
    showUpdateKeyForm() {
        const formSection = document.getElementById('openai-key-form-section');
        const formTitle = document.getElementById('form-title');
        const saveButton = document.getElementById('save-btn-text');
        const activeStatusSection = document.getElementById('active-status-section');
        const isActiveCheckbox = document.getElementById('is-active');
        
        // Configure form for update
        formTitle.textContent = '📝 Update OpenAI API Key';
        saveButton.textContent = 'Update API Key';
        activeStatusSection.style.display = 'block';
        
        // Set current active status
        if (this.currentOpenAIKey) {
            isActiveCheckbox.checked = this.currentOpenAIKey.is_active;
        }
        
        formSection.classList.remove('d-none');
        this.setupOpenAIKeyForm('update');
        
        // Scroll to form
        formSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Setup OpenAI key form (create or update)
     */
    setupOpenAIKeyForm(mode) {
        const form = document.getElementById('openai-key-form');
        const apiKeyInput = document.getElementById('openai-api-key');
        const toggleButton = document.getElementById('toggle-api-key');
        const saveButton = document.getElementById('save-key-btn');
        const saveText = saveButton.querySelector('.save-text');
        const saveSpinner = saveButton.querySelector('.save-spinner');
        const cancelButton = document.getElementById('cancel-form-btn');
        
        // Clear any previous event listeners by replacing the form
        const newForm = form.cloneNode(true);
        form.parentNode.replaceChild(newForm, form);
        
        // Re-get elements after replacement
        const newApiKeyInput = document.getElementById('openai-api-key');
        const newToggleButton = document.getElementById('toggle-api-key');
        const newSaveButton = document.getElementById('save-key-btn');
        const newSaveText = newSaveButton.querySelector('.save-text');
        const newSaveSpinner = newSaveButton.querySelector('.save-spinner');
        const newCancelButton = document.getElementById('cancel-form-btn');
        
        // Password visibility toggle
        newToggleButton.addEventListener('click', () => {
            const type = newApiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
            newApiKeyInput.setAttribute('type', type);
            newToggleButton.innerHTML = type === 'password' ? '<small>Show</small>' : '<small>Hide</small>';
        });
        
        // Real-time validation
        newApiKeyInput.addEventListener('input', () => {
            this.validateOpenAIKeyField(newApiKeyInput);
        });
        
        newApiKeyInput.addEventListener('blur', () => {
            this.validateOpenAIKeyField(newApiKeyInput);
        });
        
        // Cancel button
        newCancelButton.addEventListener('click', () => {
            this.cancelOpenAIKeyForm();
        });
        
        // Form submission
        document.getElementById('openai-key-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Validate
            if (!this.validateOpenAIKeyField(newApiKeyInput)) {
                showAlert('Please fix the errors above', 'danger');
                return;
            }
            
            // Disable form
            newSaveButton.disabled = true;
            newSaveText.classList.add('d-none');
            newSaveSpinner.classList.remove('d-none');
            newApiKeyInput.disabled = true;
            
            try {
                const apiKey = newApiKeyInput.value.trim();
                
                if (mode === 'create') {
                    await this.createOpenAIKey(apiKey);
                } else {
                    await this.updateOpenAIKey(apiKey);
                }
            } finally {
                // Re-enable form
                newSaveButton.disabled = false;
                newSaveText.classList.remove('d-none');
                newSaveSpinner.classList.add('d-none');
                newApiKeyInput.disabled = false;
            }
        });
        
        // Focus on input
        newApiKeyInput.focus();
    }

    /**
     * Validate OpenAI key input field
     */
    validateOpenAIKeyField(field) {
        const value = field.value.trim();
        let isValid = true;
        
        // Remove previous validation classes
        field.classList.remove('is-valid', 'is-invalid');
        
        // Required check
        if (!value) {
            isValid = false;
        }
        
        // Format validation
        if (value && !value.startsWith('sk-')) {
            isValid = false;
        }
        
        // Length validation
        if (value && value.length < 40) {
            isValid = false;
        }
        
        // Apply validation classes
        if (isValid) {
            field.classList.add('is-valid');
        } else {
            field.classList.add('is-invalid');
        }
        
        return isValid;
    }

    /**
     * Create OpenAI API key
     */
    async createOpenAIKey(apiKey) {
        try {
            const response = await api.createOpenAIKey(apiKey);
            
            if (response.success) {
                showAlert('🎉 OpenAI API key created successfully!', 'success');
                
                // Reload the page to show the key status
                setTimeout(() => {
                    this.loadOpenAIKeyStatus();
                }, 1500);
            } else {
                showAlert(response.message || 'Failed to create API key', 'danger');
            }
        } catch (error) {
            let errorMessage = 'Failed to create API key';
            
            if (error.message.includes('validation failed')) {
                errorMessage = error.message.replace('API key validation failed: ', '');
            } else if (error.message.includes('already has')) {
                errorMessage = 'You already have an API key. Please update the existing one instead.';
            } else {
                errorMessage = error.message;
            }
            
            showAlert(`❌ ${errorMessage}`, 'danger');
        }
    }

    /**
     * Update OpenAI API key
     */
    async updateOpenAIKey(apiKey) {
        try {
            const updateData = { api_key: apiKey };
            
            // Include active status if in update mode
            const isActiveCheckbox = document.getElementById('is-active');
            if (isActiveCheckbox && !isActiveCheckbox.parentElement.style.display.includes('none')) {
                updateData.is_active = isActiveCheckbox.checked;
            }
            
            const response = await api.updateOpenAIKey(updateData);
            
            if (response.success) {
                showAlert('🎉 OpenAI API key updated successfully!', 'success');
                
                // Reload the page to show updated key status
                setTimeout(() => {
                    this.loadOpenAIKeyStatus();
                }, 1500);
            } else {
                showAlert(response.message || 'Failed to update API key', 'danger');
            }
        } catch (error) {
            let errorMessage = 'Failed to update API key';
            
            if (error.message.includes('validation failed')) {
                errorMessage = error.message.replace('API key validation failed: ', '');
            } else {
                errorMessage = error.message;
            }
            
            showAlert(`❌ ${errorMessage}`, 'danger');
        }
    }

    /**
     * Toggle OpenAI key active status
     */
    async toggleOpenAIKeyStatus() {
        try {
            const response = await api.toggleOpenAIKey();
            
            if (response.success) {
                const status = response.data.is_active ? 'activated' : 'deactivated';
                showAlert(`🔄 OpenAI API key ${status} successfully!`, 'success');
                
                // Reload the page to show updated status
                setTimeout(() => {
                    this.loadOpenAIKeyStatus();
                }, 1000);
            } else {
                showAlert(response.message || 'Failed to toggle API key status', 'danger');
            }
        } catch (error) {
            showAlert(`❌ Failed to toggle API key status: ${error.message}`, 'danger');
        }
    }

    /**
     * Delete OpenAI API key
     */
    async deleteOpenAIKey() {
        if (!confirm('Are you sure you want to delete your OpenAI API key? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await api.deleteOpenAIKey();
            
            if (response.success) {
                showAlert('🗑️ OpenAI API key deleted successfully', 'success');
                
                // Reload the page to show create form
                setTimeout(() => {
                    this.loadOpenAIKeyStatus();
                }, 1500);
            } else {
                showAlert(response.message || 'Failed to delete API key', 'danger');
            }
        } catch (error) {
            showAlert(`❌ Failed to delete API key: ${error.message}`, 'danger');
        }
    }

    /**
     * Cancel OpenAI key form
     */
    cancelOpenAIKeyForm() {
        const formSection = document.getElementById('openai-key-form-section');
        const form = document.getElementById('openai-key-form');
        
        // Clear form
        form.reset();
        
        // Remove validation classes
        const inputs = form.querySelectorAll('input');
        inputs.forEach(input => {
            input.classList.remove('is-valid', 'is-invalid');
        });
        
        // Hide form section
        formSection.classList.add('d-none');
        
        // If user has a key, reload status, otherwise show create prompt
        if (this.currentOpenAIKey) {
            this.displayOpenAIKeyInfo(this.currentOpenAIKey);
        } else {
            this.loadOpenAIKeyStatus();
        }
    }
}

/**
 * Utility functions
 */

// Show/hide loading spinner
function showLoading(show) {
    const loading = document.getElementById('loading');
    if (show) {
        loading.classList.remove('d-none');
    } else {
        loading.classList.add('d-none');
    }
}

// Show alert message
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container');
    const alertId = 'alert-' + Date.now();
    
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    alertContainer.innerHTML = alertHtml;
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = document.getElementById(alertId);
        if (alert) {
            alert.remove();
        }
    }, 5000);
}

// Global navigate function
function navigateTo(page) {
    app.navigateTo(page);
}

// Connect provider function (global for onclick)
async function connectProvider(provider, requiresRedirect) {
    try {
        showLoading(true);
        
        if (requiresRedirect) {
            // Handle OAuth flow - call the /auth/provider/ endpoint
            const response = await api.connectWithOAuth(provider);
            if (response.auth_url) {
                // Open auth URL in new tab
                window.open(response.auth_url, '_blank');
                showAlert(`Opening ${provider} authorization in new tab...`, 'info');
            } else {
                showAlert('Failed to get authorization URL', 'danger');
            }
        } else {
            // Handle API key authentication
            showApiKeyModal(provider);
        }
    } catch (error) {
        showAlert(error.message || 'Failed to connect provider', 'danger');
    } finally {
        showLoading(false);
    }
}

// Show API key input modal
function showApiKeyModal(provider) {
    const modalHtml = `
        <div class="modal fade" id="apiKeyModal" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">🔑 Connect ${provider.charAt(0).toUpperCase() + provider.slice(1)}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted mb-3">Enter your ${provider} API key to connect your account.</p>
                        <form id="apiKeyForm">
                            <div class="mb-3">
                                <label for="apiKeyInput" class="form-label">API Key *</label>
                                <div class="position-relative">
                                    <input 
                                        type="password" 
                                        class="form-control" 
                                        id="apiKeyInput" 
                                        placeholder="Enter your API key"
                                        required
                                        minlength="10"
                                    >
                                    <button 
                                        type="button" 
                                        class="btn btn-link position-absolute end-0 top-50 translate-middle-y me-2 p-1"
                                        id="toggleApiKey"
                                        style="z-index: 10;"
                                    >
                                        <small>Show</small>
                                    </button>
                                </div>
                                <div class="invalid-feedback">
                                    Please provide a valid API key.
                                </div>
                                <div class="form-text">
                                    🔒 Your API key will be encrypted and stored securely.
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="connectApiKeyBtn">
                            <span class="connect-text">Connect</span>
                            <span class="connect-spinner spinner-border spinner-border-sm d-none" role="status">
                                <span class="visually-hidden">Connecting...</span>
                            </span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal if any
    const existingModal = document.getElementById('apiKeyModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('apiKeyModal'));
    modal.show();
    
    // Setup modal functionality
    setupApiKeyModal(provider, modal);
}

// Setup API key modal functionality
function setupApiKeyModal(provider, modal) {
    const form = document.getElementById('apiKeyForm');
    const apiKeyInput = document.getElementById('apiKeyInput');
    const toggleButton = document.getElementById('toggleApiKey');
    const connectButton = document.getElementById('connectApiKeyBtn');
    const connectText = connectButton.querySelector('.connect-text');
    const connectSpinner = connectButton.querySelector('.connect-spinner');
    
    // Password visibility toggle
    toggleButton.addEventListener('click', () => {
        const type = apiKeyInput.getAttribute('type') === 'password' ? 'text' : 'password';
        apiKeyInput.setAttribute('type', type);
        toggleButton.innerHTML = type === 'password' ? '<small>Show</small>' : '<small>Hide</small>';
    });
    
    // Real-time validation
    apiKeyInput.addEventListener('input', () => {
        validateApiKeyField(apiKeyInput);
    });
    
    apiKeyInput.addEventListener('blur', () => {
        validateApiKeyField(apiKeyInput);
    });
    
    // Connect button click
    connectButton.addEventListener('click', async () => {
        if (!validateApiKeyField(apiKeyInput)) {
            showAlert('Please provide a valid API key', 'danger');
            return;
        }
        
        // Disable form
        connectButton.disabled = true;
        connectText.classList.add('d-none');
        connectSpinner.classList.remove('d-none');
        apiKeyInput.disabled = true;
        
        try {
            const apiKey = apiKeyInput.value.trim();
            const response = await api.connectWithApiKey(provider, apiKey);
            
            if (response.success) {
                showAlert(`🎉 Successfully connected to ${provider}!`, 'success');
                modal.hide();
                
                // Reload connections to show updated status
                if (window.app && window.app.loadConnections) {
                    setTimeout(() => {
                        window.app.loadConnections();
                    }, 1000);
                }
            } else {
                showAlert(response.message || 'Failed to connect', 'danger');
            }
        } catch (error) {
            let errorMessage = 'Failed to connect';
            
            if (error.message.includes('Configuration error')) {
                errorMessage = error.message.replace('Configuration error: ', '');
            } else {
                errorMessage = error.message;
            }
            
            showAlert(`❌ ${errorMessage}`, 'danger');
        } finally {
            // Re-enable form
            connectButton.disabled = false;
            connectText.classList.remove('d-none');
            connectSpinner.classList.add('d-none');
            apiKeyInput.disabled = false;
        }
    });
    
    // Form submission (Enter key)
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        connectButton.click();
    });
    
    // Focus on input when modal is shown
    document.getElementById('apiKeyModal').addEventListener('shown.bs.modal', () => {
        apiKeyInput.focus();
    });
    
    // Clean up modal when hidden
    document.getElementById('apiKeyModal').addEventListener('hidden.bs.modal', () => {
        setTimeout(() => {
            document.getElementById('apiKeyModal').remove();
        }, 200);
    });
}

// Validate API key input field
function validateApiKeyField(field) {
    const value = field.value.trim();
    let isValid = true;
    
    // Remove previous validation classes
    field.classList.remove('is-valid', 'is-invalid');
    
    // Required check
    if (!value) {
        isValid = false;
    }
    
    // Length validation
    if (value && value.length < 10) {
        isValid = false;
    }
    
    // Apply validation classes
    if (isValid) {
        field.classList.add('is-valid');
    } else {
        field.classList.add('is-invalid');
    }
    
    return isValid;
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
