import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Annotated, TypedDict

try:
    from langchain_core.messages import BaseMessage, SystemMessage
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode, tools_condition
    from langgraph.checkpoint.memory import MemorySaver
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    from src.local_runtime import LocalMessage, LocalToolMessage

# ==========================================
# 1. SETUP & PATH RESOLUTION
# ==========================================
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parents[0]

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.agent_tools import query_telemetry_db, fetch_corridor_conditions, search_compliance_sop

load_dotenv(project_root / ".env")

class AgentState(TypedDict):
    messages: list

# ==========================================
# 2. FACTORY INITIALIZATION: AGENT REASONER LLM
# ==========================================

AGENT_LLM_SETTING = os.getenv("Agent_llm", "OLLAMA").strip().upper()

class OfflineAgent:
    def stream(self, state, config=None, stream_mode=None):
        query = state["messages"][-1].content
        telemetry = query_telemetry_db.invoke("SELECT TOP 10 * FROM FDE_VIEWS.VW_ACTIVE_FLEET")
        sop = search_compliance_sop.invoke(query)
        report = (
            "### 1. Executive Summary\n"
            "Local demo mode is active. The console is using repository telemetry and the approved local SOP.\n"
            "Immediate risk: live SQL, weather, and cloud retrieval are unavailable until credentials are configured.\n\n"
            "### 2. Telemetry & Environment Analysis\n"
            "The local telemetry sample is available below for review.\n\n"
            "### 3. Required Action Plan\n"
            "1. **Review the local telemetry sample**: Identify temperature, delay, congestion, and risk anomalies.\n"
            "2. **Apply the local SOP thresholds**: Escalate temperatures above 4.0 C and high-risk shipments with delay probability above 0.65.\n\n"
            "*SOP Compliance Citation:* Cold_Chain_Incident_SOP_v2.md\n\n"
            "#### Local telemetry\n```text\n" + telemetry + "\n```\n\n"
            "#### Relevant SOP context\n```text\n" + sop + "\n```"
        )
        yield {"tools": {"messages": [LocalToolMessage(telemetry, name="query_telemetry_db"), LocalToolMessage(sop, name="search_compliance_sop")]}}
        yield {"reasoner": {"messages": [LocalMessage(report)]}}


if not LANGGRAPH_AVAILABLE or (AGENT_LLM_SETTING == "OLLAMA" and not os.getenv("OLLAMA_HOST")):
    print("Local demo mode enabled: external agent services are not configured.")
    fde_agent = OfflineAgent()
else:
    if AGENT_LLM_SETTING == "OPENAI":
        print("🤖 Brain Mode: Utilizing Cloud OpenAI Reasoner (gpt-4o)...")
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    elif AGENT_LLM_SETTING == "DEEPSEEK":
        print("🐳 Brain Mode: Utilizing Flagship DeepSeek Cloud Reasoner (deepseek-v4-pro)...")
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model="deepseek-v4-flash",
            temperature=0,
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            max_tokens=2048,
        )
    else:
        print("🤗 Brain Mode: Local Fallback Activated. Binding Local Ollama (qwen2.5:7b)...")
        from langchain_community.chat_models import ChatOllama
        llm = ChatOllama(model="qwen2.5:7b", temperature=0, num_predict=1024)

    fde_tools = [query_telemetry_db, fetch_corridor_conditions, search_compliance_sop]
    llm_with_tools = llm.bind_tools(fde_tools)

    def reasoning_node(state: AgentState):
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    print("⚙️ Compiling LangGraph FDE Orchestrator...")
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("reasoner", reasoning_node)
    graph_builder.add_node("tools", ToolNode(fde_tools))
    graph_builder.add_edge(START, "reasoner")
    graph_builder.add_conditional_edges("reasoner", tools_condition)
    graph_builder.add_edge("tools", "reasoner")
    fde_agent = graph_builder.compile(checkpointer=MemorySaver())

# ==========================================
# 4. CHAT LOOP TESTING PANEL
# ==========================================
if __name__ == "__main__":
    print("\n" + "="*55)
    print("🚀 FDE Supply Chain Orchestrator State Machine Online")
    print(f"   Configured Execution: [LLM: {AGENT_LLM_SETTING}] -> [Embeddings: {os.getenv('Embeddings_model', 'LOCAL')}]")
    print("="*55 + "\n")
    
    # Load the business-structured system prompt from the external file
    prompt_path = project_root / "src" / "prompts" / "system_prompt.txt"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_instructions = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {prompt_path}")
        system_instructions = "You are a helpful AI assistant." # Basic fallback

    system_prompt = SystemMessage(content=system_instructions)
    
    thread_config = {"configurable": {"thread_id": "production_test_1"}}
    fde_agent.invoke({"messages": [system_prompt]}, config=thread_config)
    
    while True:
        user_input = input("\nDispatcher > ")
        if user_input.lower() in ['exit', 'quit']:
            break
            
        events = fde_agent.stream({"messages": [("user", user_input)]}, config=thread_config, stream_mode="updates")
        for event in events:
            for node_name, node_state in event.items():
                if node_name == "tools":
                    print("   [System] 🔄 Retrieving external data elements via ToolNode...")
                elif node_name == "reasoner":
                    latest_msg = node_state["messages"][-1]
                    if latest_msg.content:
                        print(f"\n🤖 FDE Agent:\n{latest_msg.content}")