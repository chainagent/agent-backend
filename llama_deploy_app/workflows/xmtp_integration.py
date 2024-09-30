import os
from typing import Tuple
from dotenv import load_dotenv
from coinbase import Coinbase, Wallet
from xmtp_mls_client import Client as XMTPClient
from eth_account import Account

load_dotenv()

def create_mpc_wallet() -> Tuple[str, str]:
    coinbase = Coinbase()
    wallet = coinbase.create_wallet(name="Agent MPC Wallet")
    private_key = wallet.private_key
    address = wallet.address
    return private_key, address

def fund_wallet_with_faucet(wallet: Wallet):
    try:
        wallet.faucet()
        print(f"Wallet {wallet.address} funded with faucet")
    except Exception as e:
        print(f"Failed to fund wallet with faucet: {str(e)}")

def setup_xmtp_client(private_key: str) -> XMTPClient:
    account = Account.from_key(private_key)
    xmtp_client = XMTPClient.create(account.address, env="production")
    return xmtp_client

def register_xmtp_identity(client: XMTPClient, private_key: str):
    account = Account.from_key(private_key)
    signature = account.sign_message(client.signature_text)
    client.add_ecdsa_signature(signature)
    client.register_identity()

def join_group_chat(client: XMTPClient, group_id: str):
    conversation = client.conversations.get_conversation_by_id(group_id)
    if conversation:
        conversation.join()
        print(f"Group chat with ID {group_id} joined")
    else:
        raise ValueError(f"Group chat with ID {group_id} not found")

async def create_agent_with_xmtp(group_id: str) -> Tuple[str, XMTPClient]:
    private_key, address = create_mpc_wallet()

    # Fund the wallet with faucet
    coinbase = Coinbase()
    wallet = coinbase.get_wallet(address)
    fund_wallet_with_faucet(wallet)

    xmtp_client = setup_xmtp_client(private_key)
    register_xmtp_identity(xmtp_client, private_key)
    join_group_chat(xmtp_client, group_id)
    return address, xmtp_client

async def listen_to_group_chat(client: XMTPClient, group_id: str, message_handler):
    conversation = client.conversations.get_conversation_by_id(group_id)
    async for message in conversation.stream():
        await message_handler(message.sender_address, message.content)
