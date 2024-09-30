from logging import getLogger
from typing import List, Dict, Any
import asyncio

from llama_index.core.llms import ChatMessage, OpenAI
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Event, Workflow, StartEvent, StopEvent, step
from llama_index.core.tools import FunctionTool

from .rag_workflow import RAGWorkflow
from .xmtp_integration import create_mpc_wallet, setup_xmtp_client, register_xmtp_identity, listen_to_group_chat

logger = getLogger(__name__)

class ChatEvent(Event):
    chat_history: List[ChatMessage]

class AgentWorkflow(Workflow):
    llm: OpenAI = OpenAI(model="gpt-4")

    def __init__(self):
        super().__init__()
        self.xmtp_client = None
        self.agent_address = None
        self.message_queue = asyncio.Queue()
        self.rag_workflow = RAGWorkflow()
        self.mpc_wallet = None
        self.group_id = None

    async def initialize(self, group_id: str):
        private_key, address = create_mpc_wallet()
        self.mpc_wallet = address
        self.xmtp_client = setup_xmtp_client(private_key)
        register_xmtp_identity(self.xmtp_client, private_key)
        print(f"Agent initialized with MPC wallet address: {self.mpc_wallet}")

        self.group_id = group_id
        self.agent_address = self.mpc_wallet
        asyncio.create_task(listen_to_group_chat(self.xmtp_client, group_id, self.handle_group_message))
        
    async def handle_group_message(self, sender: str, content: str):
        if sender != self.agent_address:
            response = await self.process_message(content)
            await self.send_group_message(response)

    async def process_message(self, message: str) -> str:
        response = await self.rag_workflow.run(query=message)
        return str(response)

    async def send_group_message(self, message: str):
        conversation = self.xmtp_client.conversations.get_conversation_by_id(self.group_id)
        await conversation.send(message)

    async def get_group_messages(self):
        messages = []
        while not self.message_queue.empty():
            messages.append(await self.message_queue.get())
        return messages

    @step
    def prepare_chat_history(self, ev: StartEvent) -> ChatEvent:
        logger.info(f"Preparing chat history: {ev}")
        chat_history_dicts = ev.get("chat_history_dicts", [])
        chat_history = [
            ChatMessage(**chat_history_dict) for chat_history_dict in chat_history_dicts
        ]

        newest_msg = ev.get("user_input")
        if not newest_msg:
            raise ValueError("No `user_input` input provided!")

        chat_history.append(ChatMessage(role="user", content=newest_msg))

        memory = ChatMemoryBuffer.from_defaults(
            chat_history=chat_history,
            llm=OpenAI(model="gpt-4"),
        )

        processed_chat_history = memory.get()

        return ChatEvent(chat_history=processed_chat_history)

    @step
    async def chat(self, ev: ChatEvent) -> StopEvent:
        chat_history = ev.chat_history

        async def run_query(query: str) -> str:
            response = await self.rag_workflow.run(query=query)
            return str(response)

        async def return_response(response: str) -> str:
            return response

        query_tool = FunctionTool.from_defaults(async_fn=run_query)
        response_tool = FunctionTool.from_defaults(async_fn=return_response)

        response = await self.llm.apredict_and_call(
            [query_tool, response_tool],
            chat_history=chat_history,
            error_on_no_tool_call=False,
        )

        logger.info(f"Response: {response.response}")

        if self.xmtp_client:
            conversation = self.xmtp_client.conversations.get_conversation_by_id(self.group_id)
            await conversation.send(response.response)

        return StopEvent(result=response.response)

    async def run(self, user_input: str, chat_history: List[Dict[str, str]] = None, streaming: bool = False) -> Dict[str, Any]:
        chat_history_dicts = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (chat_history or [])
        ]

        start_event = StartEvent(
            user_input=user_input,
            chat_history_dicts=chat_history_dicts,
        )

        chat_event = self.prepare_chat_history(start_event)
        stop_event = await self.chat(chat_event)

        return {
            "response": stop_event.result,
            "sources": [],  # Add sources if available
        }
