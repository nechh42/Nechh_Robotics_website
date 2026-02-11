// assets/js/payment-verification.js
import { supabase } from './supabase-config.js'

document.addEventListener('DOMContentLoaded', function() {
  const paymentForm = document.getElementById('payment-form')
  
  if (paymentForm) {
    paymentForm.addEventListener('submit', async function(e) {
      e.preventDefault()
      
      const txId = document.getElementById('transaction-id').value.trim()
      const urlParams = new URLSearchParams(window.location.search)
      const telegramUsername = urlParams.get('user')
      
      if (!telegramUsername) {
        alert('No user found. Please register first.')
        window.location.href = '/'
        return
      }
      
      // Transaction ID format kontrolü
      if (!txId || txId.length < 10) {
        alert('Please enter a valid transaction ID (minimum 10 characters)')
        return
      }
      
      try {
        // Supabase'de kullanýcýyý güncelle
        const { data, error } = await supabase
          .from('beta_users')
          .update({
            payment_tx_id: txId,
            subscription_status: 'active',
            last_payment_at: new Date().toISOString()
          })
          .eq('telegram_username', telegramUsername)
          .select()
        
        if (error) throw error
        
        if (data && data.length > 0) {
          // Telegram botuna bildirim gönder
          const botResponse = await fetch('https://api.telegram.org/bot7977276479:AAH8Wtd6uz0hpU0SGqd8Z_IFCwv8JtY-OYo/sendMessage', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              chat_id: '-1001946548231',
              text: ? New payment verified!\nUser: \nTX ID: \nStatus: Active
            })
          })
          
          alert('Payment verified successfully! Check your Telegram for group invite.')
          window.location.href = '/success.html'
        } else {
          alert('User not found. Please contact support.')
        }
        
      } catch (error) {
        console.error('Payment verification error:', error)
        alert('Payment verification failed: ' + error.message)
      }
    })
  }
})
