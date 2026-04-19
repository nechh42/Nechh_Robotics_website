// assets/js/registration-simple.js
import { supabase } from './supabase-config.js'

document.addEventListener('DOMContentLoaded', function() {
    const regForm = document.getElementById('registration-form')
    
    if (regForm) {
        regForm.addEventListener('submit', async function(e) {
            e.preventDefault()
            
            // Form verilerini al
            const telegram = document.getElementById('telegram-username').value.trim()
            const email = document.getElementById('email').value.trim()
            const age = parseInt(document.getElementById('age').value)
            
            // Validasyon
            if (age < 18) {
                alert('18 yaþýndan büyük olmalýsýnýz')
                return
            }
            
            if (!telegram.startsWith('@')) {
                alert('Telegram kullanýcý adý @ ile baþlamalý')
                return
            }
            
            // Supabase'e kaydet
            try {
                const { data, error } = await supabase
                    .from('beta_users')
                    .insert([
                        {
                            telegram_username: telegram,
                            email: email,
                            age: age,
                            subscription_status: 'pending'
                        }
                    ])
                    .select()
                
                if (error) {
                    if (error.code === '23505') {
                        alert('Bu kullanýcý adý veya email zaten kayýtlý')
                    } else {
                        alert('Hata: ' + error.message)
                    }
                    return
                }
                
                // Baþarýlý - Ödeme sayfasýna yönlendir
                alert('Kayýt baþarýlý! Ödeme sayfasýna yönlendiriliyorsunuz.')
                window.location.href = 'https://nechh-robotics-website.vercel.app/subscription.html?user=' + encodeURIComponent(telegram)
                
            } catch (error) {
                console.error('Kayýt hatasý:', error)
                alert('Sistem hatasý, lütfen tekrar deneyin')
            }
        })
    }
})
