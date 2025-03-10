# coding: utf-8

from typing import Literal
from typing_extensions import TypedDict
import logging
from langchain_core.language_models.chat_models import BaseChatModel

from langgraph.graph import MessagesState, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage

from langgraph.prebuilt import create_react_agent
from langchain_community.tools.tavily_search import TavilySearchResults

from tools import scrape_webpages, WritingTools

# 获取日志记录器
logger = logging.getLogger(__name__)

class State(MessagesState):
    next: str


def make_supervisor_node(llm: BaseChatModel, members: list[str]) -> str:
    options = ["FINISH"] + members
    system_prompt = (
        "You are a supervisor tasked with managing a conversation between the"
        f" following workers: {members}. Given the following user request,"
        " respond with the worker to act next. Each worker will perform a"
        " task and respond with their results and status. When finished,"
        " respond with FINISH."
    )

    class Router(TypedDict):
        """Worker to route to next. If no workers needed, route to FINISH."""

        next: Literal[*options] # type: ignore

    def supervisor_node(state: State) -> Command[Literal[*members, "__end__"]]: # type: ignore
        """An LLM-based router."""
        logger.info(f"supervisor_node called, state: {state}")
        messages = [
            {"role": "system", "content": system_prompt},
        ] + state["messages"]
        logger.info(f"Calling LLM for routing decision, messages length: {len(messages)}")
        response = llm.with_structured_output(Router).invoke(messages)
        goto = response["next"]
        if goto == "FINISH":
            goto = END
        logger.info(f"Routing decision result: {goto}")
        return Command(goto=goto, update={"next": goto})

    return supervisor_node

def create_search_node(llm: BaseChatModel, tavily_tool:TavilySearchResults, goto: str = 'supervisor') -> callable:
    search_agent = create_react_agent(llm, tools=[tavily_tool])

    def search_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"search_node called, state: {state}")
        result = search_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="search")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto=goto,
        )

    return search_node

def create_web_scraper_node(llm: BaseChatModel, goto: str = "supervisor") -> callable:
    web_scraper_agent = create_react_agent(llm, tools=[scrape_webpages])

    def web_scraper_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"web_scraper_node called, state: {state}")
        result = web_scraper_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="web_scraper")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto=goto,
        )

    return web_scraper_node

def create_doc_writing_node(llm: BaseChatModel, writing_tools: WritingTools, goto: str = "supervisor") -> callable:
    doc_writer_agent = create_react_agent(
        llm,
        tools=writing_tools.get_tools(["writing", "editing", "reading"]),
        prompt=(
            "You can read, write and edit documents based on note-taker's outlines. "
            "Don't ask follow-up questions."
        ),
    )

    def doc_writing_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"doc_writing_node called, state: {state}")
        result = doc_writer_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="doc_writer")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto=goto,
        )

    return doc_writing_node

def create_note_taking_node(llm: BaseChatModel, writing_tools: WritingTools, goto: str = "supervisor") -> callable:
    note_taking_agent = create_react_agent(
        llm,
        tools=writing_tools.get_tools(["outline", "reading"]),
        prompt=(
            "You can read documents and create outlines for the document writer. "
            "Don't ask follow-up questions."
        ),
    )

    def note_taking_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"note_taking_node called, state: {state}")
        result = note_taking_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(content=result["messages"][-1].content, name="note_taker")
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto=goto,
        )

    return note_taking_node

def create_chart_generating_node(llm: BaseChatModel, writing_tools: WritingTools, goto: str = "supervisor") -> callable:
    chart_generating_agent = create_react_agent(
        llm, tools=writing_tools.get_tools(["reading", "repl"])
    )

    def chart_generating_node(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"chart_generating_node called, state: {state}")
        result = chart_generating_agent.invoke(state)
        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=result["messages"][-1].content, name="chart_generator"
                    )
                ]
            },
            # We want our workers to ALWAYS "report back" to the supervisor when done
            goto=goto,
        )

    return chart_generating_node

def create_research_team_invoke_node(research_graph):
    def call_research_team(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"call_research_team called, state: {state}")
        if research_graph is None:
            logger.error("research_graph is None, cannot call invoke method")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content="Error: Research team graph is None, cannot process request", name="research_team"
                        )
                    ]
                },
                goto=END, # Cannot be handled by supervisor node, can only end
            )
            
        try:
            logger.info(f"Calling research_graph.invoke, input: {state['messages'][-1]}")
            response = research_graph.invoke({"messages": state["messages"][-1]})
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=response["messages"][-1].content, name="research_team"
                        )
                    ]
                },
                goto="supervisor",
            )
        except Exception as e:
            logger.error(f"Error calling research_graph.invoke: {str(e)}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=f"Error processing request by research team: {str(e)}", name="research_team"
                        )
                    ]
                },
                goto=END, # Cannot be handled by supervisor node, can only end
            )
    return call_research_team

def create_writing_team_invoke_node(writing_graph):
    def call_paper_writing_team(state: State) -> Command[Literal["supervisor"]]:
        logger.info(f"call_paper_writing_team called, state: {state}")
        if writing_graph is None:
            logger.error("writing_graph is None, cannot call invoke method")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content="Error: Writing team graph is None, cannot process request", name="writing_team"
                        )
                    ]
                },
                goto=END, # Cannot be handled by supervisor node, can only end
            )
            
        try:
            logger.info(f"Calling writing_graph.invoke, input: {state['messages'][-1]}")
            response = writing_graph.invoke({"messages": state["messages"][-1]})
            logger.info(f"writing_graph.invoke call result: {response}")
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=response["messages"][-1].content, name="writing_team"
                        )
                    ]
                },
                goto="supervisor",
            )
        except Exception as e:
            logger.error(f"Error calling writing_graph.invoke: {str(e)}", exc_info=True)
            return Command(
                update={
                    "messages": [
                        HumanMessage(
                            content=f"Error processing request by writing team: {str(e)}", name="writing_team"
                        )
                    ]
                },
                goto=END, # Cannot be handled by supervisor node, can only end
            )
    return call_paper_writing_team
