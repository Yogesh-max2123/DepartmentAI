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

        // Convert Gemini's Markdown bold (**text**) into HTML bold tags
        let formattedAnswer = data.answer.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        // textContent ki jagah innerHTML use karein
        botMessage.innerHTML = formattedAnswer;
        chatBox.appendChild(botMessage);

        // Show sources
        if (data.sources && data.sources.length > 0) {
            const sourceMessage = document.createElement("div");
            sourceMessage.className = "message bot-message";

            let sourceText = "Sources:\n\n";

            data.sources.forEach((source, index) => {
                const kind = source.chunk_type || "ordinance_clause";
                sourceText += `${index + 1}. [${kind}] ${source.chunk_id || ""}`.trim();

                if (source.section) {
                    sourceText += ` | Section ${source.section}`;
                    if (source.section_title) {
                        sourceText += `\n${source.section_title}`;
                    }
                }

                if (source.clause) {
                    sourceText += ` | Clause ${source.clause}`;
                }

                if (source.subject) {
                    sourceText += ` | ${source.subject}`;
                }

                if (source.pages) {
                    sourceText += ` | Pages ${source.pages}`;
                }

                sourceText += "\n";
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

        
        checkAndShowMeetingButton(data.answer, "chat-box");

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

// --- MEETING SCHEDULER AUTOMATION INTEGRATION ---

// 1. Propose Meeting
function checkAndShowMeetingButton(llmResponseText, chatBoxId = "chat-box") {
    if (llmResponseText.toLowerCase().includes("initial draft resolution")) {
        const chatBox = document.getElementById(chatBoxId);
        
        const proposeBtn = document.createElement("button");
        proposeBtn.setAttribute("type", "button");
        proposeBtn.innerText = "📅 Propose DMPC Meeting (WhatsApp Mock)";
        proposeBtn.className = "meeting-btn";
        
        proposeBtn.addEventListener("click", async function(e) {
            e.preventDefault();
            e.stopPropagation();
            proposeBtn.innerText = "⏳ Scheduling & Checking Calendars...";
            proposeBtn.disabled = true;
            
            // Dynamic Agenda extraction (pehle 100 characters)
            let dynamicAgenda = "Review of DMPC Case: " + llmResponseText.substring(0, 100).replace(/\n/g, " ") + "...";
            
            try {
                let response = await fetch("http://127.0.0.1:8000/schedule/propose", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        committee_name: "DMPC",
                        date_range: "2026-09-07 to 2026-09-18", // Dates static rakh sakte hain testing ke liye
                        agenda: dynamicAgenda,
                        use_gemini: false 
                    })
                });
                
                let data = await response.json();
                let proposalId = data.proposal_id || (data.proposal && data.proposal.proposal_id) || data.id;
                
                if (!proposalId) return;
                
                proposeBtn.innerText = "✅ Slots Proposed! (Waiting for HoD)";
                
                // Yahan llmResponseText ko aage pass kar rahe hain
                showApproveButton(proposalId, chatBox, llmResponseText); 
                
            } catch (err) {
                proposeBtn.innerText = "❌ Error in Scheduling API";
                console.error(err);
            }
        });
        chatBox.appendChild(proposeBtn);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// 2. Approve Meeting
function showApproveButton(proposalId, chatBox, llmResponseText) {
    const approveBtn = document.createElement("button");
    approveBtn.setAttribute("type", "button");
    approveBtn.innerText = "✅ Approve & Send Official Invites (HoD)";
    approveBtn.className = "approve-btn";
    
    approveBtn.addEventListener("click", async function(e) {
        e.preventDefault();
        e.stopPropagation();
        approveBtn.innerText = "⏳ Generating Emails & .ics files...";
        approveBtn.disabled = true;
        
        try {
            let response = await fetch("http://127.0.0.1:8000/schedule/approve", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    proposal_id: proposalId,
                    approved: true,
                    slot_index: 1, 
                    use_gemini: false
                })
            });
            
            let data = await response.json();
            approveBtn.style.display = "none"; 
            
            const confirmMsg = document.createElement("p");
            confirmMsg.style.color = "green";
            confirmMsg.style.fontWeight = "bold";
            confirmMsg.innerHTML = `System: Meeting scheduled successfully! Ref ID: ${proposalId}`;
            chatBox.appendChild(confirmMsg);
            
            // Yahan llmResponseText ko Minutes function me pass kar rahe hain
            showDraftMinutesButton(proposalId, chatBox, llmResponseText);
            
            chatBox.scrollTop = chatBox.scrollHeight;
            
        } catch (err) {
            approveBtn.innerText = "❌ Error in Approval API";
            console.error(err);
        }
    });
    chatBox.appendChild(approveBtn);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 3. Generate Dynamic AI Minutes
function showDraftMinutesButton(proposalId, chatBox, llmResponseText) {
    const draftBtn = document.createElement("button");
    draftBtn.setAttribute("type", "button");
    draftBtn.innerText = "📝 Simulate Meeting & Draft Minutes (AI)";
    draftBtn.className = "meeting-btn";
    draftBtn.style.backgroundColor = "#8e44ad"; 
    
    draftBtn.addEventListener("click", async function(e) {
        e.preventDefault();
        e.stopPropagation();
        draftBtn.innerText = "⏳ AI is actively drafting minutes...";
        draftBtn.disabled = true;
        
        try {
            let response = await fetch("http://127.0.0.1:8000/schedule/minutes/generate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // Yahan humne pura context backend ko bhej diya!
                body: JSON.stringify({ 
                    proposal_id: proposalId,
                    context_text: llmResponseText 
                })
            });
            
            let data = await response.json();
            draftBtn.style.display = "none"; 
            
            const minutesMsg = document.createElement("div");
            minutesMsg.className = "message bot-message";
            minutesMsg.style.borderLeft = "4px solid #8e44ad";
            
            // Text rendering with bold and new lines
            let formattedMinutes = data.minutes
                .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
                .replace(/\n/g, "<br>");
                
            minutesMsg.innerHTML = formattedMinutes;
            
            chatBox.appendChild(minutesMsg);
            chatBox.scrollTop = chatBox.scrollHeight;
            
        } catch (err) {
            draftBtn.innerText = "❌ Error generating minutes";
            console.error(err);
        }
    });
    chatBox.appendChild(draftBtn);
    chatBox.scrollTop = chatBox.scrollHeight;
}