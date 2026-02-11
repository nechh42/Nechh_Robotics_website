// Telegram Username Verification System
class TelegramVerification {
    constructor() {
        this.telegramRegex = /^@?[a-zA-Z][\w]{4,31}$/;
        this.minLength = 5;
        this.maxLength = 32;
        this.init();
    }
    
    init() {
        // Find all Telegram input fields
        document.querySelectorAll('input[placeholder*="telegram"], input[placeholder*="Telegram"], input[id*="telegram"]').forEach(input => {
            this.setupInputValidation(input);
        });
    }
    
    setupInputValidation(input) {
        const parent = input.closest('div');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'hidden mt-2 text-sm text-red-600';
        errorDiv.id = `${input.id || 'telegram'}_error`;
        parent.appendChild(errorDiv);
        
        // Real-time validation
        input.addEventListener('input', (e) => {
            this.validateTelegramUsername(e.target.value, errorDiv);
        });
        
        // On blur validation
        input.addEventListener('blur', (e) => {
            this.validateTelegramUsername(e.target.value, errorDiv);
        });
    }
    
    validateTelegramUsername(username, errorElement) {
        const cleanUsername = username.trim().replace('@', '');
        
        // Clear previous error
        errorElement.classList.add('hidden');
        
        // Check if empty
        if (!cleanUsername) {
            this.showError(errorElement, 'Telegram username is required');
            return false;
        }
        
        // Check length
        if (cleanUsername.length < this.minLength) {
            this.showError(errorElement, `Username must be at least ${this.minLength} characters`);
            return false;
        }
        
        if (cleanUsername.length > this.maxLength) {
            this.showError(errorElement, `Username cannot exceed ${this.maxLength} characters`);
            return false;
        }
        
        // Check format
        if (!this.telegramRegex.test('@' + cleanUsername)) {
            this.showError(errorElement, 'Invalid Telegram username format');
            return false;
        }
        
        // Check for common fake usernames
        if (this.isFakeUsername(cleanUsername)) {
            this.showError(errorElement, 'Please provide a valid Telegram username');
            return false;
        }
        
        // If valid, show success
        this.showSuccess(errorElement);
        return true;
    }
    
    isFakeUsername(username) {
        const fakePatterns = [
            'test', 'demo', 'admin', 'user', 'username',
            '123456', 'abcdef', 'qwerty', 'asdfgh'
        ];
        
        const lowerUsername = username.toLowerCase();
        return fakePatterns.some(pattern => lowerUsername.includes(pattern));
    }
    
    showError(element, message) {
        element.textContent = message;
        element.classList.remove('hidden', 'text-green-600');
        element.classList.add('text-red-600');
    }
    
    showSuccess(element) {
        element.textContent = '✓ Valid Telegram username';
        element.classList.remove('hidden', 'text-red-600');
        element.classList.add('text-green-600');
    }
    
    // API Check function (to be implemented with backend)
    async checkTelegramExistence(username) {
        try {
            // This would call your backend API
            const response = await fetch(`/api/check-telegram?username=${encodeURIComponent(username)}`);
            const data = await response.json();
            return data.exists;
        } catch (error) {
            console.error('Telegram check failed:', error);
            return null; // Don't block if API fails
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new TelegramVerification();
});
