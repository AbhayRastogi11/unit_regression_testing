# flight_agent.py
import asyncio
from a2a_sdk.server import A2AServer, AgentCard, Skill
from a2a_sdk.messages import TaskRequest, TaskResponse

# 1. Define AgentCard metadata
agent_card = AgentCard(
    name="flight_info_agent",
    version="1.0.0",
    description="Provides flight status information for Indigo-style flights (demo)",
    url="http://0.0.0.0:8000",  # will be served at root
    skills=[
        Skill(
            id="get_flight_status",
            name="Get Flight Status",
            description="Return status info for a flight number (e.g. 6E-123)"
        )
    ]
)

# 2. Define handler for tasks
async def handle_task(req: TaskRequest) -> TaskResponse:
    method = req.method
    if method == "get_flight_status":
        params = req.params or {}
        flight_no = params.get("flight_number")
        # stub hard-coded data; replace with real DB/API in real use-case
        demo_data = {
            "6E-123": {"status": "On Time", "departure": "2025-11-28T14:30:00", "arrival": "2025-11-28T16:45:00"},
            "6E-456": {"status": "Delayed", "departure": "2025-11-28T15:00:00", "arrival": "2025-11-28T17:15:00"},
        }
        info = demo_data.get(flight_no, {"status": "Unknown", "departure": None, "arrival": None})
        result = {
            "flight_number": flight_no,
            "info": info
        }
        return TaskResponse.completed(req.id, result=result)
    else:
        return TaskResponse.error(req.id, code=-32601, message=f"Unknown method: {method}")

# 3. Start server
def main():
    server = A2AServer(agent_card, handle_task)
    # By default, server will serve agent card at /.well-known/agent-card.json
    # and accept tasks at /tasks/send
    asyncio.run(server.serve(host="0.0.0.0", port=8000))

if __name__ == "__main__":
    main()
