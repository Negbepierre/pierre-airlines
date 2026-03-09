# agent.py — The Agent's Brain
# ─────────────────────────────────────────────────────────────
# Think of this like a smart manager who:
# 1. Reads the customer's message
# 2. Decides which tool to use
# 3. Uses the tool
# 4. Reads the result
# 5. Decides if it's solved or needs a human
# 6. Replies to the customer
#
# LangGraph manages the STATE — it remembers what happened
# in previous steps so the agent doesn't forget mid-conversation
# ─────────────────────────────────────────────────────────────

import os
from typing import TypedDict, Annotated, Sequence
from dotenv import load_dotenv
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Load the API key — looks 3 folders up from this file to find .env
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ── IMPORT OUR TOOLS ──
from tools import (
    check_booking,
    check_flight_status,
    check_upgrade_availability,
    calculate_compensation,
    rebook_flight,
    create_support_ticket
)

# ── WRAP TOOLS FOR LANGGRAPH ──
# The @tool decorator tells LangGraph:
# "this function is something the agent is allowed to call"
# The docstring is what the AI reads to decide WHEN to use it

@tool
def tool_check_booking(booking_ref: str) -> str:
    """Use this when a customer asks about their booking,
    wants to see their reservation details, or provides
    a booking reference like PR-48291"""
    return check_booking(booking_ref)

@tool
def tool_check_flight_status(flight_number: str) -> str:
    """Use this when a customer asks about a flight status,
    delays, or mentions a flight number like PA2847"""
    return check_flight_status(flight_number)

@tool
def tool_check_upgrade(flight_number: str, cabin_class: str = "Business") -> str:
    """Use this when a customer asks about upgrading
    their seat to Business or First Class"""
    return check_upgrade_availability(flight_number, cabin_class)

@tool
def tool_calculate_compensation(flight_number: str) -> str:
    """Use this when a customer asks about compensation,
    EU261 rights, or what they are owed for a delay"""
    return calculate_compensation(flight_number)

@tool
def tool_rebook_flight(booking_ref: str, flight_number: str) -> str:
    """Use this when a customer wants to rebook or
    change to a different flight due to a delay or cancellation"""
    return rebook_flight(booking_ref, flight_number)

@tool
def tool_create_ticket(
    booking_ref: str,
    issue_type: str,
    description: str,
    priority: str = "Normal"
) -> str:
    """Use this when the issue is too complex to resolve
    automatically — high value refunds, complaints, medical
    needs, or when the customer is very unhappy.
    issue_type options: refund, complaint, medical, legal, baggage"""
    return create_support_ticket(booking_ref, issue_type, description, priority)


# ── THE STATE ──
# This is the agent's memory for one conversation
# add_messages is a special LangGraph function that keeps
# tool calls and tool results correctly paired together
# Think of it like stapling a question to its answer

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# ── THE MODEL ──
tools = [
    tool_check_booking,
    tool_check_flight_status,
    tool_check_upgrade,
    tool_calculate_compensation,
    tool_rebook_flight,
    tool_create_ticket
]

model = ChatAnthropic(
    model="claude-sonnet-4-5",
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
).bind_tools(tools)

SYSTEM_PROMPT = """You are Pierre Assist, the AI support agent for Pierre Airlines.
A luxury premium airline known for exceptional service.

You have access to these tools:
- tool_check_booking: look up any booking by reference
- tool_check_flight_status: check if a flight is delayed or on time
- tool_check_upgrade: check if upgrades are available
- tool_calculate_compensation: calculate EU261 delay compensation
- tool_rebook_flight: move a passenger to a new flight
- tool_create_ticket: escalate to a human specialist

RULES:
1. Always use tools to get real data — never guess flight details
2. Be concise and professional — luxury airline tone
3. If you need a booking ref or flight number, ask for it politely
4. Escalate via tool_create_ticket for: refunds over £500,
   complaints, medical needs, or anything you cannot resolve
5. When you create a ticket always tell the customer the ticket
   number and expected response time
6. Never mention Claude or Anthropic — you are Pierre Assist"""


# ── THE NODES ──

def call_model(state: AgentState) -> AgentState:
    """
    NODE 1 — The Thinking Step
    The agent reads the full conversation and decides what to do.
    It either replies directly OR calls a tool.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = model.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """
    THE ROUTER — The Decision Point
    Did the agent call a tool? → go to tools node
    Did the agent write a final reply? → END
    """
    last_message = list(state["messages"])[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ToolNode automatically runs whatever tool the agent chose
tool_node = ToolNode(tools)


# ── BUILD THE GRAPH ──
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)

# After tools run → always go back to agent to read the result
workflow.add_edge("tools", "agent")

pierre_agent = workflow.compile()


# ── RUN FUNCTION ──
# This is what the server will call for every customer message

def run_agent(user_message: str, history: list = []) -> dict:
    """
    Takes a customer message + conversation history
    Returns the agent's reply and whether it was escalated
    """
    formatted_history = []
    for msg in history:
        if msg["role"] == "user":
            formatted_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            formatted_history.append(AIMessage(content=msg["content"]))

    formatted_history.append(HumanMessage(content=user_message))

    result = pierre_agent.invoke({"messages": formatted_history})

    final_message = list(result["messages"])[-1]
    reply_text = final_message.content

    # Detect escalation — did the agent create a ticket?
    escalated = "PA-" in reply_text and "TICKET" in reply_text.upper()

    return {
        "reply": reply_text,
        "escalated": escalated
    }


# ── LOCAL TEST ──
# Run: python agent.py

if __name__ == "__main__":
    print("Pierre Assist — Agent Test")
    print("=" * 40)

    test_messages = [
        "My flight PA2847 was delayed — what am I owed?",
        "I want to upgrade my seat to Business Class on PA2847",
        "Check my booking PR-48291",
    ]

    for msg in test_messages:
        print(f"\n👤 Customer: {msg}")
        result = run_agent(msg)
        print(f"🤖 Pierre Assist: {result['reply']}")
        print(f"   Escalated: {result['escalated']}")
        print("-" * 40)
