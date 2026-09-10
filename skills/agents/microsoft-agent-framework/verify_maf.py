"""Verify recipe for the microsoft-agent-framework skill: keyless Entra auth,
Pydantic structured output. Run after `az login`, with AZURE_OPENAI_ENDPOINT,
AZURE_OPENAI_CHAT_COMPLETION_MODEL and AZURE_OPENAI_API_VERSION set.
There is no API key argument, by house rule and by vendor sample.
"""

import asyncio
import os

from agent_framework.openai import OpenAIChatCompletionClient
from azure.identity import AzureCliCredential
from pydantic import BaseModel


class PersonInfo(BaseModel):
    """Information about a person."""

    name: str
    age: int
    occupation: str


async def main() -> None:
    agent = OpenAIChatCompletionClient(
        model=os.environ["AZURE_OPENAI_CHAT_COMPLETION_MODEL"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        credential=AzureCliCredential(),
    ).as_agent(instructions="You extract person information from text.")
    response = await agent.run(
        "Please provide information about John Smith, who is a 35-year-old software engineer.",
        options={"response_format": PersonInfo},
    )
    print("type:", type(response.value).__name__)
    print("value:", response.value)


asyncio.run(main())
