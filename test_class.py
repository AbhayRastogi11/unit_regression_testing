import asyncio
import os
from dotenv import load_dotenv
from a2a_sdk.server import A2AServer, AgentCard, Skill
from a2a_sdk.messages import TaskRequest, TaskResponse

load_dotenv()

flight_data = {
    "6E-123": {
        "status": "On Time",
        "from": "DEL",
        "to": "BLR",
        "departure": "14:30",
        "arrival": "16:45"
    },
    "6E-456": {
        "status": "Delayed",
        "from": "BOM",
        "to": "DEL",
        "departure": "15:00",
        "arrival": "17:15"
    }
}

agent_card = AgentCard(
    name="flight_info_agent",
    version="1.0.0",
    description="Provides flight schedule/status information.",
    url="http://localhost:8001",
    skills=[Skill(
        id="get_flight_status",
        name="Get Flight Status",
        description="Return flight status information as JSON."
    )]
)

async def handle_task(req: TaskRequest):
    if req.method != "get_flight_status":
        return TaskResponse.error(req.id, "Unknown method")

    flight_no = req.params.get("flight_number")
    info = flight_data.get(flight_no)

    if not info:
        return TaskResponse.completed(req.id, result={"error": "Flight not found"})

    return TaskResponse.completed(req.id, result=info)

def run():
    server = A2AServer(agent_card, handle_task)
    asyncio.run(server.serve(host="0.0.0.0", port=8001))

if __name__ == "__main__":
    run()
