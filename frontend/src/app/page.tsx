"use client";

import { FormEvent, useState } from "react";

type Message = { role: "user" | "assistant"; content: string };

const categories = ["VPN", "Password", "Wi-Fi", "Apps", "Printer", "Email", "Security"];

export default function Home() {
  const [category, setCategory] = useState("VPN");
  const [message, setMessage] = useState("");
  const [sessionId, setSessionId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || loading) return;
    setMessages((current) => [...current, { role: "user", content: text }]);
    setMessage("");
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, category, session_id: sessionId })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "The support service is unavailable.");
      setSessionId(data.session_id);
      setMessages((current) => [...current, { role: "assistant", content: data.response }]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: error instanceof Error ? error.message : "The support service is unavailable." }
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">✦</span><span>SupportPilot <b>AI</b></span></div>
        <p className="eyebrow">ISSUE CATEGORIES</p>
        <nav aria-label="Issue categories">
          {categories.map((item) => (
            <button className={item === category ? "category active" : "category"} key={item} onClick={() => setCategory(item)}>
              {item}
            </button>
          ))}
        </nav>
        <p className="sidebar-note">Grounded answers from your IT knowledge base.</p>
      </aside>
      <section className="conversation">
        <header><div><p className="eyebrow">IT SUPPORT AGENT</p><h1>How can we help?</h1></div><span className="status">● Online</span></header>
        <div className="messages">
          {messages.length === 0 && <div className="welcome"><h2>Welcome to SupportPilot</h2><p>Describe an IT issue and I&apos;ll guide you through the next best step.</p></div>}
          {messages.map((item, index) => <div className={`message ${item.role}`} key={`${item.role}-${index}`}><span>{item.role === "user" ? "You" : "SupportPilot"}</span><p>{item.content}</p></div>)}
          {loading && <div className="message assistant"><span>SupportPilot</span><p>Thinking…</p></div>}
        </div>
        <form className="composer" onSubmit={sendMessage}>
          <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder={`Describe your ${category} issue…`} rows={3} />
          <button type="submit" disabled={loading || !message.trim()}>Send</button>
        </form>
      </section>
    </main>
  );
}
