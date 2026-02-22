import pytest
from praisonaiagents import Agent, Task
from praisonaiagents.main import TaskOutput
from praisonaiagents.temporal.converter import (
    serialize_agent, deserialize_agent,
    serialize_task, deserialize_task,
    serialize_task_output, deserialize_task_output
)

def sample_tool():
    pass

def test_serialize_agent():
    agent = Agent(
        name="TestAgent",
        role="Tester",
        goal="Test things",
        instructions="Just test",
        llm="gpt-4o",
        tools=[sample_tool]
    )
    
    config = serialize_agent(agent)
    assert config["name"] == "TestAgent"
    assert config["role"] == "Tester"
    assert config["llm"] == "gpt-4o"
    assert config["tools"] == ["sample_tool"]

def test_deserialize_agent():
    config = {
        "name": "RestoredAgent",
        "role": "Tester",
        "llm": "gpt-4o",
        "tools": ["sample_tool"]
    }
    
    registry = {"sample_tool": sample_tool}
    agent = deserialize_agent(config, registry)
    
    assert agent.name == "RestoredAgent"
    assert agent.role == "Tester"
    assert agent.llm == "gpt-4o"
    assert agent.tools[0] == sample_tool

def test_serialize_deserialize_task():
    agent = Agent(name="TaskAgent")
    task = Task(name="task1", description="Do work", expected_output="Done", agent=agent)
    
    config = serialize_task(task)
    assert config["name"] == "task1"
    assert config["description"] == "Do work"
    assert config["agent_name"] == "TaskAgent"
    
    agents_map = {"TaskAgent": agent}
    restored = deserialize_task(config, agents_map)
    assert restored.name == "task1"
    assert restored.description == "Do work"
    assert restored.agent == agent

def test_serialize_deserialize_task_output():
    output = TaskOutput(
        description="test desc",
        raw="Hello World",
        agent="TestAgent",
        output_format="RAW"
    )
    
    data = serialize_task_output(output)
    assert data["raw"] == "Hello World"
    assert data["agent"] == "TestAgent"
    
    restored = deserialize_task_output(data)
    assert restored.raw == "Hello World"
    assert restored.agent == "TestAgent"
