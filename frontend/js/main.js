// Intermission — guest-facing chat with Amy, the AI receptionist.
// Drives the conversation UI: typewriter reveal, "thinking" pauses, and the
// request/response flow against the backend (see devserver.py / Lambda).

const waitBeforeReply = 2000;
const typingSpeed = 100;
const waitFirstLoad = 2500;
const waitSeated = 4000; // pause between the greeting and "looking up" details
const mockServer = false;
const audioVolume = 0.7; // 0-1

let userID = null;
let validMessageCount = 0;
let qIdx = 0;
let thinkingAppeared = false;

const receivedQueue = [];
let currentReceived = null;

function startAudio() {
    const audio = document.getElementById('audio');
    audio.muted = false;
    audio.volume = 0;
    const fadeAudio = setInterval(() => {
        if (audio.volume < audioVolume) {
            audio.volume = Math.min(audio.volume + 0.05, 1);
        } else {
            clearInterval(fadeAudio);
        }
    }, 400);
}

function enter() {
    startAudio();

    userID = getUserIdFromUrl();

    if (userID == null) {
        // Curious visitor with no booking link — disable chat, show the CTA.
        document.getElementsByClassName('chat-container')[0].style.pointerEvents = 'none';
        document.getElementById('findOutMore').style.display = 'inline-block';
        return;
    }

    // If they already completed the questionnaire, show the closing message.
    if (localStorage.getItem('finished') === userID) {
        addThinkingMessage();
        setTimeout(() => {
            hideLoader();
            typeMessage(`Thank you for your time. You have completed the questionnaire.

            I hope you enjoy your experience at Intermission! We're very much looking forward to your visit.`);
        }, waitFirstLoad);
        return;
    }

    // Welcome the user.
    setTimeout(() => {
        document.getElementsByClassName('enter')[0].remove();
        addMessage('', 'ai-message');
        thinkingAppeared = true;

        const greeting = `Hello and welcome to your Intermission. My name is Amy and it's my pleasure to assist you!

        Please find a comfortable seat while I find your appointment details.`;
        const greetingReturn = `Welcome back to Intermission!
        It's wonderful to see you again. I'm here to assist you as always.

        Please make yourself comfortable while I quickly retrieve your details.`;
        const isReturning = localStorage.getItem('returning');

        onReceived({
            message: isReturning ? greetingReturn : greeting,
            statusCode: 200,
            status: 'init',
            q_idx: 0,
        });
    }, waitFirstLoad);
}

document.addEventListener('DOMContentLoaded', () => {
    updateInputPlaceholder();
    window.addEventListener('resize', updateInputPlaceholder);

    // Fade the entry button out when clicked.
    document.getElementsByClassName('enter')[0].addEventListener('click', function () {
        this.classList.add('fade-out');
    });

    // Send on Enter.
    const input = document.getElementById('userInput');
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
            e.preventDefault();
        }
    });

    disableUserInput(0);
});

function getUserIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    let id = params.get('u');
    if (id != null) {
        id = id.replace(' ', '+');
    }
    return id;
}

function sendMessage() {
    thinkingAppeared = false;
    const input = document.getElementById('userInput');
    const message = input.value;
    input.value = '';
    if (message.trim() === '') {
        return;
    }

    disableUserInput();
    addMessage(message, 'user-message');
    addThinkingMessage();
    sendMessageToServer(message);
}

function addThinkingMessage() {
    setTimeout(() => {
        addMessage('', 'ai-message');
        thinkingAppeared = true;
    }, waitBeforeReply);
}

function addMessage(text, className, isHtml = false) {
    const messagesContainer = document.getElementById('chatMessages');

    // Bump existing messages up to make room.
    Array.from(messagesContainer.getElementsByClassName('message')).forEach((message) => {
        message.classList.add('bump');
        message.addEventListener('animationend', () => message.classList.remove('bump'));
    });

    const messageDiv = document.createElement('div');
    if (text.length > 0) {
        if (isHtml) {
            messageDiv.innerHTML = text;
        } else {
            messageDiv.textContent = text;
        }
    }
    messageDiv.className = `message ${className} new-message`;

    // AI messages start with a loading indicator until the reply arrives.
    if (className === 'ai-message') {
        const loadingDiv = document.createElement('div');
        loadingDiv.innerHTML = '<div class="lds-ellipsis"><div></div><div></div><div></div><div></div></div>';
        loadingDiv.className = 'message-loading';
        loadingDiv.id = 'message_loading';
        messageDiv.appendChild(loadingDiv);
    }

    messagesContainer.appendChild(messageDiv);
    messageDiv.addEventListener('animationend', () => messageDiv.classList.remove('new-message'));
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function sendMessageToServer(message) {
    if (mockServer) {
        setTimeout(() => onReceived({ statusCode: 200, message: 'Test reply?' }), 200);
        return;
    }

    // In production this posted to an AWS API Gateway URL; locally it's the
    // same-origin endpoint served by devserver.py.
    fetch('/api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, user_id: userID }),
    })
        .then((response) => response.json())
        .then(onReceived)
        .catch((error) => {
            if (error instanceof TypeError) {
                onError('There was a problem with your connection to the server. Try refreshing after a moment.');
            } else {
                onError(error);
            }
        });
}

