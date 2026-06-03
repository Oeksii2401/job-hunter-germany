const sessionId = crypto.randomUUID();
const ws = new WebSocket(`wss://${window.location.host}/ws/${sessionId}`);

const messages = document.getElementById('messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const buttonsRow = document.getElementById('buttons-row');
const uploadRow = document.getElementById('upload-row');
const cvUpload = document.getElementById('cv-upload');

// ─── WebSocket handlers ───────────────────────
ws.onopen = () => {
    addMessage('system', '🟢 Подключено');
};

ws.onclose = () => {
    addMessage('system', '🔴 Соединение прервано. Обновите страницу.');
};

ws.onerror = () => {
    addMessage('system', '⚠️ Ошибка соединения.');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'message') {
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

// ─── Send message ─────────────────────────────
function sendMessage(text) {
    if (!text.trim()) return;
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
function addMessage(sender, text) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
}
