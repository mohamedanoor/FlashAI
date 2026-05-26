/* =============================================
   AI Flashcard Generator – main.js v6
   ============================================= */

'use strict';

// ── State ──────────────────────────────────────
let currentDeck = null;
let allCards    = [];
let currentIndex = 0;
let currentMode  = 'flashcard';
let sessionStats = { studied: 0, correct: 0, startTime: Date.now() };
let quizCards    = [];
let quizIndex    = 0;
let writtenCards = [];
let writtenIndex = 0;
let isFlipped    = false;

// ── Page Detection ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('flashcard-form')) {
        initHomePage();
    }
    if (document.getElementById('study-card') || document.getElementById('flashcard-mode')) {
        initStudyPage();
    }
});

// ═══════════════════════════════════════════════
//  HOME PAGE
// ═══════════════════════════════════════════════

function initHomePage() {
    setupTextForm();
    setupTopicForm();
    setupFileForm();
    setupDropZone();
    updateCharCount();
}

// ── Tab Switching ──────────────────────────────
function switchTab(tab) {
    ['text', 'topic', 'file'].forEach(t => {
        document.getElementById(`${t}-input-container`).classList.toggle('active', t === tab);
        document.getElementById(`${t}-input-container`).classList.toggle('hidden', t !== tab);
        document.getElementById(`${t}-selector`).classList.toggle('active', t === tab);
        document.getElementById(`${t}-selector`).setAttribute('aria-selected', t === tab);
    });
}

// ── Advanced Options Toggle ────────────────────
function toggleAdvanced(id) {
    const el = document.getElementById(id);
    el.classList.toggle('hidden');
}

// ── Character Counter ──────────────────────────
function updateCharCount() {
    const ta = document.getElementById('text_input');
    const counter = document.getElementById('text-char-count');
    if (!ta || !counter) return;
    ta.addEventListener('input', () => {
        const len = ta.value.length;
        counter.textContent = `${len} character${len !== 1 ? 's' : ''}`;
        counter.style.color = len < 50 ? '#e74c3c' : '#666';
    });
}

// ── Text Form ──────────────────────────────────
function setupTextForm() {
    const form = document.getElementById('flashcard-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = document.getElementById('text_input').value.trim();
        if (!text || text.length < 50) {
            showError('Please enter at least 50 characters of text.');
            return;
        }
        const formData = new FormData(form);
        formData.set('text_input', text);
        formData.set('difficulty', document.getElementById('text-difficulty').value);
        formData.set('model', document.getElementById('text-model').value);
        await submitGeneration('/generate', formData, 'text-submit-btn');
    });
}

// ── Topic Form ────────────────────────────────
function setupTopicForm() {
    const form = document.getElementById('topic-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topic = document.getElementById('topic_input').value.trim();
        if (!topic || topic.length < 3) {
            showError('Please enter a topic (at least 3 characters).');
            return;
        }
        const formData = new FormData(form);
        formData.set('topic_input', topic);
        formData.set('difficulty', document.getElementById('topic-difficulty').value);
        formData.set('model', document.getElementById('topic-model').value);
        await submitGeneration('/generate_from_topic', formData, 'topic-submit-btn');
    });
}

// ── File Form ─────────────────────────────────
function setupFileForm() {
    const form = document.getElementById('file-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const files = document.getElementById('file_input').files;
        if (!files || files.length === 0) {
            showError('Please select at least one file.');
            return;
        }
        const formData = new FormData(form);
        formData.set('difficulty', document.getElementById('file-difficulty').value);
        formData.set('model', document.getElementById('file-model').value);
        await submitGeneration('/generate_from_files', formData, 'file-submit-btn');
    });
}

// ── Drop Zone ────────────────────────────────
function setupDropZone() {
    const zone   = document.getElementById('drop-zone');
    const input  = document.getElementById('file_input');
    const list   = document.getElementById('file-list');
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    input.addEventListener('change', () => renderFileList(input.files, list));

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        input.files = e.dataTransfer.files;
        renderFileList(input.files, list);
    });
}

function renderFileList(files, container) {
    container.innerHTML = '';
    Array.from(files).forEach(f => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `<span>📄 ${f.name}</span><span>${(f.size / 1024).toFixed(1)} KB</span>`;
        container.appendChild(item);
    });
}

