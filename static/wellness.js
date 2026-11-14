(() => {
  const quotes = [
    { text: "You do not have to do everything today. Just take the next small step.", author: "MindEase reminder" },
    { text: "Progress is still progress, even when it feels slow.", author: "A gentle reminder" },
    { text: "You deserve the same patience and kindness you give to others.", author: "MindEase reminder" },
    { text: "Rest is not a reward you have to earn. It is part of caring for yourself.", author: "A gentle reminder" },
    { text: "One difficult day does not define your whole journey.", author: "MindEase reminder" },
    { text: "You are allowed to begin again, as many times as you need.", author: "A gentle reminder" },
    { text: "Small steps taken consistently can lead to meaningful change.", author: "MindEase reminder" },
    { text: "Your worth is not measured by your productivity.", author: "MindEase reminder" },
    { text: "Take a breath. You can meet this moment one step at a time.", author: "A gentle reminder" }
  ];
  const quoteEl = document.getElementById("dailyQuote");
  const authorEl = document.getElementById("quoteAuthor");
  const button = document.getElementById("newQuoteBtn");
  if (!quoteEl || !authorEl || !button) return;

  let current = -1;
  function showAnotherQuote() {
    let next = Math.floor(Math.random() * quotes.length);
    if (quotes.length > 1) while (next === current) next = Math.floor(Math.random() * quotes.length);
    current = next;
    quoteEl.textContent = "“" + quotes[current].text + "”";
    authorEl.textContent = "— " + quotes[current].author;
  }
  button.addEventListener("click", showAnotherQuote);
  showAnotherQuote();
})();
