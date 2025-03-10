# coding: utf-8

import os
import argparse
import tempfile
import shutil
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults

from config import setup_environment
from graph import build_research_team_graph, build_writing_team_graph
from graph import build_super_team_graph


def run_cli_mode():
    """Run command line interactive mode (for testing)"""
    setup_environment()

    llm = ChatOpenAI(model='gpt-4o')
    # llm = ChatOpenAI(
    #     model="openai/gpt-4o-2024-11-20",
    #     temperature=0,
    #     api_key=os.environ["OPENROUTER_API_KEY"],
    #     base_url="https://openrouter.ai/api/v1",
    # )

    tavily_tool = TavilySearchResults(max_results=5)

    # Create temporary directory as working directory
    temp_dir = Path(tempfile.mkdtemp(prefix="agent_cli_"))
    try:
        research_team = build_research_team_graph(llm, tavily_tool)
        writing_team = build_writing_team_graph(llm, temp_dir)
        super_team = build_super_team_graph(llm, research_team, writing_team)

        for s in super_team.stream(
            {
                "messages": [
                    ("user", "Research AI agents and write a brief report about them.")
                ],
            },
            {"recursion_limit": 150},
        ):
            print(s)
            print("---")
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def run_api_mode(host="0.0.0.0", port=8000):
    """Start API server"""
    import uvicorn
    uvicorn.run("api:app", host=host, port=port, reload=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Hierarchical Agent Teams Application')
    parser.add_argument('--api', action='store_true', help='Run in API server mode')
    parser.add_argument('--host', type=str, default="0.0.0.0", help='API server listening address')
    parser.add_argument('--port', type=int, default=8000, help='API server listening port')
    args = parser.parse_args()
    
    if args.api:
        run_api_mode(host=args.host, port=args.port)
    else:
        run_cli_mode()