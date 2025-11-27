import asyncio
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import requests

from a2a_sdk.server import A2AServer, AgentCard, Skill
from a2a_sdk.messages import (
    TaskRequest, TaskResponse, TaskEvent,
    new_agent_text_message
)

load_dotenv()

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION")
)

deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
FLIGHT_AGENT_URL = "http://localhost:8001"

agent_card = AgentCard(
    name="passenger_support_agent",
    version="1.0.0",
    description="Passenger support agent providing flight information responses.",
    url="http://localhost:8000",
    skills=[Skill(
        id="support_chat",
        name="Passenger Support Chat",
        description="Provides professional support messaging."
    )]
)

async def stream_to_client(event_queue, req_id, flight_no):
    await event_queue.put(TaskEvent.progress(
        req_id, progress=10, message="Searching for flight information..."
    ))

    info = requests.post(
        FLIGHT_AGENT_URL + "/tasks/send",
        json={
            "jsonrpc": "2.0",
            "id": "req_flight",
            "method": "get_flight_status",
            "params": {"flight_number": flight_no}
        }
    ).json()

    await event_queue.put(TaskEvent.progress(
        req_id, progress=60,
        message="Flight information received. Preparing response..."
    ))

    data = info.get("result", {})
    if "error" in data:
        final_text = "The requested flight information is not available."
    else:
        prompt = f"""
        Convert the following JSON flight data into a short professional message:
        {data}
        """

        response_stream = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )

        await event_queue.put(TaskEvent.progress(
            req_id, progress=90,
            message="Sending response..."
        ))

        async for chunk in response_stream:
            token = chunk.choices[0].delta.content if chunk.choices[0].delta else ""
            if token:
                await event_queue.put(
                    new_agent_text_message(req_id, token)
                )

    await event_queue.put(TaskEvent.completed(req_id))

async def handle_task(req: TaskRequest):
    flight_no = req.params.get("flight_number")

    event_queue = asyncio.Queue()
    asyncio.create_task(stream_to_client(event_queue, req.id, flight_no))

    return TaskResponse.streaming(req.id, event_queue)

def run():
    server = A2AServer(agent_card, handle_task)
    asyncio.run(server.serve(host="0.0.0.0", port=8000))

if __name__ == "__main__":
    run()
