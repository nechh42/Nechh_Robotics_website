// Email Verification System
class EmailVerification {
    constructor() {
        this.emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        this.commonDomains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'protonmail.com'];
        this.tempEmailDomains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com', 'mailinator.com'];
        this.init();
    }
    
    init() {
        document.querySelectorAll('input[type="email"]').forEach(input => {
            this.setupEmailValidation(input);
        });
    }
    
    setupEmailValidation(input) {
        const parent = input.closest('div');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'hidden mt-2 text-sm';
        parent.appendChild(errorDiv);
        
        input.addEventListener('blur', (e) => {
            this.validateEmail(e.target.value, errorDiv);
        });
    }
    
    validateEmail(email, errorElement) {
        const cleanEmail = email.trim();
        
        // Clear previous state
        errorElement.classList.add('hidden');
        
        if (!cleanEmail) {
            return true; // Email is optional
        }
        
        // Basic format check
        if (!this.emailRegex.test(cleanEmail)) {
            this.showError(errorElement, 'Please enter a valid email address');
            return false;
        }
        
        // Check for temporary email
        const domain = cleanEmail.split('@')[1].toLowerCase();
        if (this.tempEmailDomains.includes(domain)) {
            this.showError(errorElement, 'Temporary email addresses are not allowed');
            return false;
        }
        
        // Check domain validity
        if (!this.isValidDomain(domain)) {
            this.showWarning(errorElement, 'Please use a permanent email address');
            return true; // Don't block, just warn
        }
        
        this.showSuccess(errorElement);
        return true;
    }
    
    isValidDomain(domain) {
        // Check if domain has valid MX records (simplified check)
        return this.commonDomains.includes(domain) || 
               domain.includes('.') || 
               domain.length > 4;
    }
    
    showError(element, message) {
        element.textContent = message;
        element.classList.remove('hidden', 'text-green-600', 'text-yellow-600');
        element.classList.add('text-red-600');
    }
    
    showWarning(element, message) {
        element.textContent = `⚠️ ${message}`;
        element.classList.remove('hidden', 'text-red-600', 'text-green-600');
        element.classList.add('text-yellow-600');
    }
    
    showSuccess(element) {
        element.textContent = '✓ Valid email address';
        element.classList.remove('hidden', 'text-red-600', 'text-yellow-600');
        element.classList.add('text-green-600');
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new EmailVerification();
});
