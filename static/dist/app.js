// DOM Elements
const primaryList = document.getElementById("primary-list");
const lowList = document.getElementById("low-list");
const digestDate = document.getElementById("digest-date");
const primaryCount = document.getElementById("primary-count");
const lowCount = document.getElementById("low-count");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send-btn");
const promptList = document.getElementById("prompt-list");

// State
let digestData = null;
let chatHistory = [];
let cardSwapInstances = [];

// Utilities
const formatDate = (isoDate) => {
  if (!isoDate) return "Today";
  const date = new Date(isoDate);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const escapeHtml = (text) => {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
};

// Card Rendering
const createCard = (item, index) => {
  const card = document.createElement("div");
  card.className = "news-card";
  card.style.animationDelay = `${0.1 + index * 0.05}s`;
  card.dataset.id = item.id;

  const credClass = item.credibility_label || "medium";
  const sourceInitials = (item.source || "N/A").substring(0, 2).toUpperCase();

  const tags = (item.tags || [])
    .slice(0, 3)
    .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
    .join("");

  // Default to English
  const currentLang = "en";

  card.innerHTML = `
    <div class="card-header">
      <div class="card-source">
        <div class="source-icon">${sourceInitials}</div>
        <span class="source-name">${escapeHtml(item.source || "Unknown")}</span>
      </div>
      <span class="cred-badge ${credClass}">${credClass}</span>
    </div>
    <div class="card-content">
      <div class="card-title-row">
        <h3 class="card-title">${escapeHtml(item.title || "Untitled")}</h3>
        ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" class="source-link" title="View original source">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
        </a>` : ''}
      </div>
      <p class="card-summary" data-en="${escapeHtml(item.summary_en || "")}" data-zh="${escapeHtml(item.summary_zh || "")}">${escapeHtml(item.summary_en || item.summary_zh || "No summary available")}</p>
      <button class="expand-btn" aria-label="Expand content">
        <span>Show more</span>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      <div class="card-implication" style="display: none;">
        <p class="card-implication-label">Implication</p>
        <p class="card-implication-text" data-en="${escapeHtml(item.implication_en || "")}" data-zh="${escapeHtml(item.implication_zh || "")}">${escapeHtml(item.implication_en || item.implication_zh || "")}</p>
      </div>
    </div>
    <div class="card-footer">
      <div class="tag-row">${tags}</div>
      <div class="lang-toggle">
        <button class="lang-btn active" data-lang="en">EN</button>
        <button class="lang-btn" data-lang="zh">中文</button>
      </div>
    </div>
  `;

  // Language toggle handlers
  const langBtns = card.querySelectorAll(".lang-btn");
  const summary = card.querySelector(".card-summary");
  const implication = card.querySelector(".card-implication-text");

  langBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.dataset.lang;
      langBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      // Update summary
      const summaryText = summary.dataset[lang] || summary.dataset.en || "";
      summary.textContent = summaryText || "No summary available";

      // Update implication
      if (implication) {
        const impText = implication.dataset[lang] || implication.dataset.en || "";
        implication.textContent = impText;
      }
    });
  });

  // Expand button handler
  const expandBtn = card.querySelector(".expand-btn");
  const implicationDiv = card.querySelector(".card-implication");

  expandBtn.addEventListener("click", () => {
    const isExpanded = summary.classList.toggle("expanded");
    expandBtn.classList.toggle("expanded", isExpanded);
    expandBtn.querySelector("span").textContent = isExpanded ? "Show less" : "Show more";
    implicationDiv.style.display = isExpanded ? "block" : "none";
  });

  return card;
};

const renderList = (container, items) => {
  container.innerHTML = "";
  
  // Clear any existing CardSwap instances for this container
  const existingInstance = cardSwapInstances.find(inst => inst.container === container);
  if (existingInstance) {
    existingInstance.instance.destroy();
    cardSwapInstances = cardSwapInstances.filter(inst => inst.container !== container);
  }
  
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="news-card" style="animation: none; opacity: 1;">
        <div class="card-content" style="text-align: center; padding: 40px;">
          <p style="color: var(--text-muted);">No items to display</p>
        </div>
      </div>
    `;
    return;
  }
  
  // For now, render cards in a simple grid until CardSwap is fully debugged
  // We'll use a simpler stacked layout
  container.style.display = 'grid';
  container.style.gridTemplateColumns = 'repeat(auto-fill, minmax(340px, 1fr))';
  container.style.gap = '24px';
  container.style.minHeight = 'auto';
  
  items.forEach((item, idx) => {
    const card = createCard(item, idx);
    container.appendChild(card);
  });
};

// Chat Functions
const addMessage = (content, role = "user") => {
  // Remove welcome message if present
  const welcome = chatMessages.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = role === "assistant" ? formatMarkdown(content) : escapeHtml(content);

  msgDiv.appendChild(bubble);
  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  return msgDiv;
};

