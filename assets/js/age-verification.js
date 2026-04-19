// Age Verification - SADECE KAYIT SAYFASINDA
class AgeVerification {
    constructor() {
        // SADECE kayıt formu varsa çalış
        if (!document.getElementById('betaForm')) return;
        
        this.minAge = 18;
        this.init();
    }
    
    init() {
        const form = document.getElementById('betaForm');
        form.addEventListener('submit', (e) => {
            if (!this.verifyAge()) {
                e.preventDefault();
                this.showAgeModal();
            }
        });
    }
    
    verifyAge() {
        const stored = localStorage.getItem('nechh_age_verified');
        if (!stored) return false;
        
        try {
            const data = JSON.parse(stored);
            const age = new Date().getFullYear() - data.birthYear;
            return age >= this.minAge;
        } catch {
            return false;
        }
    }
    
    showAgeModal() {
        // Basit yaş doğrulama modal'ı
        const modal = document.createElement('div');
        modal.innerHTML = `
            <div style="position:fixed; inset:0; background:rgba(0,0,0,0.8); z-index:9999; display:flex; align-items:center; justify-content:center; padding:20px;">
                <div style="background:white; padding:30px; border-radius:15px; max-width:400px; width:100%;">
                    <h2 style="font-size:24px; font-weight:bold; margin-bottom:15px; color:#dc2626;">Age Verification Required</h2>
                    <p style="margin-bottom:20px; color:#4b5563;">You must be 18+ to register. Enter your birth year:</p>
                    <select id="birthYear" style="width:100%; padding:12px; border:2px solid #d1d5db; border-radius:8px; margin-bottom:20px;">
                        <option value="">Select Year</option>
                        ${this.generateYears()}
                    </select>
                    <div style="display:flex; gap:10px;">
                        <button id="confirmBtn" style="flex:1; background:#dc2626; color:white; padding:12px; border-radius:8px; font-weight:bold;">Confirm 18+</button>
                        <button id="cancelBtn" style="flex:1; background:#6b7280; color:white; padding:12px; border-radius:8px;">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        modal.querySelector('#confirmBtn').addEventListener('click', () => {
            const year = parseInt(modal.querySelector('#birthYear').value);
            if (year) {
                const age = new Date().getFullYear() - year;
                if (age >= 18) {
                    localStorage.setItem('nechh_age_verified', JSON.stringify({
                        birthYear: year,
                        verifiedAt: new Date().toISOString()
                    }));
                    modal.remove();
                    document.getElementById('betaForm').submit();
                } else {
                    alert(`You are ${age} years old. Must be 18+.`);
                }
            }
        });
        
        modal.querySelector('#cancelBtn').addEventListener('click', () => {
            modal.remove();
        });
    }
    
    generateYears() {
        let options = '';
        const currentYear = new Date().getFullYear();
        for (let year = currentYear; year >= currentYear - 100; year--) {
            options += `<option value="${year}">${year}</option>`;
        }
        return options;
    }
}

// Sadece kayıt sayfasında başlat
if (document.getElementById('betaForm')) {
    new AgeVerification();
}
