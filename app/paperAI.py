import json
from typing import Optional, Iterator
from phi.agent import Agent
from phi.workflow import Workflow, RunResponse, RunEvent
from phi.storage.workflow.sqlite import SqlWorkflowStorage
from phi.utils.pprint import pprint_run_response
from phi.utils.log import logger
from phi.tools.arxiv_toolkit import ArxivToolkit
from phi.model.openai.like import OpenAILike

class PaperSummaryGenerator(Workflow):
    searcher: Agent = Agent(
        model=OpenAILike(
            id="yi-large-fc",
            api_key="1352a88fdd3844deaec9d7dbe4b467d5",
            base_url="https://api.lingyiwanwu.com/v1",
        ),
        tools=[ArxivToolkit()],
        instructions=["Given a topic, search for 10 research papers and return the 5 most relevant papers in a simple format including title, URL, and abstract for each paper."],
    )

    summarizer: Agent = Agent(
        instructions=[
            "You will be provided with a topic and a list of top research papers on that topic.",
            "Carefully read each paper and generate a concise summary of the research findings.",
            "Break the summary into sections and provide key takeaways at the end.",
            "Make sure the title is informative and clear.",
            "Always provide sources, do not make up information or sources.",
        ],
        model=OpenAILike(
            id="yi-medium-200k",
            api_key="1352a88fdd3844deaec9d7dbe4b467d5",
            base_url="https://api.lingyiwanwu.com/v1",
        ),
    )

    def run(self, topic: str, use_cache: bool = True) -> Iterator[RunResponse]:
        logger.info(f"Generating a summary on: {topic}")

        # Use the cached summary if use_cache is True
        if use_cache and "summaries" in self.session_state:
            logger.info("Checking if cached summary exists")
            for cached_summary in self.session_state["summaries"]:
                if cached_summary["topic"] == topic:
                    logger.info("Found cached summary")
                    yield RunResponse(
                        run_id=self.run_id,
                        event=RunEvent.workflow_completed,
                        content=cached_summary["summary"],
                    )
                    return

        # Step 1: Search the web for research papers on the topic
        num_tries = 0
        search_results = None
        # Run until we get valid search results
        while search_results is None and num_tries < 3:
            try:
                num_tries += 1
                searcher_response: RunResponse = self.searcher.run(topic)
                if (
                    searcher_response
                    and searcher_response.content
                ):
                    logger.info("Successfully retrieved papers.")
                    search_results = searcher_response.content
                else:
                    logger.warning("Searcher response invalid, trying again...")
            except Exception as e:
                logger.warning(f"Error running searcher: {e}")

        # If no search_results are found for the topic, end the workflow
        if not search_results:
            yield RunResponse(
                run_id=self.run_id,
                event=RunEvent.workflow_completed,
                content=f"Sorry, could not find any research papers on the topic: {topic}",
            )
            return

        # Step 2: Summarize the research papers
        logger.info("Summarizing research papers")
        # Prepare the input for the summarizer
        summarizer_input = {
            "topic": topic,
            "papers": search_results,
        }
        # Run the summarizer and yield the response
        yield from self.summarizer.run(json.dumps(summarizer_input, indent=4), stream=True)

        # Save the summary in the session state for future runs
        if "summaries" not in self.session_state:
            self.session_state["summaries"] = []
        self.session_state["summaries"].append({"topic": topic, "summary": self.summarizer.run_response.content})