const addTypingIndicator = () => {
  const typing = document.createElement("div");
  typing.className = "chat-message assistant";
  typing.id = "typing-indicator";
  typing.innerHTML = `
    <div class="typing-indicator">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  chatMessages.appendChild(typing);
  chatMessages.scrollTop = chatMessages.scrollHeight;
};

const removeTypingIndicator = () => {
  const typing = document.getElementById("typing-indicator");
  if (typing) typing.remove();
};

const formatMarkdown = (text) => {
  // Basic markdown formatting
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
};

const sendMessage = async () => {
  const message = chatInput.value.trim();
  if (!message) return;

  // Add user message
  addMessage(message, "user");
  chatInput.value = "";
  chatInput.style.height = "auto";

  // Add to history
  chatHistory.push({ role: "user", content: message });

  // Show typing indicator
  addTypingIndicator();
  chatSendBtn.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: chatHistory.slice(-10), // Last 10 messages for context
        digest_context: digestData,
      }),
    });

    removeTypingIndicator();

    if (response.ok) {
      const data = await response.json();
      const reply = data.reply || "I apologize, but I couldn't process that request.";
      addMessage(reply, "assistant");
      chatHistory.push({ role: "assistant", content: reply });
    } else {
      // Fallback response when API is not available
      const fallbackReply = generateFallbackResponse(message);
      addMessage(fallbackReply, "assistant");
      chatHistory.push({ role: "assistant", content: fallbackReply });
    }
  } catch (error) {
    removeTypingIndicator();
    // Fallback response
    const fallbackReply = generateFallbackResponse(message);
    addMessage(fallbackReply, "assistant");
    chatHistory.push({ role: "assistant", content: fallbackReply });
  }

  chatSendBtn.disabled = false;
  chatInput.focus();
};

const generateFallbackResponse = (message) => {
  const lowerMsg = message.toLowerCase();
  
  if (!digestData || !digestData.primary || digestData.primary.length === 0) {
    return "I don't have any news digest loaded yet. Please wait for the data to load.";
  }

  const newsCount = digestData.primary.length;
  const titles = digestData.primary.slice(0, 3).map(n => `• ${n.title}`).join("\n");

  if (lowerMsg.includes("summar") || lowerMsg.includes("overview") || lowerMsg.includes("today")) {
    return `**Today's Digest Overview**\n\nI have ${newsCount} stories loaded for you today. Here are some highlights:\n\n${titles}\n\nWould you like me to explain any specific story in more detail?`;
  }

  if (lowerMsg.includes("china") || lowerMsg.includes("us") || lowerMsg.includes("supply")) {
    const relevantNews = digestData.primary.filter(n => 
      (n.summary_en && (n.summary_en.toLowerCase().includes("china") || n.summary_en.toLowerCase().includes("us"))) ||
      (n.tags && n.tags.some(t => t.toLowerCase().includes("politics")))
    );
    if (relevantNews.length > 0) {
      return `**China-US Related Stories**\n\nI found ${relevantNews.length} potentially relevant stories. The key one is: **${relevantNews[0].title}**\n\n${relevantNews[0].implication_en || relevantNews[0].summary_en}`;
    }
    return "I didn't find specific China-US related stories in today's digest, but I recommend checking the political and finance tagged articles.";
  }

  if (lowerMsg.includes("credib") || lowerMsg.includes("corrobor") || lowerMsg.includes("reliable")) {
    return `**Credibility Analysis**\n\nAll ${newsCount} stories in today's digest have been tagged with credibility levels. Most are marked as **medium** credibility based on source reputation and corroboration. For critical decisions, I recommend cross-referencing with primary sources.`;
  }

  if (lowerMsg.includes("invest") || lowerMsg.includes("financ") || lowerMsg.includes("money")) {
    const financeNews = digestData.primary.filter(n => n.tags && n.tags.includes("finance"));
    if (financeNews.length > 0) {
      return `**Finance-Related Stories**\n\nI found ${financeNews.length} finance stories. Top pick:\n\n**${financeNews[0].title}**\n${financeNews[0].implication_en || "Check the implications for investment insights."}`;
    }
  }

  return `I'm here to help you understand today's ${newsCount} stories. I can:\n\n• Summarize the key news\n• Explain implications\n• Find China-US related content\n• Analyze credibility\n• Discuss finance impacts\n\nWhat would you like to know more about?`;
};

// Event Listeners
chatSendBtn.addEventListener("click", sendMessage);

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Auto-resize textarea
chatInput.addEventListener("input", () => {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
});

// Prompt suggestions
promptList.addEventListener("click", (e) => {
  const li = e.target.closest("li");
  if (li && li.dataset.prompt) {
    chatInput.value = li.dataset.prompt;
    chatInput.focus();
    sendMessage();
  }
});

// Fetch and render digest
const loadDigest = async () => {
  try {
    const res = await fetch("/api/digest");
    const data = await res.json();
    digestData = data;

    digestDate.textContent = formatDate(data.date);
    primaryCount.textContent = data.primary ? data.primary.length : 0;
    lowCount.textContent = data.low_credibility ? data.low_credibility.length : 0;

    renderList(primaryList, data.primary);
    renderList(lowList, data.low_credibility);
  } catch (err) {
    digestDate.textContent = "Unable to load digest";
    console.error("Failed to load digest:", err);
  }
};

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    loadDigest();
  });
} else {
  loadDigest();
}
