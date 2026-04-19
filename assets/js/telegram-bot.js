// assets/js/telegram-bot.js
async function addToTelegramGroup(telegramUsername, txId) {
    // Bu fonksiyon ödeme onaylandýðýnda çalýþacak
    
    // 1. Önce Supabase'de durumu güncelle
    try {
        const { supabase } = await import('./supabase-config.js')
        
        const { error } = await supabase
            .from('beta_users')
            .update({
                subscription_status: 'active',
                payment_tx_id: txId,
                last_payment_at: new Date().toISOString()
            })
            .eq('telegram_username', telegramUsername)
        
        if (error) throw error
        
        // 2. Telegram botuna bildirim gönder (direkt API)
        const botToken = '7977276479:AAH8Wtd6uz0hpU0SGqd8Z_IFCwv8JtY-OYo'
        const chatId = '-1001946548231'
        
        // Admin bildirimi
        await fetch(\https://api.telegram.org/bot\/sendMessage\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatId,
                text: \ Yeni Ödeme\nKullanýcý: \\nTX: \\nTarih: \\
            })
        })
        
        // Kullanýcýya hoþgeldin mesajý
        await fetch(\https://api.telegram.org/bot\/sendMessage\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: telegramUsername.replace('@', ''),
                text: \ Hoþgeldin! Ödemeniz onaylandý.\n\n +
                      \ TX ID: \\n +
                      \ Abonelik: 30 gün ücretsiz\n +
                      \ Telegram grubuna eklendiniz!\n +
                      \ Grup: https://t.me/+xxxxxxxxxx\
            })
        })
        
        return { success: true, message: 'Kullanýcý aktif edildi ve Telegram\'a eklendi' }
        
    } catch (error) {
        console.error('Telegram ekleme hatasý:', error)
        return { success: false, message: error.message }
    }
}

// Ödeme sayfasýnda kullanmak için
window.addToTelegramGroup = addToTelegramGroup
