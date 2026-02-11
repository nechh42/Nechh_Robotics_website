/**
 * Nechh Radar Integration Script
 * Fetches JSON analysis data and updates the frontend UI.
 */

const DATA_URL = 'radar_data.json'; // Local file for immediate preview

async function fetchRadarData() {
    try {
        const response = await fetch(DATA_URL);
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error('Error fetching radar data:', error);
        // Fallback or loading state
        document.getElementById('system-status-dot').style.color = 'gray';
        document.getElementById('system-status-text').textContent = 'Connecting...';
    }
}

function updateUI(data) {
    if (!data || !data.website_data) return;

    const webData = data.website_data;

    // 1. Update Status Bar
    const statusDot = document.getElementById('system-status-dot');
    const statusText = document.getElementById('system-status-text');
    const lastUpdate = document.getElementById('last-update');
    const activeSym = document.getElementById('active-symbols');
    const uptime = document.getElementById('uptime');

    if (webData.system_status.status === 'OPERATIONAL') {
        statusDot.classList.remove('text-red-500', 'text-gray-500');
        statusDot.classList.add('text-green-500');
        statusText.textContent = 'SYSTEM ONLINE';
    } else {
        statusDot.classList.remove('text-green-500', 'text-gray-500');
        statusDot.classList.add('text-red-500');
        statusText.textContent = 'SYSTEM OFFLINE';
    }

    lastUpdate.textContent = webData.system_status.last_update;
    activeSym.textContent = webData.system_status.active_symbols;
    uptime.textContent = webData.system_status.uptime;

    // 2. Update Quick Cards
    const cardsContainer = document.getElementById('quick-cards-container');
    cardsContainer.innerHTML = ''; // Clear existing

    webData.quick_cards.forEach(card => {
        const cardEl = document.createElement('div');
        cardEl.className = 'bg-white p-4 rounded-xl shadow border border-gray-100 card-hover';

        const signalColor = card.signal === '🟢' ? 'text-green-500' : 'text-red-500';
        const changeColor = card.change.includes('+') ? 'text-green-600' : 'text-red-600';

        cardEl.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span class="font-bold text-gray-800">${card.symbol}</span>
                <span class="${signalColor} text-sm">${card.signal}</span>
            </div>
            <div class="mb-2">
                <span class="text-2xl font-bold text-gray-900">$${card.price}</span>
                <span class="text-xs font-medium ${changeColor} ml-2">${card.change}</span>
            </div>
            <div class="text-xs text-gray-500 bg-gray-50 p-2 rounded">
                <span class="font-semibold text-gray-700">${card.tag_label}:</span> ${card.tag_value}
            </div>
        `;
        cardsContainer.appendChild(cardEl);
    });

    // 3. Update Chart (Simple SVG Line)
    renderSimpleChart(webData.live_chart);

    // 4. Update Recent Signals List
    const signalList = document.getElementById('recent-signals-list');
    signalList.innerHTML = '';
    webData.recent_signals.forEach(sig => {
        const li = document.createElement('li');
        li.className = 'text-sm text-gray-600 border-l-2 border-blue-500 pl-2 py-1';
        li.textContent = sig;
        signalList.appendChild(li);
    });
}

function renderSimpleChart(dataPoints) {
    const canvas = document.getElementById('mini-chart');
    if (!canvas || !dataPoints || dataPoints.length === 0) return;

    // Very simple mock chart using HTML5 Canvas
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(37, 99, 235, 0.2)');
    gradient.addColorStop(1, 'rgba(37, 99, 235, 0)');

    // Draw Line
    ctx.beginPath();
    const min = Math.min(...dataPoints);
    const max = Math.max(...dataPoints);

    dataPoints.forEach((val, i) => {
        const x = (i / (dataPoints.length - 1)) * width;
        const y = height - ((val - min) / (max - min) * (height - 20) + 10);

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });

    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Fill
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.fillStyle = gradient;
    ctx.fill();
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchRadarData();
    setInterval(fetchRadarData, 30000); // Poll every 30s
});
