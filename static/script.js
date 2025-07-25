const startMicButton = document.getElementById("startMic");
const languageSelect = document.getElementById("languageSelect");
const shoppingList = document.getElementById("shoppingList");
const suggestionsList = document.getElementById("suggestionsList");
const searchResults = document.getElementById("searchResults");
const statusMessage = document.getElementById("statusMessage");

let recognition;
let listening = false;

if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    statusMessage.textContent = "🎙️ Listening...";
    startMicButton.textContent = "🛑 Stop";
    listening = true;
  };

  recognition.onend = () => {
    statusMessage.textContent = "⏳ Processing...";
    startMicButton.textContent = "🎤 Start Listening";
    listening = false;
  };

  recognition.onerror = (event) => {
    statusMessage.textContent = `⚠️ Error: ${event.error}`;
    listening = false;
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript.trim();
    statusMessage.textContent = `📥 Heard: "${transcript}"`;
    processVoiceCommand(transcript);
  };
} else {
  alert("Speech Recognition not supported. Use Chrome or Edge.");
  startMicButton.disabled = true;
}

startMicButton.addEventListener("click", () => {
  if (listening) {
    recognition.stop();
  } else {
    recognition.lang = languageSelect.value === "es" ? "es-ES" : "en-US";
    recognition.start();
  }
});

function processVoiceCommand(text) {
  const lang = languageSelect.value;

  // First: Send to /voice-command (add/remove intent)
  fetch("/voice-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, lang }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "success") {
        statusMessage.textContent = `✅ ${data.message}`;
        if (data.substitute_suggestions) {
          updateSuggestions(data.substitute_suggestions, "Suggested substitutes:");
        }
        refreshShoppingList();
      } else {
        // If not recognized as add/remove, try search
        statusMessage.textContent = `🤔 Trying search instead...`;
        searchProducts(text, lang);
      }
    })
    .catch((err) => {
      console.error("Error handling command:", err);
      statusMessage.textContent = "❌ Failed to process voice command.";
    });
}

function searchProducts(text, lang) {
  fetch("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, lang }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === "success" && data.found_items.length > 0) {
        updateSearchResults(data.found_items);
        statusMessage.textContent = `🔎 Found ${data.found_items.length} result(s).`;
      } else {
        searchResults.innerHTML = "<li>No results found.</li>";
        statusMessage.textContent = `❌ Nothing found for: "${text}"`;
      }
    })
    .catch((err) => {
      console.error("Search error:", err);
      statusMessage.textContent = "❌ Search failed.";
    });
}

function refreshShoppingList() {
  fetch("/list")
    .then((res) => res.json())
    .then((items) => {
      shoppingList.innerHTML = "";
      if (items.length === 0) {
        shoppingList.innerHTML = "<li>No items yet.</li>";
      } else {
        items.forEach((item) => {
          const li = document.createElement("li");
          li.textContent = `${item.name} (${item.quantity})`;
          shoppingList.appendChild(li);
        });
      }
    });
}

function loadSuggestions() {
  fetch("/suggestions")
    .then((res) => res.json())
    .then((data) => {
      const allSuggestions = [...data.seasonal_suggestions, ...data.frequently_bought];
      updateSuggestions(allSuggestions, "Smart Suggestions:");
    });
}

function updateSuggestions(items, heading = "") {
  suggestionsList.innerHTML = heading ? `<li><strong>${heading}</strong></li>` : "";
  if (items.length === 0) {
    suggestionsList.innerHTML += "<li>No suggestions available.</li>";
  } else {
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      suggestionsList.appendChild(li);
    });
  }
}

function updateSearchResults(results) {
  searchResults.innerHTML = "";
  results.forEach((product) => {
    const li = document.createElement("li");
    li.textContent = `${product.name} (${product.brand}) - $${product.price.toFixed(2)}`;
    searchResults.appendChild(li);
  });
}

// 🔁 Load initial data
refreshShoppingList();
loadSuggestions();
