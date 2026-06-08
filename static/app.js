const sessionId = crypto.randomUUID();

const messages = document.getElementById('messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const buttonsRow = document.getElementById('buttons-row');
const uploadRow = document.getElementById('upload-row');
const cvUpload = document.getElementById('cv-upload');

let ws = null;
let pingInterval = null;
let reconnectTimeout = null;
let reconnectCount = 0;
const MAX_RECONNECTS = 5;

// ─── WebSocket connect ────────────────────────
function connect() {
    ws = new WebSocket(`wss://${window.location.host}/ws/${sessionId}`);

    ws.onopen = () => {
        reconnectCount = 0;
        addMessage('system', '🟢 Подключено');

        // Keepalive ping каждые 30 секунд — Railway обрывает idle после ~60с
        pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    };

    ws.onclose = () => {
        clearInterval(pingInterval);

        if (reconnectCount < MAX_RECONNECTS) {
            reconnectCount++;
            const delay = reconnectCount * 2000; // 2с, 4с, 6с...
            addMessage('system', `🔄 Переподключение (${reconnectCount}/${MAX_RECONNECTS})...`);
            reconnectTimeout = setTimeout(connect, delay);
        } else {
            addMessage('system', '🔴 Соединение прервано. Обновите страницу.');
        }
    };

    ws.onerror = () => {
        // onerror всегда идёт перед onclose — не дублируем сообщение
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // Игнорируем pong от сервера если придёт
        if (data.type === 'pong') return;

        // Typing indicator — сервер думает, соединение живо
        if (data.type === 'typing') {
            showTyping();
            return;
        }

        if (data.type === 'message') {
            hideTyping();
            addMessage('bot', data.text);

            // Кнопки быстрого ответа
            buttonsRow.innerHTML = '';
            if (data.buttons && data.buttons.length > 0) {
                data.buttons.forEach(btn => {
                    const b = document.createElement('button');
                    b.className = 'quick-btn';
                    b.textContent = btn;
                    b.onclick = () => sendMessage(btn);
                    buttonsRow.appendChild(b);
                });
            }

            // Кнопка загрузки файла
            uploadRow.style.display = data.show_upload ? 'block' : 'none';
        }
    };
}

// Запускаем соединение
connect();

// ─── Send message ─────────────────────────────
function sendMessage(text) {
    if (!text.trim()) return;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        addMessage('system', '⚠️ Нет соединения. Подождите...');
        return;
    }
    addMessage('user', text);
    ws.send(JSON.stringify({ type: 'text', text: text }));
    userInput.value = '';
    buttonsRow.innerHTML = '';
}

sendBtn.onclick = () => sendMessage(userInput.value);

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(userInput.value);
    }
});

// ─── PDF Upload ───────────────────────────────
cvUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    addMessage('user', `📎 ${file.name}`);
    addMessage('system', '⏳ Загружаю файл...');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);

    try {
        const response = await fetch('/upload-cv', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.status === 'ok') {
            ws.send(JSON.stringify({ type: 'cv_uploaded', text: result.text }));
        } else {
            addMessage('system', '❌ Ошибка загрузки файла.');
        }
    } catch (err) {
        addMessage('system', '❌ Ошибка: ' + err.message);
    }

    cvUpload.value = '';
    uploadRow.style.display = 'none';
});

// ─── Add message to chat ──────────────────────
function linkify(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(urlRegex, '<a href="$1" target="_blank" rel="noopener" style="color:#90cdf4;text-decoration:underline;">$1</a>');
}

function addMessage(sender, text) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = linkify(text);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}

// ─── Typing indicator ─────────────────────────
function showTyping() {
    let el = document.getElementById('typing-indicator');
    if (!el) {
        el = document.createElement('div');
        el.id = 'typing-indicator';
        el.className = 'message bot';
        el.innerHTML = '⏳ <em>Думаю...</em>';
        messages.appendChild(el);
        messages.scrollTop = messages.scrollHeight;
    }
}

function hideTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}