const input = document.getElementById("question-input");
const sendButton = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");

// Stores the current conversation
let conversationHistory = [];


async function sendQuestion() {
    const question = input.value.trim();

    if (!question) {
        return;
    }

    // Show user message
    const userMessage = document.createElement("div");
    userMessage.className = "message user-message";
    userMessage.textContent = question;
    chatBox.appendChild(userMessage);

    input.value = "";
    sendButton.disabled = true;

    try {
        const response = await fetch("http://127.0.0.1:8000/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                question: question,
                conversation_history: conversationHistory
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Something went wrong.");
        }

        // Show bot answer
        const botMessage = document.createElement("div");
        botMessage.className = "message bot-message";
        botMessage.textContent = data.answer;
        chatBox.appendChild(botMessage);

        // Show sources
        if (data.sources && data.sources.length > 0) {
            const sourceMessage = document.createElement("div");
            sourceMessage.className = "message bot-message";

            let sourceText = "Sources:\n\n";

            data.sources.forEach((source, index) => {
                sourceText += `${index + 1}. Section ${source.section} - ${source.section_title}, `;
                sourceText += `Clause ${source.clause}, Pages ${source.pages}\n`;
            });

            sourceMessage.textContent = sourceText;
            chatBox.appendChild(sourceMessage);
        }

        // Save this conversation turn
        conversationHistory.push({
            role: "user",
            content: question
        });

        conversationHistory.push({
            role: "assistant",
            content: data.answer
        });

    } catch (error) {
        const errorMessage = document.createElement("div");
        errorMessage.className = "message bot-message";
        errorMessage.textContent = "Error: " + error.message;
        chatBox.appendChild(errorMessage);
    }

    sendButton.disabled = false;
    chatBox.scrollTop = chatBox.scrollHeight;
}


sendButton.addEventListener("click", sendQuestion);


input.addEventListener("keydown", function(event) {
    if (event.key === "Enter") {
        sendQuestion();
    }
});