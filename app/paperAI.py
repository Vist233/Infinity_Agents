import json
from typing import Iterator

from flask import session
from phi.agent import Agent
from phi.utils.pprint import pprint_run_response
from phi.workflow import Workflow, RunResponse, RunEvent
from phi.utils.log import logger
from phi.model.openai.like import OpenAILike
from phi.tools.pubmed import PubmedTools
from phi.tools.arxiv_toolkit import ArxivToolkit
import os

from config import API_KEY

# Get the API key from environment variables OR set your API key here
API_KEY = API_KEY

class PaperSummaryGenerator(Workflow):
    # searcher: Agent = Agent(
    #     model=OpenAILike(
    #         id="yi-large-fc",
    #         api_key=API_KEY,
    #         base_url="https://api.lingyiwanwu.com/v1",
    #     ),
    #     tools=[PubmedTools()],
    #     instructions=["Given a topic, search for 5 research papers and return the 3 most relevant papers in a simple format including title, URL, and abstract for each paper."],
    #     add_history_to_messages=True,
    # )
    
    searcher: Agent = Agent(
        model=OpenAILike(
            id="yi-lightning",
            api_key=API_KEY,
            base_url="https://api.lingyiwanwu.com/v1",
        ),
        # tools=[PubmedTools()],
        instructions=["Given a topic, search for 5 research papers and return the 3 most relevant papers in a simple format including title, URL, and abstract for each paper."],
        add_history_to_messages=True,
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
            id="yi-lightning",
            api_key=API_KEY,
            base_url="https://api.lingyiwanwu.com/v1",
        ),
        add_history_to_messages=True,
    )

    def __init__(self, storage=None):
        super().__init__(storage=storage)
        self._session_id = None

    @property
    def session_id(self):
        return self._session_id

    @session_id.setter
    def session_id(self, value):
        self._session_id = value

    def run(self, logs: list, topic: str, use_cache: bool = True) -> Iterator[RunResponse]:
        # 测试用的快速响应
        if topic == "量子计算":
            print("处理量子计算测试响应")
            test_response = "这里是ai的回复"
            response = RunResponse(
                run_id=self.run_id,
                event=RunEvent.workflow_completed,
                content=test_response,
                metadata={}
            )
            print(f"生成测试响应: {response}")
            self.run_response = response
            yield response
            return

        try:
            logger.info(f"Generating a summary on: {topic}")
            logs.append(f"Generating a summary on: {topic}\n")

            # Step 1: Search the web for research papers on the topic
            num_tries = 0
            search_results = None
            last_error = None
            
            # Run until we get valid search results
            while search_results is None and num_tries < 3:
                try:
                    num_tries += 1
                    print(f"尝试第 {num_tries} 次搜索论文")
                    searcher_response: RunResponse = self.searcher.run(topic)
                    print(f"搜索响应: {searcher_response}")
                    
                    if searcher_response and searcher_response.content:
                        content = searcher_response.content
                        print(f"搜索结果内容: {content}")
                        
                        # 检查是否是错误消息
                        if isinstance(content, str) and (
                            "error" in content.lower() or 
                            "sorry" in content.lower() or 
                            "trouble" in content.lower()
                        ):
                            last_error = content
                            logger.warning(f"Search error: {last_error}")
                            continue
                            
                        logger.info("Successfully retrieved papers.")
                        logs.append(f"Successfully retrieved papers.\n")
                        search_results = content
                    else:
                        logger.warning("Searcher response invalid, trying again...")
                        logs.append(f"Searcher response invalid, trying again...\n")
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Error running searcher: {e}")
                    logs.append(f"Error running searcher: {e}\n")

            # If no search_results are found for the topic, return error message
            if not search_results:
                error_message = "抱歉，暂时无法获取相关论文信息。"
                if last_error:
                    if "trouble accessing" in last_error:
                        error_message = "抱歉，暂时无法访问 PubMed 数据库，请稍后再试。"
                    elif "timeout" in last_error.lower():
                        error_message = "抱歉，网络连接超时，请稍后再试。"
                    else:
                        error_message = f"抱歉，搜索过程中出现错误: {last_error}"
                
                response = RunResponse(
                    run_id=self.run_id,
                    event=RunEvent.workflow_completed,
                    content=error_message,
                    metadata={}
                )
                self.run_response = response
                yield response
                return

            # Step 2: Summarize the research papers
            try:
                logger.info("Summarizing research papers")
                logs.append(f"Summarizing research papers\n")
                
                summarizer_input = {
                    "topic": topic,
                    "papers": search_results,
                }
                print(f"准备发送给摘要生成器的输入: {summarizer_input}")
                
                # 运行摘要生成器并获取最后的响应
                last_response = None
                for res in self.summarizer.run(json.dumps(summarizer_input, indent=4), stream=True):
                    print(f"收到摘要生成器响应: {res}")
                    if res.event == RunEvent.workflow_completed and res.content:
                        print(f"生成的摘要内容: {res.content}")
                        self.run_response = res
                        yield res
                        return
                    last_response = res
                
                # 如果没有得到有效响应
                error_message = "抱歉，生成摘要时出现错误，请稍后重试。"
                if last_response and hasattr(last_response, 'content'):
                    if not last_response.content:
                        print("摘要生成器返回的内容为空")
                    elif "error" in str(last_response.content).lower():
                        error_message = f"抱歉，{last_response.content}"
                else:
                    print("没有收到摘要生成器的响应")
                
                response = RunResponse(
                    run_id=self.run_id,
                    event=RunEvent.workflow_completed,
                    content=error_message,
                    metadata={}
                )
                self.run_response = response
                yield response
                    
            except Exception as e:
                error_msg = f"生成摘要时出错: {str(e)}"
                logger.error(error_msg)
                print(f"摘要生成异常: {error_msg}")
                response = RunResponse(
                    run_id=self.run_id,
                    event=RunEvent.workflow_completed,
                    content=error_msg,
                    metadata={}
                )
                self.run_response = response
                yield response
                
        except Exception as e:
            error_msg = f"处理过程中出错: {str(e)}"
            logger.error(error_msg)
            print(f"整体处理异常: {error_msg}")
            response = RunResponse(
                run_id=self.run_id,
                event=RunEvent.workflow_completed,
                content=error_msg,
                metadata={}
            )
            self.run_response = response
            yield response

        # Save the summary in the session state for future runs
        if "summaries" not in self.session_state:
            self.session_state["summaries"] = []
        self.session_state["summaries"].append({"topic": topic, "summary": self.summarizer.run_response.content})


if __name__ == "__main__":
    paperai = PaperSummaryGenerator()
    logs=[]
    result=paperai.run(logs,"language models")
    pprint_run_response(result, markdown=True)

