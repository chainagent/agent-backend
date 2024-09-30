import os
import subprocess
import json
import asyncio
import sys

# Add the backend directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from llama_deploy import deploy_workflow, WorkflowServiceConfig, ControlPlaneConfig
from llama_deploy_app.workflows.agent_workflow import AgentWorkflow
from llama_deploy_app.workflows.xmtp_integration import create_mpc_wallet, setup_xmtp_client, register_xmtp_identity

ADMIN_AGENT_NAME = "llama-deploy-admin-agent"
GROUP_CHAT_ID_FILE = "group_chat_id.txt"
ADMIN_WALLET_FILE = "admin_wallet.json"

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    if process.returncode != 0:
        print(f"Error executing command: {command}")
        print(error.decode('utf-8'))
        return False, error.decode('utf-8')
    return True, output.decode('utf-8')

def get_current_instances():
    success, output = run_command("flyctl apps list --json")
    if not success:
        print("Failed to get current apps list")
        return []
    apps = json.loads(output)
    return [app['Name'] for app in apps if app['Name'].startswith('llama-deploy-')]

def get_or_create_group_chat_id():
    if os.path.exists(GROUP_CHAT_ID_FILE):
        with open(GROUP_CHAT_ID_FILE, 'r') as f:
            return f.read().strip()
    else:
        group_id = f"group-{os.urandom(8).hex()}"
        with open(GROUP_CHAT_ID_FILE, 'w') as f:
            f.write(group_id)
        return group_id

def get_or_create_admin_wallet():
    if os.path.exists(ADMIN_WALLET_FILE):
        with open(ADMIN_WALLET_FILE, 'r') as f:
            return json.load(f)
    else:
        private_key, address = create_mpc_wallet()
        admin_wallet = {"private_key": private_key, "address": address}
        with open(ADMIN_WALLET_FILE, 'w') as f:
            json.dump(admin_wallet, f)
        return admin_wallet

async def deploy_admin_agent():
    print("Deploying admin agent...")
    
    control_plane_config = ControlPlaneConfig()
    workflow_config = WorkflowServiceConfig(
        host="0.0.0.0", 
        port=8002, 
        service_name=ADMIN_AGENT_NAME
    )
    
    group_id = get_or_create_group_chat_id()
    admin_wallet = get_or_create_admin_wallet()
    
    xmtp_client = setup_xmtp_client(admin_wallet["private_key"])
    register_xmtp_identity(xmtp_client, admin_wallet["private_key"])
    
    workflow = AgentWorkflow()
    await workflow.initialize(group_id, xmtp_client, admin_wallet["address"])
    
    # Deploy to Fly.io
    os.chdir('backend/llama_deploy_app')
    success, _ = run_command(f"flyctl launch --no-deploy --name {ADMIN_AGENT_NAME}")
    if not success:
        print(f"Failed to launch {ADMIN_AGENT_NAME}")
        return False
    
    success, _ = run_command(f"flyctl deploy --app {ADMIN_AGENT_NAME}")
    if not success:
        print(f"Failed to deploy {ADMIN_AGENT_NAME}")
        return False
    
    os.chdir('../..')
    
    # Deploy workflow
    await deploy_workflow(
        workflow=workflow,
        workflow_config=workflow_config,
        control_plane_config=control_plane_config,
    )
    
    print(f"{ADMIN_AGENT_NAME} deployed successfully")
    return True

async def deploy_new_instance(instance_number):
    app_name = f"llama-deploy-agent-{instance_number}"
    print(f"Deploying {app_name}...")
    
    control_plane_config = ControlPlaneConfig()
    workflow_config = WorkflowServiceConfig(
        host="0.0.0.0", 
        port=8002, 
        service_name=app_name
    )
    
    group_id = get_or_create_group_chat_id()
    private_key, address = create_mpc_wallet()
    xmtp_client = setup_xmtp_client(private_key)
    register_xmtp_identity(xmtp_client, private_key)
    
    workflow = AgentWorkflow()
    await workflow.initialize(group_id, xmtp_client, address)
    
    # Deploy to Fly.io
    os.chdir('backend/llama_deploy_app')
    success, _ = run_command(f"flyctl launch --no-deploy --name {app_name}")
    if not success:
        print(f"Failed to launch {app_name}")
        return False
    
    success, _ = run_command(f"flyctl deploy --app {app_name}")
    if not success:
        print(f"Failed to deploy {app_name}")
        return False
    
    os.chdir('../..')
    
    # Deploy workflow
    await deploy_workflow(
        workflow=workflow,
        workflow_config=workflow_config,
        control_plane_config=control_plane_config,
    )
    
    # Admin agent sends invite to the group chat
    admin_wallet = get_or_create_admin_wallet()
    admin_xmtp_client = setup_xmtp_client(admin_wallet["private_key"])
    await admin_xmtp_client.conversations.create(address)
    conversation = admin_xmtp_client.conversations.get_conversation_by_id(group_id)
    await conversation.send(f"Welcome, agent {app_name}! You've been invited to the group chat.")
    
    print(f"{app_name} deployed successfully and invited to the group chat")
    return True

async def main():
    current_instances = get_current_instances()
    
    # Check if admin agent exists, if not, create it
    if ADMIN_AGENT_NAME not in current_instances:
        if not await deploy_admin_agent():
            print("Failed to deploy admin agent. Exiting.")
            return
    
    instance_numbers = [int(name.split('-')[-1]) for name in current_instances if name.split('-')[-1].isdigit()]
    next_instance = max(instance_numbers + [-1]) + 1

    print(f"Deploying new instance: {next_instance}")
    if await deploy_new_instance(next_instance):
        print(f"\nNew instance {next_instance} deployed successfully!")
        print(f"Connection Information:")
        print(f"Agent: https://llama-deploy-agent-{next_instance}.fly.dev")
        print(f"Admin Agent: https://{ADMIN_AGENT_NAME}.fly.dev")
        print(f"Group Chat ID: {get_or_create_group_chat_id()}")
    else:
        print("Deployment failed.")

if __name__ == "__main__":
    asyncio.run(main())