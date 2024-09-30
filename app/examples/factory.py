import logging
from typing import List, Optional
from llama_deploy_app.workflows.agent_workflow import AgentWorkflow, build_agentic_workflow
from llama_deploy_app.workflows.rag_workflow import RAGWorkflow

from llama_index.core.workflow import Workflow
from llama_index.core.chat_engine.types import ChatMessage

import os

logger = logging.getLogger("uvicorn")

def create_agent(chat_history: Optional[List[ChatMessage]] = None, workflow_type: str = "agent") -> Workflow:
    agent_type = os.getenv("EXAMPLE_TYPE", "").lower()
    
    if workflow_type == "rag":
        return RAGWorkflow(chat_history=chat_history)
    
    match agent_type:
        case "agentic":
            rag_workflow = RAGWorkflow(chat_history=chat_history)
            agent = build_agentic_workflow(rag_workflow)
        case _:
            agent = AgentWorkflow(chat_history=chat_history)

    logger.info(f"Using agent pattern: {agent_type}")

    return agent
