import asyncio
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.agent_execution import AgentExecutor, RequestContext, EventQueue
from a2a.types import AgentCard, AgentSkill, AgentCapabilities
from a2a.utils.message import new_agent_text_message


# ---- Simple in-memory fake flight DB ----
FLIGHTS = {
    "6E-101": {
        "status": "On Time",
        "from": "DEL",
        "to": "BLR",
        "departure": "14:30",
        "arrival": "16:45",
    },
    "6E-202": {
        "status": "Delayed",
        "from": "BOM",
        "to": "CCU",
        "departure": "18:10",
        "arrival": "20:55",
        "delay_reason": "Weather congestion over eastern sector",
    },
}


class FlightInfoAgent:
    async def get_status(self, flight_number: str) -> str:
        data = FLIGHTS.get(flight_number.upper())
        if not data:
            return f"Flight {flight_number} not found in the demo system."

        base = (
            f"Flight {flight_number} from {data['from']} to {data['to']} "
            f"is currently {data['status']}."
        )
        if "departure" in data and "arrival" in data:
            base += f" Scheduled departure {data['departure']}, arrival {data['arrival']}."
        if "delay_reason" in data:
            base += f" Delay reason: {data['delay_reason']}."
        return base


class FlightInfoExecutor(AgentExecutor):
    """Implements the A2A AgentExecutor interface."""

    def __init__(self) -> None:
        self.agent = FlightInfoAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # For demo, read flight number from message text.
        user_msg = context.request.params.message.parts[0].text  # type: ignore[attr-defined]

        # Expect something like: "status 6E-101"
        parts = user_msg.strip().split()
        flight_number = parts[-1] if parts else "6E-101"

        text = await self.agent.get_status(flight_number)
        await event_queue.enqueue_event(new_agent_text_message(text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # No long-running jobs in this simple demo.
        return


def build_server() -> A2AStarletteApplication:
    skill = AgentSkill(
        id="flight_status",
        name="Flight status lookup",
        description="Returns current status for a given Indigo flight number.",
        tags=["flight", "indigo", "status"],
        examples=["status 6E-101", "flight status 6E-202"],
    )

    card = AgentCard(
        name="IndiGo Flight Info Agent",
        description="Demo A2A agent that returns Indigo flight status.",
        url="http://localhost:8001/",
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    handler = DefaultRequestHandler(
        agent_executor=FlightInfoExecutor(),
        task_store=InMemoryTaskStore(),
    )

    return A2AStarletteApplication(
        agent_card=card,
        http_handler=handler,
    )


if __name__ == "__main__":
    server_app = build_server()
    uvicorn.run(server_app.build(), host="0.0.0.0", port=8001)