// ── Core Generation ──────────────────────────
async function submitGeneration(url, formData, btnId) {
    showLoading();
    const btn = document.getElementById(btnId);
    if (btn) { btn.disabled = true; btn.textContent = 'Generating...'; }

    animateProgress();

    try {
        const res = await fetch(url, { method: 'POST', body: formData });
        const data = await res.json();

        if (!res.ok) throw new Error(data.error || `Server error ${res.status}`);
        if (data.error) throw new Error(data.error);

        currentDeck = data;
        displayResults(data);
    } catch (err) {
        hideLoading();
        showError(err.message || 'An unexpected error occurred. Please try again.');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '✨ Generate Flashcards'; }
    }
}

let progressInterval = null;

function animateProgress() {
    const fill = document.getElementById('progress-fill');
    if (!fill) return;
    let pct = 0;
    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
        pct = Math.min(pct + Math.random() * 6, 88);
        fill.style.width = pct + '%';
    }, 300);
}

function showLoading() {
    document.getElementById('loading-section')?.classList.remove('hidden');
    document.getElementById('results-section')?.classList.add('hidden');
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    document.querySelector('.tabs')?.classList.add('hidden');
}

function hideLoading() {
    clearInterval(progressInterval);
    document.getElementById('loading-section')?.classList.add('hidden');
    document.querySelectorAll('.tab-panel').forEach(p => {
        if (p.id === 'text-input-container') p.classList.remove('hidden');
    });
    document.querySelector('.tabs')?.classList.remove('hidden');
}

function displayResults(data) {
    clearInterval(progressInterval);
    const fill = document.getElementById('progress-fill');
    if (fill) fill.style.width = '100%';

    setTimeout(() => {
        document.getElementById('loading-section')?.classList.add('hidden');

        const mainCards = data.main || [];
        const defCards  = data.definitions || [];
        const clozeCards = data.cloze || [];

        renderCardGrid('flashcard-container', mainCards);
        renderCardGrid('definitions-container', defCards);
        renderCardGrid('cloze-container', clozeCards);

        const setCount = (id, count) => {
            const el = document.getElementById(id);
            if (el) el.textContent = count > 0 ? count : '';
        };
        setCount('main-count', mainCards.length);
        setCount('def-count', defCards.length);
        setCount('cloze-count', clozeCards.length);

        if (data.metadata) {
            const cost = document.getElementById('cost-info');
            if (cost) {
                cost.textContent = `Model: ${data.metadata.model_used} · Estimated cost: $${(data.metadata.estimated_cost || 0).toFixed(4)}`;
            }
        }

        document.getElementById('results-section')?.classList.remove('hidden');
    }, 400);
}

function renderCardGrid(containerId, cards) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    if (!cards || cards.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:20px">No cards generated for this type.</p>';
        return;
    }

    cards.forEach(card => {
        const el = document.createElement('div');
        el.className = 'preview-flashcard';
        const diff = card.difficulty || 'medium';
        el.innerHTML = `
            <span class="diff-badge diff-${diff}">${diff}</span>
            <div class="front">${escapeHtml(card.question || '')}</div>
            <div class="back">${escapeHtml(card.answer || '')}</div>`;
        container.appendChild(el);
    });
}

function showCardType(type) {
    ['main', 'definitions', 'cloze'].forEach(t => {
        document.getElementById(t === 'main' ? 'flashcard-container' : `${t === 'definitions' ? 'definitions' : 'cloze'}-container`)
            ?.classList.toggle('hidden', t !== type);
    });
    document.querySelectorAll('.card-type-tab').forEach((btn, i) => {
        btn.classList.toggle('active', ['main', 'definitions', 'cloze'][i] === type);
    });
}

function studyNow() {
    if (!currentDeck) return;
    sessionStorage.setItem('studyDeck', JSON.stringify(currentDeck));
    window.location.href = '/flashcards';
}

function saveDeck() {
    document.getElementById('save-modal')?.classList.remove('hidden');
    document.getElementById('modal-overlay')?.classList.remove('hidden');
    const titleEl = document.getElementById('deck-title');
    if (titleEl && !titleEl.value) titleEl.value = 'My Flashcard Deck';
}

function closeModal() {
    document.getElementById('save-modal')?.classList.add('hidden');
    document.getElementById('modal-overlay')?.classList.add('hidden');
}

