// api/payment/verify.js
export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }
    
    try {
        const { txId, userId, telegramUsername } = req.body;
        
        // Basit TX doðrulama (gerçekte blockchain API kullan)
        const isValidTx = txId && txId.length >= 10;
        
        if (!isValidTx) {
            return res.status(400).json({ error: 'Invalid transaction ID' });
        }
        
        // Supabase'de güncelle
        const supabaseUrl = process.env.SUPABASE_URL;
        const supabaseKey = process.env.SUPABASE_SERVICE_KEY;
        
        const updateResponse = await fetch(\\/rest/v1/beta_users?id=eq.\\, {
            method: 'PATCH',
            headers: {
                'apikey': supabaseKey,
                'Authorization': \Bearer \\,
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            },
            body: JSON.stringify({
                payment_tx_id: txId,
                subscription_status: 'active',
                last_payment_at: new Date().toISOString()
            })
        });
        
        // Telegram'a ekle
        await fetch(\\/api/telegram/add-user\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                telegramUsername,
                userId,
                paymentTxId: txId
            })
        });
        
        // Email gönder
        await fetch(\\/api/email/send\, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                to: data.email,
                type: 'payment_success',
                data: { txId }
            })
        });
        
        res.status(200).json({ 
            success: true, 
            message: 'Payment verified and user activated',
            userId,
            telegramUsername 
        });
        
    } catch (error) {
        console.error('Payment automation error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
}
