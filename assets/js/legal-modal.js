// assets/js/legal-modal.js
// Adim adim yasal onay: Yas -> Yasal Uyari -> Risk Aciklamasi -> KVKK/Gizlilik
// Tum onaylar kaydedilir, eksikse site bloklanir

(function() {
  'use strict';

  const STORAGE_KEY = 'nechh_legal_v2';
  const MODAL_ID = 'legal-modal-overlay';

  function getConsents() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
    } catch(e) {
      return {};
    }
  }

  function saveConsents(data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }

  function allConsented() {
    const c = getConsents();
    return c.age === true && c.legal === true && c.risk === true && c.privacy === true;
  }

  if (allConsented()) {
    showLegalFooter();
    return;
  }

  const TEXTS = {
    age: {
      title: 'Yas Onayi / Age Verification',
      icon: '\ud83d\ude1e',
      color: '#ef4444',
      text: `Bu web sitesi 18 yas ve uzeri kullanicilar icindir. Finansal piyasalar yuksek risk icerir ve resit olmayan bireyler icin uygun degildir.\n\nThis website is intended for users aged 18 and over. Financial markets involve high risk and are not suitable for minors.`,
      checkbox: '18 yasindan buyugum / I am over 18 years old'
    },
    legal: {
      title: 'Yasal Uyari / Legal Disclaimer',
      icon: '\u2696\ufe0f',
      color: '#f59e0b',
      text: `Bu sitede bulunan icerik, tavsiye ve yorumlar hicbir surette yatirim danismanligi olarak degerlendirilmemelidir. Yatirim danismanligi hizmeti, ucuncu kisi yatirim sirketleri tarafindan kisiye ozel sunulmalidir.\n\nBu sitede yer alan ve hicbir sekilde yonlendirici nitelikte olmayan icerik, yorum ve tavsiyeler genel nitelikte bilgi vermeyi amaclamakta olup bu kapsamda soz konusu tavsiyelerin, musterilerin ve diger yatirimcilarin alim satim kararlarini destekleyebilecek yeterli bilgileri kapsamayabilecegini; mali durumunuzla birlikte degerlendirildiginde, risk ve tahmin ettiginiz getiri tercihlerinizle uygun olmayabilecegini ve bu nedenle, sadece burada yer alan bilgilere dayanilarak yatirim karari verilmesinin beklentilerinize uygun sonuclar dogurmayabilecegini onemle hatirlatmak isteriz.\n\nBurada yer alan bilgiler Nechh Robotics tarafindan ve genel bilgilendirme amaci ile hazirlanmaktadir. Yatirim danismanligi hizmetleri; araci kurumlar, portfoy yonetim sirketleri, mevduat kabul etmeyen bankalar ile musteri arasinda imzalanacak sozlesmeler cercevesinde sunulmalidir.\n\nBu sayfalarda yer alan cesitli tavsiye, bilgi ve goruslere dayanilarak yapilacak ileriye donuk yatirimlar ve ticari islemlerin sonuclarindan ya da ortaya cikabilecek zararlardan Nechh Robotics sorumlu tutulamaz.`
    },
    risk: {
      title: 'Risk Aciklamasi / Risk Disclosure',
      icon: '\u26a0\ufe0f',
      color: '#dc2626',
      text: `Yuksek Risk Uyarisi / High Risk Warning\n\nKripto para birimleri, hisse senetleri, forex ve diger finansal enstrumanlarda islem yapmak yuksek duzeyde risk icerir ve tum yatirimcilar icin uygun olmayabilir. Kaldiracli islemler, sermayenizin tamamini kaybetme riskini beraberinde getirir.\n\nGecmis performans, gelecekteki sonuclarin garantisi degildir. Algoritmik sistemler canli piyasada backtest sonuclarindan farkli performans gosterebilir.\n\nTeknik arizalar, veri gecikmeleri ve baglanti sorunlari algoritmik sistemleri etkileyebilir. Piyasa kosullari hizla degisebilir ve sistemler zamaninda adapte olamayabilir.\n\nSadece kaybetmeyi goze alabileceginiz miktarla islem yapiniz. Nechh Robotics analiz araclari saglar, yatirim tavsiyesi vermez. Karar vermeden once kendi arastirmanizi yapiniz ve nitelikli bir finansal danismana basvurunuz.`
    },
    privacy: {
      title: 'Gizlilik ve Cerezler / Privacy & Cookies',
      icon: '\ud83d\udd12',
      color: '#10b981',
      text: `Kisisel verileriniz, 6698 sayili Kisisel Verilerin Korunmasi Kanunu (KVKK) ve GDPR kapsaminda korunmaktadir.\n\nTopladigimiz veriler: E-posta adresiniz, odeme bilgileriniz (Stripe uzerinden), kullanim istatistikleri.\n\nCerezler: Sitemizde deneyiminizi iyilestirmek ve trafigi analiz etmek icin cerezler kullaniyoruz. Tarayicinizdan cerezleri reddedebilirsiniz.\n\nVerileriniz ucuncu taraflarla paylasilmaz. Abonelik iptali istediginiz zaman yapilabilir.\n\nDetayli bilgi icin: Gizlilik Politikamizi inceleyiniz.`
    }
  };

  const steps = ['age', 'legal', 'risk', 'privacy'];
  let currentStep = 0;

  function getNextUnconsented() {
    const c = getConsents();
    for (let i = 0; i < steps.length; i++) {
      if (!c[steps[i]]) return i;
    }
    return -1;
  }

  function buildModal() {
    currentStep = getNextUnconsented();
    if (currentStep === -1) return false;

    const step = steps[currentStep];
    const data = TEXTS[step];
    const progress = ((currentStep) / steps.length * 100).toFixed(0);

    return `
      <div id="${MODAL_ID}" style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.95);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      ">
        <div style="
          max-width: 760px;
          width: 100%;
          background: #111;
          border: 1px solid #262626;
          border-radius: 20px;
          overflow: hidden;
          max-height: 92vh;
          display: flex;
          flex-direction: column;
        ">
          <div style="
            background: ${data.color}15;
            border-bottom: 2px solid ${data.color};
            padding: 24px 32px;
            display: flex;
            align-items: center;
            gap: 16px;
          ">
            <div style="
              width: 48px;
              height: 48px;
              background: ${data.color}25;
              border: 2px solid ${data.color};
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 24px;
            ">${data.icon}</div>
            <div style="flex: 1;">
              <h2 style="margin: 0; font-size: 20px; color: ${data.color};">${data.title}</h2>
              <p style="margin: 4px 0 0 0; color: #737373; font-size: 12px;">Adim ${currentStep + 1} / ${steps.length}</p>
            </div>
            <div style="
              width: 48px;
              height: 48px;
              border-radius: 50%;
              background: conic-gradient(${data.color} ${progress}%, #262626 0);
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 12px;
              font-weight: 700;
              color: #fff;
            ">
              <div style="width: 40px; height: 40px; background: #111; border-radius: 50%; display: flex; align-items: center; justify-content: center;">
                ${progress}%
              </div>
            </div>
          </div>

          <div style="
            padding: 32px;
            overflow-y: auto;
            flex: 1;
          ">
            <div style="
              background: #0a0a0a;
              border: 1px solid #262626;
              border-radius: 12px;
              padding: 24px;
              margin-bottom: 24px;
              max-height: 280px;
              overflow-y: auto;
            ">
              <p style="
                color: #a3a3a3;
                font-size: 14px;
                line-height: 1.9;
                margin: 0;
                white-space: pre-line;
              ">${data.text}</p>
            </div>

            <label style="
              display: flex;
              align-items: flex-start;
              gap: 14px;
              cursor: pointer;
              padding: 20px;
              background: #0a0a0a;
              border: 2px solid #262626;
              border-radius: 12px;
              transition: all 0.2s;
            " onmouseover="this.style.borderColor='${data.color}'" onmouseout="this.style.borderColor='#262626'">
              <input type="checkbox" id="legal-checkbox" style="
                width: 22px;
                height: 22px;
                accent-color: ${data.color};
                margin-top: 2px;
                cursor: pointer;
                flex-shrink: 0;
              ">
              <span style="color: #d4d4d4; font-size: 15px; line-height: 1.5; font-weight: 500;">
                ${data.checkbox || 'Yukaridaki metni okudum, anladim ve kabul ediyorum / I have read, understood, and agree to the above'}
              </span>
            </label>
          </div>

          <div style="
            padding: 24px 32px;
            border-top: 1px solid #262626;
            background: #0a0a0a;
          ">
            <button id="legal-accept-btn" disabled style="
              width: 100%;
              padding: 16px;
              background: #262626;
              color: #525252;
              border: none;
              border-radius: 10px;
              font-weight: 700;
              font-size: 16px;
              cursor: not-allowed;
              transition: all 0.2s;
              letter-spacing: 0.5px;
            ">
              Onayla ve Devam Et / Confirm & Continue
            </button>
            <p style="
              color: #525252;
              font-size: 11px;
              text-align: center;
              margin-top: 12px;
            ">
              Bu onaylar tarayicinizda guvenle saklanir. / These consents are securely saved in your browser.
            </p>
          </div>
        </div>
      </div>
    `;
  }

  function showModal() {
    const html = buildModal();
    if (!html) {
      showLegalFooter();
      return;
    }

    document.body.style.overflow = 'hidden';
    document.body.insertAdjacentHTML('beforeend', html);

    const checkbox = document.getElementById('legal-checkbox');
    const btn = document.getElementById('legal-accept-btn');
    const step = steps[currentStep];
    const data = TEXTS[step];

    checkbox.addEventListener('change', function() {
      if (this.checked) {
        btn.disabled = false;
        btn.style.background = data.color;
        btn.style.color = '#0a0a0a';
        btn.style.cursor = 'pointer';
      } else {
        btn.disabled = true;
        btn.style.background = '#262626';
        btn.style.color = '#525252';
        btn.style.cursor = 'not-allowed';
      }
    });

    btn.addEventListener('click', function() {
      if (!checkbox.checked) return;

      const consents = getConsents();
      consents[step] = true;
      consents[step + '_date'] = new Date().toISOString();
      saveConsents(consents);

      const modal = document.getElementById(MODAL_ID);
      modal.style.opacity = '0';
      modal.style.transition = 'opacity 0.3s ease';

      setTimeout(() => {
        modal.remove();
        document.body.style.overflow = '';

        if (!allConsented()) {
          showModal();
        } else {
          showLegalFooter();
        }
      }, 300);
    });

    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') e.preventDefault();
    });

    document.getElementById(MODAL_ID).addEventListener('click', function(e) {
      if (e.target === this) e.preventDefault();
    });
  }

  function showLegalFooter() {
    if (document.getElementById('legal-footer-bar')) return;

    const footer = document.createElement('div');
    footer.id = 'legal-footer-bar';
    footer.style.cssText = `
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: #0a0a0a;
      border-top: 1px solid #262626;
      padding: 10px 20px;
      z-index: 9990;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 11px;
      color: #525252;
      text-align: center;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    `;

    footer.innerHTML = `
      <span>\ud83d\ude1e 18+ | Yasal Uyari: Yatirim tavsiyesi degildir |
      <a href="risk-disclosure.html" style="color: #737373; text-decoration: underline;">Risk</a> |
      <a href="privacy.html" style="color: #737373; text-decoration: underline;">Gizlilik</a> |
      <a href="terms.html" style="color: #737373; text-decoration: underline;">Kosullar</a></span>
      <button onclick="resetLegalConsents()" style="background: transparent; border: 1px solid #333; color: #525252; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 10px;">Onaylari Sifirla</button>
    `;

    document.body.appendChild(footer);
    document.body.style.paddingBottom = '40px';
  }

  window.resetLegalConsents = function() {
    if (confirm('Tum yasal onaylari sifirlamak istiyor musunuz? Sayfa yenilenecek.')) {
      localStorage.removeItem(STORAGE_KEY);
      location.reload();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showModal);
  } else {
    showModal();
  }

})();
