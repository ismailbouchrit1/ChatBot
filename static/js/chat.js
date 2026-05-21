/* ===== Chat Interface Logic ===== */
document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const typingIndicator = document.getElementById('typingIndicator');
    const newSessionBtn = document.getElementById('newSessionBtn');
    const emotionModal = document.getElementById('emotionModal');
    const msgCountEl = document.getElementById('msgCount');
    const chatWelcome = document.getElementById('chatWelcome');
    const sessionList = document.getElementById('sessionList');

    let currentConversationId = null;
    let isProcessing = false;

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        sendBtn.disabled = !messageInput.value.trim();
    });

    // Enter to send (shift+enter for newline)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (messageInput.value.trim() && !isProcessing) chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Load conversations
    async function loadConversations() {
        try {
            const data = await api('/api/chat/conversations');
            sessionList.innerHTML = '';
            data.conversations.forEach(c => {
                const el = document.createElement('div');
                el.className = 'session-item' + (c.id === currentConversationId ? ' active' : '');

                const date = new Date(c.started_at);
                const label = document.createElement('span');
                label.className = 'session-label';
                label.textContent = `${date.toLocaleDateString('fr-FR')} - ${c.emotion_initial || 'Session'}`;
                label.addEventListener('click', () => loadConversation(c.id));

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'session-delete';
                deleteBtn.title = 'Supprimer cette conversation';
                deleteBtn.innerHTML = '<i data-lucide="trash-2"></i>';
                deleteBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (!confirm('Supprimer cette conversation ?')) return;
                    try {
                        await api(`/api/chat/conversations/${c.id}`, { method: 'DELETE' });
                        showToast('Conversation supprimee');
                        if (currentConversationId === c.id) {
                            currentConversationId = null;
                            chatMessages.innerHTML = chatWelcome.outerHTML;
                        }
                        loadConversations();
                    } catch (err) {
                        showToast('Erreur de suppression', 'error');
                    }
                });

                el.appendChild(label);
                el.appendChild(deleteBtn);
                sessionList.appendChild(el);
            });
            lucide.createIcons();
        } catch (e) { /* ignore */ }
    }

    // Load specific conversation messages
    async function loadConversation(convId) {
        try {
            const data = await api(`/api/chat/conversations/${convId}/messages`);
            currentConversationId = convId;
            chatMessages.innerHTML = '';
            if (data.messages.length === 0) {
                chatMessages.innerHTML = chatWelcome.outerHTML;
            } else {
                data.messages.forEach(msg => addMessageBubble(msg.content, msg.sender, msg.timestamp));
            }
            scrollToBottom();
            loadConversations();
        } catch (e) {
            showToast('Erreur de chargement', 'error');
        }
    }

    // New session
    newSessionBtn.addEventListener('click', () => {
        emotionModal.style.display = 'flex';
        lucide.createIcons();
    });

    // Emotion selection
    document.querySelectorAll('.emotion-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const emotion = btn.dataset.emotion;
            document.querySelectorAll('.emotion-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');

            try {
                const data = await api('/api/chat/new-session', {
                    method: 'POST',
                    body: JSON.stringify({ emotion }),
                });
                currentConversationId = data.conversation.id;
                chatMessages.innerHTML = '';
                addMessageBubble(
                    `Nouvelle session. Tu as indique te sentir : ${emotion.replace('_', ' ')}. Je suis la pour t'ecouter.`,
                    'CHATBOT', new Date().toISOString()
                );
                emotionModal.style.display = 'none';
                scrollToBottom();
                loadConversations();
            } catch (e) {
                showToast('Erreur', 'error');
            }
        });
    });

    // Send message
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message || isProcessing) return;

        isProcessing = true;
        sendBtn.disabled = true;

        // Remove welcome if present
        const welcome = chatMessages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        // Add student message
        addMessageBubble(message, 'ELEVE', new Date().toISOString());
        messageInput.value = '';
        messageInput.style.height = 'auto';
        scrollToBottom();

        // Show typing
        typingIndicator.style.display = 'block';
        scrollToBottom();

        try {
            const data = await api('/api/chat/send', {
                method: 'POST',
                body: JSON.stringify({ message, conversation_id: currentConversationId }),
            });

            typingIndicator.style.display = 'none';
            currentConversationId = data.conversation_id;
            addMessageBubble(data.response, 'CHATBOT', data.timestamp);
            msgCountEl.textContent = data.message_count_today;
            scrollToBottom();
            loadConversations();
        } catch (err) {
            typingIndicator.style.display = 'none';
            addMessageBubble("Desole, une erreur est survenue. Reessaie dans un instant.", 'CHATBOT', new Date().toISOString());
            scrollToBottom();
        } finally {
            isProcessing = false;
            sendBtn.disabled = !messageInput.value.trim();
        }
    });

    function addMessageBubble(content, sender, timestamp) {
        const div = document.createElement('div');
        div.className = `message-bubble ${sender === 'ELEVE' ? 'student' : 'bot'}`;
        // Convert **bold** to <strong>
        let html = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br>');
        div.innerHTML = `${html}<span class="message-time">${formatTime(timestamp)}</span>`;
        chatMessages.appendChild(div);
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // Show emotion modal on first load if no active conversation
    async function init() {
        await loadConversations();
        try {
            const data = await api('/api/chat/conversations');
            const activeConv = data.conversations.find(c => c.is_active);
            if (activeConv) {
                await loadConversation(activeConv.id);
            } else {
                emotionModal.style.display = 'flex';
            }
        } catch (e) {
            emotionModal.style.display = 'flex';
        }
        lucide.createIcons();
    }

    init();
});
