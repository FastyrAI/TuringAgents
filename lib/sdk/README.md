Providing the general usage of the library.

```python
from lib.sdk.agents import Agent, Knowledge, GraphDB, Hooks, AgentConfig, Capability
from lib.sdk.knowledge import Knowledge, GraphDB, RetrievalPipeline

db = GraphDB()

retrieval_pipeline = RetrievalPipeline(execute=retrieval_function, condition_evaluation=evaluate_if_should_retrieve)

knowledge = Knowledge(source=db, retrieval=retrieval_pipeline)

hooks = Hooks(before_tool=example_function)

# A capability is an abstract concept that defines the "what" and has tools that implement the "how". For example, web search is a capability but searching Google is the specific implementation. What should we do if there is more than one valid option? How do we implement more complex capabilities like speech?
web_search = Capability(description='search the web for information', tools=[google_web_search])

config = AgentConfig(model='gpt-5', provider='openai', system_prompt='Be helpful')

agent = Agent(
    task_id="123",
    capabilities=[web_search],
    knowledge=[knowledge],
    hooks=hooks,
    config=config
)

agent.run()
```