import os
from typing import Dict, Any, List
import asyncio

from llama_deploy import LlamaDeployApp, LlamaDeployService, deploy_workflow, WorkflowServiceConfig, ControlPlaneConfig
from agent_workflow import AgentWorkflow

app = LlamaDeployApp()

@app.service("agent_workflow")
class AgentWorkflowService(LlamaDeployService):
    async def initialize(self):
        workflow = AgentWorkflow()
        await workflow.initialize(None)  # Pass None as StartEvent
        return workflow

async def deploy_agent():
    control_plane_config = ControlPlaneConfig()
    
    workflow_config = WorkflowServiceConfig(
        host="0.0.0.0", 
        port=8002, 
        service_name="agent_workflow"
    )
    
    workflow = await AgentWorkflowService().initialize()
    
    await deploy_workflow(
        workflow=workflow,
        workflow_config=workflow_config,
        control_plane_config=control_plane_config,
    )

if __name__ == "__main__":
    asyncio.run(deploy_agent())
