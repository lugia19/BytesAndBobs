// ==UserScript==
// @name         Gemini exporter
// @namespace    lugia19.com
// @version      0.4
// @description  Export messages from Gemini share links into tavern/ooba format
// @author       lugia19
// @match        https://gemini.google.com/share/*
// @grant        none
// ==/UserScript==

//Data conversion stuff
function extractConversationGemini() {
    const messages = [];
    // Collect all user and assistant messages
    const userQueries = document.querySelectorAll('user-query .query-text');
    const assistantResponses = document.querySelectorAll('response-container .message-content');

    for (let i = 0; i < userQueries.length || i < assistantResponses.length; i++) {
        if (userQueries[i]) {
            messages.push({
                parent: "",
                message: {
                    author: {
                        role: "user"
                    },
                    create_time: getCurrentUnixTimestamp(),
                    content: {
                        parts: [userQueries[i].textContent.trim()]
                    }
                }
            });
        }
        if (assistantResponses[i]) {
            messages.push({
                parent: "",
                message: {
                    author: {
                        role: "assistant"
                    },
                    create_time: getCurrentUnixTimestamp(),
                    content: {
                        parts: [assistantResponses[i].textContent.trim()]
                    }
                }
            });
        }
    }

    return messages;
}

function convertMessageToTavern(messageData) {
    if (!messageData.message) {
        return null;
    }

    const senderRole = messageData.message.author.role;
    if (senderRole === 'system') {
        return null;
    }

    const isAssistant = senderRole === 'assistant';
    const createTime = messageData.message.create_time;
    const text = messageData.message.content.parts[0];

    return {
        name: isAssistant ? 'Assistant' : 'You',
        is_user: !isAssistant,
        is_name: isAssistant,
        send_date: createTime,
        mes: text,
        swipes: [text],
        swipe_id: 0,
    };
}

function jsonlStringify(messageArray) {
    return messageArray.map(msg => JSON.stringify(msg)).join('\n');
}

function getTavernString() {
    const conversation = extractConversationGemini();

    const convertedConvo = [{
        user_name: 'You',
        character_name: 'Assistant',
    }];

    conversation.forEach((message) => {
        const convertedMsg = convertMessageToTavern(message);
        if (convertedMsg !== null) {
            convertedConvo.push(convertedMsg);
        }
    });

    return jsonlStringify(convertedConvo);
}

function getOobaString() {
    const messages = extractConversationGemini();
    const pairs = [];
    let idx = 0;

    while (idx < messages.length - 1) {
        const message = messages[idx];
        const nextMessage = messages[idx + 1];
        let role, text, nextRole, nextText;

        if (!message.message || !nextMessage.message) {
            idx += 1;
            continue;
        }

        try {
            role = message.message.author.role;
            text = message.message.content.parts[0];
            nextRole = nextMessage.message.author.role;
            nextText = nextMessage.message.content.parts[0];
        } catch (error) {
            idx += 1;
            continue;
        }

        if (role === 'system') {
            if (text !== '') {
                pairs.push(['<|BEGIN-VISIBLE-CHAT|>', text]);
            }
            idx += 1;
            continue;
        }

        if (role === 'user') {
            if (nextRole === 'assistant') {
                pairs.push([text, nextText]);
                idx += 2;
                continue;
            } else if (nextRole === 'user') {
                pairs.push([text, '']);
                idx += 1;
                continue;
            }
        }

        if (role === 'assistant') {
            pairs.push(['', text]);
            idx += 1;
        }
    }
    const oobaData = {
        internal: pairs,
        visible: JSON.parse(JSON.stringify(pairs)),
    };

    if (oobaData.visible[0] && oobaData.visible[0][0] === '<|BEGIN-VISIBLE-CHAT|>') {
        oobaData.visible[0][0] = '';
    }

    return JSON.stringify(oobaData, null, 2);
}


// Function to get current Unix timestamp in milliseconds
function getCurrentUnixTimestamp() {
    return Math.floor(Date.now());
}


// Function to download data as JSON (Shamelessly copied from ChatGPT-Exporter)
function downloadFile(filename, type, content) {
    const blob = content instanceof Blob ? content : new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
}

// Create and style button
const menuButton = document.createElement('button');
menuButton.textContent = 'Export Chatlog';
Object.assign(menuButton.style, {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    zIndex: 1000,
    backgroundColor: '#131314',
    color: 'white',
    border: '1px solid white',
    padding: '10px 20px',
    cursor: 'pointer',
    borderRadius: '5px',
    boxSizing: 'border-box', // Include padding and border in the width
    textAlign: 'center', // Center the text
});

// Create menu container
const menuContainer = document.createElement('div');
Object.assign(menuContainer.style, {
    position: 'fixed',
    bottom: '70px', // Adjusted to not overlap the main button
    right: '20px',
    zIndex: 1001,
    display: 'none', // Initially hidden
    backgroundColor: '#131314',
    borderRadius: '0px',
    boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
});

// Function to toggle menu display
function toggleMenu() {
    menuContainer.style.display = menuContainer.style.display === 'none' ? 'block' : 'none';
}

// Add click event listener to menu button
menuButton.addEventListener('click', toggleMenu);

// Add buttons to the menu
['Tavern', 'Ooba'].forEach(type => {
    const button = document.createElement('button');
    button.textContent = `${type} format`;
    Object.assign(button.style, {
        backgroundColor: '#131314',
        color: 'white',
        border: '1px solid white',
        padding: '10px 20px',
        cursor: 'pointer',
        borderRadius: '5px',
        display: 'block', // Ensure each button is on its own line
        marginTop: '10px', // Space out the buttons
        width: '100%', // Ensure consistent width
        boxSizing: 'border-box', // Include padding and border in the width
        textAlign: 'center', // Center the text
    });
    button.onclick = function () {
        let title = document.title.replace(/^\W+/, '').trim().replace(/\s+/g, '_');
        if (type === 'Tavern') {
            const resultString = getTavernString();
            downloadFile(`${title}_tavern.jsonl`, 'application/json', resultString);
        } else if (type === 'Ooba') {
            const resultString = getOobaString();
            downloadFile(`${title}_ooba.json`, 'application/json', resultString);
        } else { // JSON
            const resultString = JSON.stringify(extractConversationGemini(), null, 2);
            downloadFile(`${title}.json`, 'application/json', resultString);
        }
        // Optionally close the menu after download
        toggleMenu();
    };
    menuContainer.appendChild(button);
});

// Add menu and menu button to the page
document.body.appendChild(menuButton);
document.body.appendChild(menuContainer);