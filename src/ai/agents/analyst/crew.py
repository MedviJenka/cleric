from pathlib import Path
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from settings import Config
from src.ai.agents.analyst.schemas import MonitoringSchema
from src.ai.config import AgentConfig


SKILLS_PATH = Path(__file__).with_name('skills')


@CrewBase
class AnalystAgent(AgentConfig):

    @agent
    def observer(self) -> Agent:
        return Agent(
            config=self.agents_config['observer'],
            verbose=Config.AGENT_VERBOSE,
            llm=self.llm,
            skills=[str(SKILLS_PATH)],
        )

    @agent
    def diagnostician(self) -> Agent:
        return Agent(
            config=self.agents_config['diagnostician'],
            verbose=Config.AGENT_VERBOSE,
            llm=self.llm,
            skills=[str(SKILLS_PATH)],
        )

    @agent
    def repair_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config['repair_strategist'],
            verbose=Config.AGENT_VERBOSE,
            llm=self.llm,
            skills=[str(SKILLS_PATH)],
        )

    @agent
    def risk_policy_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['risk_policy_analyst'],
            verbose=Config.AGENT_VERBOSE,
            llm=self.llm,
            skills=[str(SKILLS_PATH)],
        )

    @task
    def observe_failure_task(self) -> Task:
        return Task(config=self.tasks_config['observe_failure_task'])

    @task
    def diagnose_failure_task(self) -> Task:
        return Task(
            config=self.tasks_config['diagnose_failure_task'],
            context=[self.observe_failure_task()],
        )

    @task
    def propose_repair_task(self) -> Task:
        return Task(
            config=self.tasks_config['propose_repair_task'],
            context=[self.observe_failure_task(), self.diagnose_failure_task()],
        )

    @task
    def policy_decision_task(self) -> Task:
        return Task(
            config=self.tasks_config['policy_decision_task'],
            context=[
                self.observe_failure_task(),
                self.diagnose_failure_task(),
                self.propose_repair_task(),
            ],
            output_pydantic=MonitoringSchema,
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.observer(),
                self.diagnostician(),
                self.repair_strategist(),
                self.risk_policy_analyst(),
            ],
            tasks=[
                self.observe_failure_task(),
                self.diagnose_failure_task(),
                self.propose_repair_task(),
                self.policy_decision_task(),
            ],
            process=Process.sequential,
            verbose=Config.AGENT_VERBOSE,
        )


def analyst_agent(log: str) -> dict:
    return AnalystAgent().crew().kickoff(inputs={'log': log}).pydantic.model_dump()

def dummy_log() -> str:
    with open(r'C:\Users\medvi\PycharmProjects\PythonProject1\tests\fixtures\dummy_automation_failure.log','r') as file:
        return file.read()


if __name__ == '__main__':
    analyst_agent(log=dummy_log())
