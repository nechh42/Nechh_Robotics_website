// Basic Privacy-Friendly Analytics
class NechhAnalytics {
    constructor() {
        this.endpoint = 'https://your-backend.com/api/analytics'; // Change this
        this.sessionId = this.generateSessionId();
        this.pageStartTime = Date.now();
        this.init();
    }
    
    init() {
        // Track page view
        this.trackPageView();
        
        // Track form submissions
        this.trackForms();
        
        // Track outbound links
        this.trackOutboundLinks();
        
        // Track age verification events
        this.trackAgeVerification();
        
        // Send data on page unload
        window.addEventListener('beforeunload', () => {
            this.trackTimeOnPage();
        });
    }
    
    trackPageView() {
        const data = {
            type: 'pageview',
            url: window.location.pathname,
            referrer: document.referrer,
            sessionId: this.sessionId,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            screenResolution: `${window.screen.width}x${window.screen.height}`
        };
        
        this.sendToBackend(data);
    }
    
    trackForms() {
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', (e) => {
                const formData = new FormData(form);
                const formValues = {};
                
                formData.forEach((value, key) => {
                    if (key.includes('password')) return; // Don't track passwords
                    formValues[key] = value;
                });
                
                const data = {
                    type: 'form_submission',
                    formId: form.id || 'unknown',
                    values: formValues,
                    sessionId: this.sessionId,
                    timestamp: new Date().toISOString()
                };
                
                this.sendToBackend(data);
            });
        });
    }
    
    trackAgeVerification() {
        // Listen for age verification completion
        const originalSetItem = localStorage.setItem;
        localStorage.setItem = function(key, value) {
            originalSetItem.apply(this, arguments);
            
            if (key === 'nechh_age_verified') {
                const analytics = window.NechhAnalyticsInstance;
                if (analytics) {
                    const data = {
                        type: 'age_verification',
                        verified: true,
                        sessionId: analytics.sessionId,
                        timestamp: new Date().toISOString()
                    };
                    analytics.sendToBackend(data);
                }
            }
        };
    }
    
    trackOutboundLinks() {
        document.querySelectorAll('a[href^="http"]').forEach(link => {
            if (!link.href.includes(window.location.hostname)) {
                link.addEventListener('click', () => {
                    const data = {
                        type: 'outbound_click',
                        url: link.href,
                        sessionId: this.sessionId,
                        timestamp: new Date().toISOString()
                    };
                    this.sendToBackend(data);
                });
            }
        });
    }
    
    trackTimeOnPage() {
        const timeSpent = Date.now() - this.pageStartTime;
        const data = {
            type: 'time_on_page',
            timeSpent: timeSpent,
            url: window.location.pathname,
            sessionId: this.sessionId,
            timestamp: new Date().toISOString()
        };
        
        // Use sendBeacon for reliable delivery on page unload
        navigator.sendBeacon(this.endpoint, JSON.stringify(data));
    }
    
    sendToBackend(data) {
        // Use fetch with keepalive for reliability
        fetch(this.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            keepalive: true // Important for page unload events
        }).catch(err => console.error('Analytics error:', err));
    }
    
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
}

// Initialize analytics
document.addEventListener('DOMContentLoaded', () => {
    window.NechhAnalyticsInstance = new NechhAnalytics();
});
