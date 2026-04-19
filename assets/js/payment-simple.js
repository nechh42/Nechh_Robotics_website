// assets/js/payment-simple.js
document.addEventListener('DOMContentLoaded', function() {
    const paymentForm = document.getElementById('payment-form')
    
    if (paymentForm) {
        paymentForm.addEventListener('submit', async function(e) {
            e.preventDefault()
            
            const txId = document.getElementById('transaction-id').value.trim()
            const urlParams = new URLSearchParams(window.location.search)
            const telegramUser = urlParams.get('user')
            
            if (!telegramUser) {
                alert('Kullanýcý bulunamadý. Lütfen önce kayýt olun.')
                window.location.href = 'https://nechh-robotics-website.vercel.app/'
                return
            }
            
            if (!txId || txId.length < 10) {
                alert('Geçerli bir Transaction ID girin (en az 10 karakter)')
                return
            }
            
            // Ödemeyi doðrula ve Telegram'a ekle
            try {
                const { addToTelegramGroup } = await import('./telegram-bot.js')
                const result = await addToTelegramGroup(telegramUser, txId)
                
                if (result.success) {
                    alert(' Ödeme onaylandý! Telegram grubuna eklendiniz.')
                    window.location.href = 'https://nechh-robotics-website.vercel.app/success.html'
                } else {
                    alert('Hata: ' + result.message)
                }
                
            } catch (error) {
                alert('Ödeme iþlemi sýrasýnda hata: ' + error.message)
            }
        })
    }
    
    // Crypto adreslerini göster
    showCryptoAddresses()
})

function showCryptoAddresses() {
    const addresses = {
        BTC: 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
        ETH: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e'
    }
    
    const container = document.getElementById('crypto-addresses')
    if (container) {
        container.innerHTML = \
            <div style="margin: 20px 0;">
                <h3> Crypto Adresleri:</h3>
                <p><strong>Bitcoin (BTC):</strong></p>
                <code style="background:#f8f9fa; padding:10px; display:block; margin:10px 0;">
                    \
                </code>
                <p><strong>Ethereum (ETH):</strong></p>
                <code style="background:#f8f9fa; padding:10px; display:block; margin:10px 0;">
                    \
                </code>
                <p><small>Ödeme yaptýktan sonra Transaction ID'yi yukarýdaki forma girin.</small></p>
            </div>
        \
    }
}