async function confirmSave() {
    const title = document.getElementById('deck-title')?.value?.trim();
    const description = document.getElementById('deck-description')?.value?.trim();
    if (!title) { alert('Please enter a title for your deck.'); return; }
    if (!currentDeck) return;

    try {
        const res = await fetch('/save_deck', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                cards: currentDeck,
                model_used: currentDeck.metadata?.model_used || 'gpt-4',
                source_type: 'text'
            })
        });
        const data = await res.json();
        if (data.success) {
            closeModal();
            showSuccessToast('Deck saved successfully!');
        } else {
            alert('Error saving deck: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        alert('Error saving deck: ' + err.message);
    }
}

function downloadDeck(deck) {
    if (!deck) { alert('No flashcards to download.'); return; }
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/download_deck_direct';
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'data';
    input.value = JSON.stringify({ title: 'Flashcards', cards: deck });
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
    setTimeout(() => document.body.removeChild(form), 500);
}

function resetForm() {
    currentDeck = null;
    document.getElementById('results-section')?.classList.add('hidden');
    document.querySelector('.tabs')?.classList.remove('hidden');
    document.getElementById('text-input-container')?.classList.remove('hidden');
    ['topic-input-container','file-input-container'].forEach(id => {
        document.getElementById(id)?.classList.add('hidden');
    });
    ['text-selector','topic-selector','file-selector'].forEach((id, i) => {
        document.getElementById(id)?.classList.toggle('active', i === 0);
    });
    const ta = document.getElementById('text_input');
    if (ta) ta.value = '';
}

