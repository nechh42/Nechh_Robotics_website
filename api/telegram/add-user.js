// api/telegram/add-user.js
export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }
    
    try {
        const { telegramUsername, userId, paymentTxId } = req.body;
        
        // 1. Kullanýcýyý Telegram grubuna ekle
        const botToken = process.env.TELEGRAM_BOT_TOKEN;
        const chatId = process.env.TELEGRAM_CHAT_ID;
        
        // Hoþgeldin mesajý gönder
        const welcomeMsg = await fetch(\https://api.telegram.org/bot\/sendMessage\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: telegramUsername.replace('@', ''),
                text: \ Hoþgeldin! Beta programýna kaydoldunuz.\n\n +
                      \ Ödeme Onaylandý: \\n +
                      \ Abonelik: 30 gün ücretsiz\n +
                      \ Grup Linki: https://t.me/+xxxxxxxxxx\n\n +
                      \Kurallar:\n1. Sinyalleri paylaþma\n2. Saygýlý ol\n3. Spam yapma\
            })
        });
        
        // 2. Admin grubuna bildirim gönder
        await fetch(\https://api.telegram.org/bot\/sendMessage\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chat_id: chatId,
                text: \ Yeni Üye Eklendi\n\n +
                      \: \\n +
                      \: \\n +
                      \ TX: \\n +
                      \: \\
            })
        });
        
        res.status(200).json({ 
            success: true, 
            message: 'User added to Telegram group',
            telegramUsername 
        });
        
    } catch (error) {
        console.error('Telegram automation error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
}
