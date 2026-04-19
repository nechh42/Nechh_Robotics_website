// assets/js/registration.js
import { supabase } from './supabase-config.js'

document.addEventListener('DOMContentLoaded', function() {
  const registrationForm = document.getElementById('registration-form')
  
  if (registrationForm) {
    registrationForm.addEventListener('submit', async function(e) {
      e.preventDefault()
      
      const telegramUsername = document.getElementById('telegram-username').value.trim()
      const email = document.getElementById('email').value.trim()
      const age = parseInt(document.getElementById('age').value)
      
      // Ya� kontrol�
      if (age < 18) {
        alert('You must be at least 18 years old to register.')
        return
      }
      
      // Telegram username format kontrol�
      if (!telegramUsername.startsWith('@')) {
        alert('Telegram username must start with @')
        return
      }
      
      // Email format kontrol�
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailRegex.test(email)) {
        alert('Please enter a valid email address')
        return
      }
      
      try {
        // Supabase'e kullan�c� kaydet
        const { data, error } = await supabase
          .from('beta_users')
          .insert([
            {
              telegram_username: telegramUsername,
              email: email,
              age: age,
              subscription_status: 'pending'
            }
          ])
          .select()
        
        if (error) {
          if (error.code === '23505') { // Unique constraint violation
            alert('This username or email is already registered.')
          } else {
            throw error
          }
          return
        }
        
        alert('Your beta application has been received.\nThis is not an automatic approval.')
        
        // �deme sayfas�na y�nlendir
        window.location.href = '/subscription.html?user=' + encodeURIComponent(telegramUsername)
        
      } catch (error) {
        console.error('Registration error:', error)
        alert('Registration failed: ' + error.message)
      }
    })
  }
})
