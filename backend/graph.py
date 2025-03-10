# coding: utf-8
import logging
from langgraph.graph import StateGraph, START
from langchain_core.tools.base import BaseTool
from langchain_core.language_models.chat_models import BaseChatModel
from pathlib import Path

from node import State
from node import make_supervisor_node
from node import create_search_node, create_web_scraper_node
from node import create_doc_writing_node, create_note_taking_node, create_chart_generating_node
from node import create_research_team_invoke_node, create_writing_team_invoke_node
from tools.writing_tools import WritingTools

logger = logging.getLogger(__name__)

def build_research_team_graph(llm: BaseChatModel, search_tool: BaseTool):
    logger.info("Starting to build research_team_graph")
    research_supervisor_node = make_supervisor_node(llm, ["search", "web_scraper"])
    search_node = create_search_node(llm, search_tool, goto='supervisor')
    web_scraper_node = create_web_scraper_node(llm, goto='supervisor')
    research_builder = StateGraph(State)
    research_builder.add_node("supervisor", research_supervisor_node)
    research_builder.add_node("search", search_node)
    research_builder.add_node("web_scraper", web_scraper_node)

    research_builder.add_edge(START, "supervisor")
    
    compiled_graph = research_builder.compile()
    logger.info("research_team_graph build completed")
    return compiled_graph

def build_writing_team_graph(llm: BaseChatModel, working_dir: Path):
    logger.info(f"Starting to build writing_team_graph, working_dir: {working_dir}")
    doc_writing_supervisor_node = make_supervisor_node(
        llm, ["doc_writer", "note_taker", "chart_generator"]
    )
    
    # Create WritingTools instance, using the working directory passed in from outside
    writing_tools = WritingTools(working_dir)
    doc_writing_node = create_doc_writing_node(llm, writing_tools)
    note_taking_node = create_note_taking_node(llm, writing_tools)
    chart_generating_node = create_chart_generating_node(llm, writing_tools)

    # Create the graph here
    paper_writing_builder = StateGraph(State)
    paper_writing_builder.add_node("supervisor", doc_writing_supervisor_node)
    paper_writing_builder.add_node("doc_writer", doc_writing_node)
    paper_writing_builder.add_node("note_taker", note_taking_node)
    paper_writing_builder.add_node("chart_generator", chart_generating_node)

    paper_writing_builder.add_edge(START, "supervisor")
    
    compiled_graph = paper_writing_builder.compile()
    logger.info("writing_team_graph build completed")
    return compiled_graph

def build_super_team_graph(llm: BaseChatModel, research_graph, writing_graph):
    logger.info("Starting to build super_team_graph")
    logger.info(f"Input parameters - llm: {llm}, research_graph: {research_graph}, writing_graph: {writing_graph}")
    
    if research_graph is None:
        logger.error("research_graph is None, cannot build super_team")
        return None
        
    if writing_graph is None:
        logger.error("writing_graph is None, cannot build super_team")
        return None
    
    teams_supervisor_node = make_supervisor_node(llm, ["research_team", "writing_team"])
    call_research_team = create_research_team_invoke_node(research_graph)
    call_writing_team = create_writing_team_invoke_node(writing_graph)

    super_builder = StateGraph(State)
    super_builder.add_node("supervisor", teams_supervisor_node)
    super_builder.add_node("research_team", call_research_team)
    super_builder.add_node("writing_team", call_writing_team)
    super_builder.add_edge(START, "supervisor")
    
    try:
        compiled_graph = super_builder.compile()
        logger.info("super_team_graph build completed")
        return compiled_graph
    except Exception as e:
        logger.error(f"Error compiling super_team_graph: {str(e)}", exc_info=True)
        return None
