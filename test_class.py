import asyncio
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import requests

from a2a_sdk.server import A2AServer, AgentCard, Skill
from a2a_sdk.messages import TaskRequest, TaskResponse

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
    description="Passenger support agent providing professional flight information responses.",
    url="http://localhost:8000",
    skills=[Skill(
        id="support_chat",
        name="Passenger Support Chat",
        description="Provides professional support messaging."
    )]
)

async def handle_task(req: TaskRequest):
    if req.method != "support_chat":
        return TaskResponse.error(req.id, "Unknown method")

    flight_no = req.params.get("flight_number")

    # 1) Call Flight Info Agent
    flight_resp = requests.post(
        FLIGHT_AGENT_URL + "/tasks/send",
        json={
            "jsonrpc": "2.0",
            "id": "req_flight",
            "method": "get_flight_status",
            "params": {"flight_number": flight_no}
        },
        timeout=5
    ).json()

    data = flight_resp.get("result", {})

    # 2) If not found, simple message
    if "error" in data:
        final_text = "The requested flight information is not available."
    else:
        # 3) Ask GPT-4o to write a short professional message
        prompt = f"""
You are an airline support assistant.
Convert the following JSON flight data into a short, clear, professional message
for the passenger. Do NOT add emojis. Keep it 1–2 sentences.

Flight data:
{data}
"""

        completion = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        final_text = completion.choices[0].message.content.strip()

    # 4) Return normal (non-streaming) response
    return TaskResponse.completed(
        req.id,
        result={
            "flight_number": flight_no,
            "message": final_text,
            "raw_data": data
        }
    )

def run():
    server = A2AServer(agent_card, handle_task)
    asyncio.run(server.serve(host="0.0.0.0", port=8000))

if __name__ == "__main__":
    run()
