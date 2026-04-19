// Telegram AI Project - Beta Registration with Age Verification
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('betaForm');
    
    if (!form) return;
    
    // Check age verification before allowing form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // 1. First check age verification
        if (!checkAgeVerification()) {
            showAgeWarning();
            return;
        }
        
        // 2. Then process form
        await processBetaRequest(this);
    });
    
    function checkAgeVerification() {
        const storageKey = 'nechh_age_verified';
        const stored = localStorage.getItem(storageKey);
        
        if (!stored) return false;
        
        try {
            const data = JSON.parse(stored);
            const currentYear = new Date().getFullYear();
            const age = currentYear - data.birthYear;
            
            return age >= 18;
        } catch (e) {
            return false;
        }
    }
    
    function showAgeWarning() {
        const warningHTML = `
        <div class="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
            <div class="bg-white rounded-2xl max-w-md w-full p-8">
                <div class="text-center">
                    <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                        <i class="fas fa-exclamation-triangle text-red-600 text-2xl"></i>
                    </div>
                    <h3 class="text-xl font-bold mb-4">Age Verification Required</h3>
                    <p class="text-gray-600 mb-6">
                        Beta access requires age verification (18+).
                        Please refresh the page and verify your age first.
                    </p>
                    <button onclick="location.reload()" 
                            class="bg-red-600 hover:bg-red-700 text-white px-8 py-3 rounded-xl font-medium">
                        Verify Age
                    </button>
                </div>
            </div>
        </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', warningHTML);
    }
    
    async function processBetaRequest(form) {
        const telegramInput = form.querySelector('input[type="text"]');
        const agreementCheckbox = document.getElementById('licenseAgreement');
        const submitBtn = form.querySelector('button[type="submit"]');
        
        if (!telegramInput.value.trim()) {
            alert('Telegram username is required');
            return;
        }
        
        if (!agreementCheckbox.checked) {
            alert('You must agree to the license agreement');
            return;
        }
        
        // Get age verification data for logging
        const ageData = JSON.parse(localStorage.getItem('nechh_age_verified') || '{}');
        const userAge = new Date().getFullYear() - (ageData.birthYear || 0);
        
        // Original button text
        const originalText = submitBtn.textContent;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
        submitBtn.disabled = true;
        
        try {
            // Simulate API call with age data
            const userData = {
                telegram: telegramInput.value.trim().replace('@', ''),
                email: '', // Add if you have email field
                ageVerified: true,
                userAge: userAge,
                verifiedAt: ageData.verifiedAt,
                userAgent: navigator.userAgent
            };
            
            console.log('Beta request with age verification:', userData);
            
            // Simulate API delay
            await new Promise(resolve => setTimeout(resolve, 1500));
            
            // Show success
            alert('Beta access requested successfully. Age verification confirmed.');
            form.reset();
            
        } catch (error) {
            console.error('Error:', error);
            alert('Request failed. Please try again.');
        } finally {
            // Restore button
            submitBtn.textContent = originalText;
            submitBtn.disabled = false;
        }
    }
});
