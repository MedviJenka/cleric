from settings import Config
from crewai import LLM, Task
from functools import cached_property
from crewai.agents.agent_builder.base_agent import BaseAgent


class AgentConfig:

    agents: list[BaseAgent]
    tasks: list[Task]
    tasks_config: dict = 'config/tasks.yaml'
    agents_config: dict = 'config/agents.yaml'

    @cached_property
    def llm(self) -> LLM:
        return LLM(model=Config.OPENAI_MODEL)
