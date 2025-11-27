import { useState } from "react";

export default function App() {
  const [supportFlight, setSupportFlight] = useState("");
  const [directFlight, setDirectFlight] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [directResult, setDirectResult] = useState(null);
  const [loadingSupport, setLoadingSupport] = useState(false);
  const [loadingDirect, setLoadingDirect] = useState(false);

  const handleSupportRequest = async () => {
    if (!supportFlight) return;
    setLoadingSupport(true);
    setChatMessages((prev) => [
      ...prev,
      `Requesting support for flight ${supportFlight}...`,
    ]);

    try {
      const res = await fetch("/api/support/tasks/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: "support1",
          method: "support_chat",
          params: { flight_number: supportFlight },
        }),
      });

      const data = await res.json();
      const msg =
        data.result?.message || "No response message received from agent.";
      setChatMessages((prev) => [...prev, msg]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        "Error contacting support agent.",
      ]);
    } finally {
      setLoadingSupport(false);
    }
  };

  const callFlightAgentDirect = async () => {
    if (!directFlight) return;
    setLoadingDirect(true);
    setDirectResult(null);

    try {
      const res = await fetch("/api/flight/tasks/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: "test1",
          method: "get_flight_status",
          params: { flight_number: directFlight },
        }),
      });

      const data = await res.json();
      setDirectResult(data.result);
    } catch (err) {
      setDirectResult({ error: "Error contacting flight agent." });
    } finally {
      setLoadingDirect(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "sans-serif" }}>
      {/* LEFT: Passenger Support */}
      <div style={{ flex: 1, padding: 20, borderRight: "1px solid #ccc" }}>
        <h2>Passenger Support</h2>
        <div style={{ marginBottom: 10 }}>
          <input
            placeholder="Enter flight number (e.g., 6E-123)"
            value={supportFlight}
            onChange={(e) => setSupportFlight(e.target.value)}
            style={{ marginRight: 10 }}
          />
          <button onClick={handleSupportRequest} disabled={loadingSupport}>
            {loadingSupport ? "Processing..." : "Request Support"}
          </button>
        </div>

        <div
          style={{
            marginTop: 20,
            padding: 10,
            border: "1px solid #ddd",
            height: "70vh",
            overflowY: "auto",
            background: "#fafafa",
          }}
        >
          {chatMessages.length === 0 && (
            <p style={{ color: "#777" }}>No messages yet.</p>
          )}
          {chatMessages.map((m, i) => (
            <p key={i} style={{ marginBottom: 8 }}>
              {m}
            </p>
          ))}
        </div>
      </div>

      {/* RIGHT: Flight Agent Direct Test */}
      <div style={{ flex: 1, padding: 20 }}>
        <h2>Flight Info Agent</h2>
        <div style={{ marginBottom: 10 }}>
          <input
            placeholder="Enter flight number (e.g., 6E-123)"
            value={directFlight}
            onChange={(e) => setDirectFlight(e.target.value)}
            style={{ marginRight: 10 }}
          />
          <button onClick={callFlightAgentDirect} disabled={loadingDirect}>
            {loadingDirect ? "Loading..." : "Get Status"}
          </button>
        </div>

        <div
          style={{
            marginTop: 20,
            padding: 10,
            border: "1px solid #ddd",
            minHeight: "70vh",
            background: "#fafafa",
            overflowY: "auto",
          }}
        >
          {directResult ? (
            <pre>{JSON.stringify(directResult, null, 2)}</pre>
          ) : (
            <p style={{ color: "#777" }}>No data loaded.</p>
          )}
        </div>
      </div>
    </div>
  );
}
