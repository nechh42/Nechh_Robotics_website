// Tawk.to Live Chat Widget — Nechh Robotics
// Kurulum:
// 1. https://www.tawk.to → Ücretsiz hesap aç
// 2. Dashboard → Settings → Chat Widget → Widget Code kopyala
// 3. Aşağıdaki YOUR_TAWK_PROPERTY_ID ve YOUR_TAWK_WIDGET_ID değerlerini değiştir
//    (örnek: s1xxxxxxxx/default)
//
// Şu an placeholder aktif — gerçek ID eklendiğinde chat aktif olacak.

(function(){
  var TAWK_PROPERTY_ID = 'YOUR_TAWK_PROPERTY_ID'; // tawk.to'dan al
  var TAWK_WIDGET_ID   = 'YOUR_TAWK_WIDGET_ID';   // tawk.to'dan al

  if (TAWK_PROPERTY_ID === 'YOUR_TAWK_PROPERTY_ID') {
    // Gerçek ID girilmeden chatbot gösterilmez
    return;
  }

  var s1 = document.createElement("script");
  var s0 = document.getElementsByTagName("script")[0];
  s1.async = true;
  s1.src = 'https://embed.tawk.to/' + TAWK_PROPERTY_ID + '/' + TAWK_WIDGET_ID;
  s1.charset = 'UTF-8';
  s1.setAttribute('crossorigin', '*');
  s0.parentNode.insertBefore(s1, s0);
})();