function showError(msg) {
    const existing = document.getElementById('error-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.id = 'error-toast';
    toast.style.cssText = `
        position:fixed;bottom:24px;right:24px;background:#e74c3c;color:white;
        padding:14px 20px;border-radius:10px;font-weight:600;z-index:9999;
        box-shadow:0 4px 16px rgba(231,76,60,0.35);max-width:360px;font-size:0.9rem`;
    toast.textContent = '⚠️ ' + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function showSuccessToast(msg) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position:fixed;bottom:24px;right:24px;background:#27ae60;color:white;
        padding:14px 20px;border-radius:10px;font-weight:600;z-index:9999;
        box-shadow:0 4px 16px rgba(39,174,96,0.35);max-width:360px;font-size:0.9rem`;
    toast.textContent = '✅ ' + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

// ═══════════════════════════════════════════════
//  STUDY PAGE
// ═══════════════════════════════════════════════

function initStudyPage() {
    loadStudyDeck();
}

function loadStudyDeck() {
    // Try preloaded deck (from server)
    const preloaded = document.getElementById('preloaded-deck');
    if (preloaded) {
        try {
            const data = JSON.parse(preloaded.textContent);
            initStudySession(data.title, data.cards);
            return;
        } catch (e) { console.error('Preloaded deck parse error:', e); }
    }

    // Try sessionStorage (from home page)
    const stored = sessionStorage.getItem('studyDeck');
    if (stored) {
        try {
            const data = JSON.parse(stored);
            initStudySession('Study Session', data);
            sessionStorage.removeItem('studyDeck');
            return;
        } catch (e) { console.error('SessionStorage deck parse error:', e); }
    }

    document.getElementById('study-deck-title').textContent = 'No deck loaded';
}

function initStudySession(title, cards) {
    // Set title
    const titleEl = document.getElementById('study-deck-title');
    if (titleEl) titleEl.textContent = title;

    // Flatten all cards
    allCards = [
        ...(cards.main || []),
        ...(cards.definitions || []),
        ...(cards.cloze || [])
    ];

    if (allCards.length === 0) {
        document.getElementById('study-deck-title').textContent = 'No cards found';
        return;
    }

    allCards = shuffleArray(allCards);
    sessionStats = { studied: 0, correct: 0, startTime: Date.now() };
    currentIndex = 0;

    // Prepare quiz/written versions
    quizCards    = shuffleArray([...allCards]);
    writtenCards = shuffleArray([...allCards]);
    quizIndex    = 0;
    writtenIndex = 0;

    updateProgressUI();
    loadFlashcard(currentIndex);
    loadQuizCard(quizIndex);
    loadWrittenCard(writtenIndex);
}

function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

// ── Flashcard Mode ────────────────────────────
function loadFlashcard(index) {
    if (!allCards.length) return;
    const card = allCards[index];
    const front = document.getElementById('card-front-content');
    const back  = document.getElementById('card-back-content');
    if (front) front.textContent = card.question || '';
    if (back)  back.textContent  = card.answer || '';

    // Reset flip
    isFlipped = false;
    document.getElementById('study-card')?.classList.remove('flipped');

    // Hide rating buttons until flipped
    document.querySelector('.hard-btn')?.style.setProperty('display','none');
    document.querySelector('.easy-btn')?.style.setProperty('display','none');

    updateProgressUI();
}

function flipCard() {
    const card = document.getElementById('study-card');
    if (!card) return;
    isFlipped = !isFlipped;
    card.classList.toggle('flipped', isFlipped);

    if (isFlipped) {
        document.querySelector('.hard-btn')?.style.setProperty('display','inline-block');
        document.querySelector('.easy-btn')?.style.setProperty('display','inline-block');
        sessionStats.studied++;
    }
}

function rateCard(rating) {
    if (rating === 'easy') sessionStats.correct++;
    nextCard();
}

function nextCard() {
    if (currentIndex < allCards.length - 1) {
        currentIndex++;
        loadFlashcard(currentIndex);
    } else {
        showSessionComplete();
    }
}

function prevCard() {
    if (currentIndex > 0) {
        currentIndex--;
        loadFlashcard(currentIndex);
    }
}

// ── Quiz Mode ─────────────────────────────────
function loadQuizCard(index) {
    if (!quizCards.length) return;
    const card = quizCards[index];

    const qEl = document.getElementById('quiz-question');
    const oEl = document.getElementById('quiz-options');
    const fEl = document.getElementById('quiz-feedback');
    const nEl = document.getElementById('quiz-next-btn');

    if (qEl) qEl.textContent = card.question || '';
    if (fEl) { fEl.textContent = ''; fEl.classList.add('hidden'); }
    if (nEl) nEl.style.display = 'none';

    // Build options: correct + 3 random wrong answers
    const correct = card.answer || '';
    const others  = quizCards
        .filter((_, i) => i !== index)
        .map(c => c.answer)
        .filter(a => a && a !== correct)
        .sort(() => Math.random() - 0.5)
        .slice(0, 3);

    const options = shuffleArray([correct, ...others]);

    if (oEl) {
        oEl.innerHTML = '';
        options.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'quiz-option';
            btn.textContent = opt;
            btn.onclick = () => answerQuiz(btn, opt, correct, oEl, fEl, nEl);
            oEl.appendChild(btn);
        });
    }
}

function answerQuiz(btn, chosen, correct, optionsEl, feedbackEl, nextBtn) {
    // Disable all options
    optionsEl.querySelectorAll('.quiz-option').forEach(b => {
        b.disabled = true;
        if (b.textContent === correct) b.classList.add('correct');
    });

    const isCorrect = chosen === correct;
    if (!isCorrect) btn.classList.add('wrong');

    if (feedbackEl) {
        feedbackEl.textContent = isCorrect ? '✅ Correct!' : `❌ Correct answer: ${correct}`;
        feedbackEl.style.cssText = `background:${isCorrect ? '#d5f5e3' : '#fad7d7'};color:${isCorrect ? '#1e8449' : '#922b21'}`;
        feedbackEl.classList.remove('hidden');
    }

    sessionStats.studied++;
    if (isCorrect) sessionStats.correct++;

    if (nextBtn) nextBtn.style.display = 'block';
}

function nextQuizCard() {
    if (quizIndex < quizCards.length - 1) {
        quizIndex++;
        loadQuizCard(quizIndex);
    } else {
        showSessionComplete();
    }
    updateProgressUI();
}

// ── Written Mode ──────────────────────────────
function loadWrittenCard(index) {
    if (!writtenCards.length) return;
    const card = writtenCards[index];

    const qEl = document.getElementById('written-question');
    const aEl = document.getElementById('written-answer');
    const fEl = document.getElementById('written-feedback');
    const nEl = document.getElementById('written-next-btn');

    if (qEl) qEl.textContent = card.question || '';
    if (aEl) aEl.value = '';
    if (fEl) { fEl.textContent = ''; fEl.classList.add('hidden'); }
    if (nEl) nEl.style.display = 'none';
}

function checkWrittenAnswer() {
    if (!writtenCards.length) return;
    const card    = writtenCards[writtenIndex];
    const input   = document.getElementById('written-answer')?.value?.trim().toLowerCase();
    const correct = (card.answer || '').toLowerCase();
    const fEl = document.getElementById('written-feedback');
    const nEl = document.getElementById('written-next-btn');

    const isCorrect = input && correct.includes(input) || input === correct;

    if (fEl) {
        fEl.innerHTML = `<strong>${isCorrect ? '✅ Great!' : '📝 Model Answer:'}</strong><br>${escapeHtml(card.answer || '')}`;
        fEl.style.cssText = `background:${isCorrect ? '#d5f5e3' : '#fdebd0'};color:${isCorrect ? '#1e8449' : '#7d4e00'};padding:14px;border-radius:8px`;
        fEl.classList.remove('hidden');
    }

    sessionStats.studied++;
    if (isCorrect) sessionStats.correct++;

    if (nEl) nEl.style.display = 'block';
}

function nextWrittenCard() {
    if (writtenIndex < writtenCards.length - 1) {
        writtenIndex++;
        loadWrittenCard(writtenIndex);
    } else {
        showSessionComplete();
    }
    updateProgressUI();
}

// ── Mode Switching ────────────────────────────
function setMode(mode) {
    currentMode = mode;
    ['flashcard', 'quiz', 'written'].forEach(m => {
        document.getElementById(`${m}-mode`)?.classList.toggle('active', m === mode);
        document.getElementById(`${m}-mode`)?.classList.toggle('hidden', m !== mode);
        document.getElementById(`mode-${m}`)?.classList.toggle('active', m === mode);
    });
}

// ── Progress ──────────────────────────────────
function updateProgressUI() {
    const total = allCards.length;
    const current = currentMode === 'quiz' ? quizIndex :
                    currentMode === 'written' ? writtenIndex : currentIndex;
    const pct = total ? ((current + 1) / total) * 100 : 0;

    const fill = document.getElementById('study-progress-fill');
    if (fill) fill.style.width = Math.min(pct, 100) + '%';

    const text = document.getElementById('progress-text');
    if (text) text.textContent = `Card ${Math.min(current + 1, total)} / ${total}`;
}

// ── Session Complete ──────────────────────────
function showSessionComplete() {
    document.querySelectorAll('.study-mode').forEach(el => {
        el.classList.remove('active');
        el.classList.add('hidden');
    });
    document.getElementById('session-complete')?.classList.remove('hidden');

    const duration = Math.round((Date.now() - sessionStats.startTime) / 60000);
    const accuracy = sessionStats.studied > 0
        ? Math.round((sessionStats.correct / sessionStats.studied) * 100)
        : 0;

    const statsEl = document.getElementById('complete-stats');
    if (statsEl) {
        statsEl.innerHTML = `
            <div>Cards studied: <strong>${sessionStats.studied}</strong></div>
            <div>Correct: <strong>${sessionStats.correct}</strong></div>
            <div>Accuracy: <strong>${accuracy}%</strong></div>
            <div>Time: <strong>${duration} min</strong></div>`;
    }

    // Save session to server if session ID exists
    if (typeof SESSION_ID !== 'undefined' && SESSION_ID) {
        fetch('/update_study_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: SESSION_ID,
                cards_studied: sessionStats.studied,
                cards_correct: sessionStats.correct,
                duration_minutes: duration,
                study_mode: currentMode
            })
        }).catch(err => console.warn('Could not save session:', err));
    }
}

function restartSession() {
    currentIndex  = 0;
    quizIndex     = 0;
    writtenIndex  = 0;
    sessionStats  = { studied: 0, correct: 0, startTime: Date.now() };
    allCards      = shuffleArray(allCards);
    quizCards     = shuffleArray([...allCards]);
    writtenCards  = shuffleArray([...allCards]);

    document.getElementById('session-complete')?.classList.add('hidden');
    setMode('flashcard');
    loadFlashcard(0);
    loadQuizCard(0);
    loadWrittenCard(0);
    updateProgressUI();
}

// Expose globals needed by inline HTML handlers
window.switchTab      = switchTab;
window.toggleAdvanced = toggleAdvanced;
window.showCardType   = showCardType;
window.studyNow       = studyNow;
window.saveDeck       = saveDeck;
window.closeModal     = closeModal;
window.confirmSave    = confirmSave;
window.downloadDeck   = downloadDeck;
window.resetForm      = resetForm;
window.flipCard       = flipCard;
window.rateCard       = rateCard;
window.nextCard       = nextCard;
window.prevCard       = prevCard;
window.nextQuizCard   = nextQuizCard;
window.checkWrittenAnswer = checkWrittenAnswer;
window.nextWrittenCard = nextWrittenCard;
window.setMode        = setMode;
window.restartSession = restartSession;
