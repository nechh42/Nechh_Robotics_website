// api/email/send.js
export default async function handler(req, res) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }
    
    try {
        const { to, subject, type, data } = req.body;
        
        // Email þablonlarý
        const templates = {
            welcome: {
                subject: ' Nechh Robotics Beta Programýna Hoþgeldiniz!',
                html: \
                    <h1>Hoþgeldiniz!</h1>
                    <p>Beta programýna kaydoldunuz.</p>
                    <p><strong>Telegram:</strong> \</p>
                    <p><strong>Abonelik:</strong> 30 gün ücretsiz</p>
                    <p>Ödeme yapmak için: <a href="\">Týklayýn</a></p>
                \
            },
            payment_success: {
                subject: ' Ödemeniz Onaylandý!',
                html: \
                    <h1>Ödeme Baþarýlý!</h1>
                    <p>Aboneliðiniz aktif edildi.</p>
                    <p><strong>Transaction ID:</strong> \</p>
                    <p>Telegram grubuna otomatik eklendiniz.</p>
                \
            },
            reminder: {
                subject: ' Abonelik Yenileme Hatýrlatmasý',
                html: \
                    <h1>Aboneliðiniz Bitmek Üzere!</h1>
                    <p>5 gün sonra yenileniyor: \</p>
                    <p>Ýptal için: <a href="\">Týklayýn</a></p>
                \
            }
        };
        
        // Resend API ile gönder (ücretsiz 100 email/gün)
        const response = await fetch('https://api.resend.com/emails', {
            method: 'POST',
            headers: {
                'Authorization': \Bearer \\,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                from: 'Nechh Robotics <noreply@nechh-robotics.com>',
                to: to,
                subject: templates[type].subject,
                html: templates[type].html
            })
        });
        
        const result = await response.json();
        
        res.status(200).json({ 
            success: true, 
            message: 'Email sent',
            emailId: result.id 
        });
        
    } catch (error) {
        console.error('Email automation error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
}
