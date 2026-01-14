const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");

// chat-д мессеж нэмэх
function addMessage(text, sender) {
    const messageDiv = document.createElement("div");
    messageDiv.classList.add("message", sender);
    messageDiv.innerText = text;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// хэрэглэгчийн мессеж илгээх
function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return; // Хоосон мессеж илгээхгүй

    addMessage(message, "user");
    userInput.value = "";

    fetch("http://localhost:5005/webhooks/rest/webhook", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            sender: "user123", // Хэрэглэгчийн ID-г хүссэнээр сольж болно
            message: message
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Серверээс хариу ирсэнгүй");
        }
        return response.json();
    })
    .then(data => {
        if (data.length === 0) {
            addMessage("Бот хариулт өгөөгүй байна.", "bot");
        } else {
            data.forEach(item => {
                if (item.text) {
                    addMessage(item.text, "bot");
                }
            });
        }
    })
    .catch(error => {
        console.error("Алдаа:", error);
        addMessage("Алдаа гарлаа. Rasa сервер ажиллаж байна уу?", "bot");
    });
}

// Enter товч дарахад мессеж илгээх
userInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
        e.preventDefault();  // Дахин шугам нэмэгдэхээс сэргийлэх
        sendMessage();
    }
});
