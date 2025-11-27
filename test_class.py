import { useState } from "react";

export default function App() {
  const [flightNumber, setFlightNumber] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [directResult, setDirectResult] = useState(null);

  const handleSupportRequest = () => {
    const evt = new EventSource("http://localhost:8000/tasks/send", {
      method: "POST"
    });

    fetch("http://localhost:8000/tasks/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "support1",
        method: "support_chat",
        params: { flight_number: flightNumber }
      }),
    });

    evt.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.progress) {
        setChatMessages((prev) => [...prev, `Progress: ${data.message}`]);
      } else if (data.text) {
        setChatMessages((prev) => [...prev, data.text]);
      }
    };
  };

  const callFlightAgentDirect = async () => {
    const res = await fetch("http://localhost:8001/tasks/send", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "test1",
        method: "get_flight_status",
        params: { flight_number: flightNumber }
      })
    });

    const out = await res.json();
    setDirectResult(out.result);
  };

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {/* Left Side - Passenger Support */}
      <div style={{ flex: 1, padding: 20, borderRight: "1px solid gray" }}>
        <h2>Passenger Support</h2>
        <input
          placeholder="Enter flight number"
          onChange={(e) => setFlightNumber(e.target.value)}
        />
        <button onClick={handleSupportRequest}>Request Support</button>

        <div style={{ marginTop: 20 }}>
          {chatMessages.map((m, i) => <p key={i}>{m}</p>)}
        </div>
      </div>

      {/* Right Side - Flight Agent Direct */}
      <div style={{ flex: 1, padding: 20 }}>
        <h2>Flight Info Agent</h2>
        <input
          placeholder="Enter flight number"
          onChange={(e) => setFlightNumber(e.target.value)}
        />
        <button onClick={callFlightAgentDirect}>Get Status</button>

        {directResult && (
          <pre style={{ background: "#eee", marginTop: 20 }}>
            {JSON.stringify(directResult, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