function processNextMessageIfAble() {
    if (currentReceived != null || receivedQueue.length === 0) {
        return;
    }

    currentReceived = receivedQueue.shift();

    typeMessage(currentReceived.message, typingSpeed, () => {
        const status = currentReceived.status;
        qIdx = currentReceived.q_idx;
        currentReceived = null;

        if (status === 'not_found') {
            addMessage('<a href="https://www.theriptide.co.uk/intermission">theriptide.co.uk/intermission</a>', 'ai-message', true);
            hideLoader();
            return;
        }

        // The init greeting triggers a follow-up request for the first question.
        if (status === 'init') {
            addThinkingMessage();
            setTimeout(() => sendMessageToServer(''), waitSeated);
            return;
        }

        processNextMessageIfAble();

        // Re-enable input once the queue is drained.
        if (currentReceived == null) {
            setTimeout(enableUserInput, 400);
        }
    });
}

function onReceived(data) {
    // If the server replied before the "thinking" bubble appeared, wait for it.
    if (!thinkingAppeared) {
        setTimeout(() => onReceived(data), waitBeforeReply);
        return;
    }

    hideError();
    hideLoader();

    if (data == null) {
        onError('Sorry, communication has been lost with Amy. Please wait a few minutes then refresh the page.');
        return;
    }

    if (data.errorMessage) {
        showServerError();
        return;
    }

    // Rewrite some statuses into guest-friendly copy.
    if (data.status === 'not_found') {
        data.message = `Thank you for your interest in Intermission! Unfortunately, I'm unable to find your details in our system.

        Intermission experiences are carefully curated and require prior booking.

        We invite you to explore our website or contact our customer service for more information on how you can be a part of future Intermission experiences.`;
    } else if (data.status === 'response_error') {
        onError('Sorry, communication has been lost with Amy. Please wait a few minutes then refresh the page.');
        return;
    } else if (data.status === 'rate_limit_error') {
        data.message = 'Sorry, our computer systems are really busy at the moment. I recommend refreshing the page after waiting a moment.';
    }

    validMessageCount += 1;
    if (validMessageCount >= 4) {
        localStorage.setItem('returning', true);
    }

    receivedQueue.push(data);
    processNextMessageIfAble();
}

function onError(error) {
    console.error('Intermission error:', error);
    if (error.status === 'key_error') {
        showServerError();
        return;
    }
    hideLoader();
    showError(error);
}

function showError(message) {
    const el = document.getElementById('error-message');
    el.innerHTML = message ?? 'Sorry, an error occurred.';
    el.parentElement.appendChild(el);
    el.style.display = 'block';
    scrollTop();
}

function showServerError() {
    showError('Oops, looks like something went wrong with my computer. Support has been notified. Sorry about that!');
}

function hideError() {
    document.getElementById('error-message').style.display = 'none';
}

function scrollTop() {
    const chatMessagesDiv = document.getElementById('chatMessages');
    chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;
}

function hideLoader() {
    const div = document.getElementById('message_loading');
    if (div) {
        div.remove();
    }
}

function enableUserInput() {
    if (qIdx && qIdx >= 32) {
        return;
    }
    const el = document.getElementById('userInput');
    el.disabled = false;
    el.parentElement.style.opacity = '1';
}

function disableUserInput(opacity = 0.3) {
    const el = document.getElementById('userInput');
    el.disabled = true;
    el.parentElement.style.opacity = opacity;
}

// Reveal a message one word at a time, fading each in.
function typeMessage(message, speed = typingSpeed, completion = null) {
    const messages = document.querySelectorAll('.ai-message');
    const div = messages[messages.length - 1];

    const words = message.replace(/\n/g, ' <br> ').split(/\s+/);
    const chatMessagesDiv = document.getElementById('chatMessages');
    let index = 0;

    function typeWord() {
        if (index >= words.length) {
            if (completion) completion();
            return;
        }

        const word = words[index];
        if (word === '<br>') {
            div.appendChild(document.createElement('br'));
            index++;
            typeWord();
            return;
        }
        if (word === '') {
            index++;
            typeWord();
            return;
        }

        const wordSpan = document.createElement('span');
        wordSpan.classList.add('fade-in');
        wordSpan.innerHTML = word;
        div.appendChild(wordSpan);

        if (index < words.length - 1) {
            div.appendChild(document.createTextNode(' '));
        }
        chatMessagesDiv.scrollTop = chatMessagesDiv.scrollHeight;

        index++;
        if (index < words.length) {
            setTimeout(typeWord, speed);
        } else if (completion) {
            completion();
        }
    }

    typeWord();
}

function updateInputPlaceholder() {
    scrollTop();
}
