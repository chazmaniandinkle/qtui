"""
Agent factory for creating specialized agents with optimal configurations.

This module provides factory methods for creating different types of agents
optimized for specific tasks and workflows.
"""
from enum import Enum
from typing import Dict, Optional, Type, Any

from .base import BaseAgent, CodingAgent, AnalysisAgent, AgentMode, AgentState
from ..backends.manager import BackendManager
from ..tools import ToolManager
from ..logging import get_main_logger


class AgentType(Enum):
    """Types of specialized agents."""
    CODING = "coding"
    ANALYSIS = "analysis"
    DEBUGGING = "debugging"
    RESEARCH = "research"
    GENERAL = "general"


class AgentFactory:
    """Factory for creating and configuring agents."""
    
    def __init__(self, backend_manager: BackendManager, tool_manager: ToolManager):
        self.backend_manager = backend_manager
        self.tool_manager = tool_manager
        self.logger = get_main_logger()
        
        # Register agent types
        self._agent_types: Dict[AgentType, Type[BaseAgent]] = {
            AgentType.CODING: CodingAgent,
            AgentType.ANALYSIS: AnalysisAgent,
            AgentType.GENERAL: CodingAgent,  # Default to coding agent
        }
        
        # Agent configurations
        self._agent_configs = {
            AgentType.CODING: {
                "context": {
                    "focus": "code implementation and modification",
                    "preferred_tools": ["Read", "Write", "Edit", "MultiEdit", "Bash"],
                    "quality_checks": ["syntax", "style", "tests"]
                }
            },
            AgentType.ANALYSIS: {
                "context": {
                    "focus": "code exploration and understanding",
                    "preferred_tools": ["Read", "Grep", "Glob", "LS"],
                    "analysis_depth": "comprehensive"
                }
            },
            AgentType.DEBUGGING: {
                "context": {
                    "focus": "issue identification and resolution",
                    "preferred_tools": ["Read", "Grep", "Bash", "Edit"],
                    "investigation_mode": "systematic"
                }
            },
            AgentType.RESEARCH: {
                "context": {
                    "focus": "information gathering and documentation",
                    "preferred_tools": ["Read", "Grep", "Glob", "Task"],
                    "depth": "thorough"
                }
            }
        }

    def create_agent(self, agent_type: AgentType, agent_id: Optional[str] = None,
                    working_directory: Optional[str] = None, 
                    additional_context: Optional[Dict[str, Any]] = None) -> BaseAgent:
        """Create a specialized agent of the specified type."""
        
        # Get agent class
        agent_class = self._agent_types.get(agent_type, CodingAgent)
        
        # Create agent
        agent = agent_class(
            backend_manager=self.backend_manager,
            tool_manager=self.tool_manager,
            agent_id=agent_id
        )
        
        # Set working directory
        if working_directory:
            agent.set_working_directory(working_directory)
        
        # Apply configuration
        config = self._agent_configs.get(agent_type, {})
        context = config.get("context", {})
        
        if additional_context:
            context.update(additional_context)
        
        for key, value in context.items():
            agent.add_context(key, value)
        
        self.logger.info(f"Created {agent_type.value} agent: {agent.agent_id}")
        return agent

    def create_coding_agent(self, working_directory: str, 
                           language: Optional[str] = None,
                           framework: Optional[str] = None) -> CodingAgent:
        """Create a coding agent optimized for a specific language/framework."""
        
        context = {}
        if language:
            context["primary_language"] = language
        if framework:
            context["framework"] = framework
            
        agent = self.create_agent(
            AgentType.CODING,
            working_directory=working_directory,
            additional_context=context
        )
        
        return agent

    def create_analysis_agent(self, working_directory: str,
                            analysis_type: str = "general") -> AnalysisAgent:
        """Create an analysis agent for codebase exploration."""
        
        context = {
            "analysis_type": analysis_type,
            "exploration_strategy": "breadth_first" if analysis_type == "overview" else "depth_first"
        }
        
        agent = self.create_agent(
            AgentType.ANALYSIS,
            working_directory=working_directory,
            additional_context=context
        )
        
        return agent

    def create_debugging_agent(self, working_directory: str,
                              issue_type: Optional[str] = None) -> BaseAgent:
        """Create a debugging agent for issue resolution."""
        
        context = {
            "debugging_mode": True,
            "systematic_approach": True
        }
        
        if issue_type:
            context["issue_type"] = issue_type
            
        agent = self.create_agent(
            AgentType.DEBUGGING,
            working_directory=working_directory,
            additional_context=context
        )
        
        return agent

    def get_recommended_agent_type(self, task_description: str) -> AgentType:
        """Recommend the best agent type for a given task."""
        task_lower = task_description.lower()
        
        # Keyword-based recommendations
        if any(word in task_lower for word in ["implement", "write", "create", "build", "code", "develop"]):
            return AgentType.CODING
        
        elif any(word in task_lower for word in ["analyze", "understand", "explore", "examine", "review"]):
            return AgentType.ANALYSIS
        
        elif any(word in task_lower for word in ["debug", "fix", "error", "bug", "issue", "problem"]):
            return AgentType.DEBUGGING
        
        elif any(word in task_lower for word in ["research", "find", "search", "investigate", "document"]):
            return AgentType.RESEARCH
        
        else:
            return AgentType.GENERAL

    def create_recommended_agent(self, task_description: str, 
                                working_directory: str) -> BaseAgent:
        """Create the most appropriate agent for a task."""
        agent_type = self.get_recommended_agent_type(task_description)
        
        context = {
            "task_description": task_description,
            "auto_selected": True,
            "recommendation_reason": f"Selected {agent_type.value} agent based on task keywords"
        }
        
        return self.create_agent(
            agent_type,
            working_directory=working_directory,
            additional_context=context
        )


class AgentOrchestrator:
    """Orchestrates multiple agents for complex tasks."""
    
    def __init__(self, factory: AgentFactory):
        self.factory = factory
        self.active_agents: Dict[str, BaseAgent] = {}
        self.logger = get_main_logger()

    async def delegate_task(self, task: str, working_directory: str,
                           preferred_agent_type: Optional[AgentType] = None) -> str:
        """Delegate a task to the most appropriate agent."""
        
        if preferred_agent_type:
            agent_type = preferred_agent_type
        else:
            agent_type = self.factory.get_recommended_agent_type(task)
        
        # Create agent for this task
        agent = self.factory.create_agent(agent_type, working_directory=working_directory)
        self.active_agents[agent.agent_id] = agent
        
        try:
            # Execute the task
            result = await agent.execute_autonomous_task(task)
            return result
        
        finally:
            # Clean up
            if agent.agent_id in self.active_agents:
                del self.active_agents[agent.agent_id]

    def get_active_agents(self) -> Dict[str, BaseAgent]:
        """Get currently active agents."""
        return self.active_agents.copy()

    def terminate_agent(self, agent_id: str) -> bool:
        """Terminate a specific agent."""
        if agent_id in self.active_agents:
            del self.active_agents[agent_id]
            self.logger.info(f"Terminated agent: {agent_id}")
            return True
        return False

    def terminate_all_agents(self) -> None:
        """Terminate all active agents."""
        count = len(self.active_agents)
        self.active_agents.clear()
        self.logger.info(f"Terminated {count} agents")


# Global factory instance
_global_factory: Optional[AgentFactory] = None


def get_agent_factory(backend_manager: BackendManager, tool_manager: ToolManager) -> AgentFactory:
    """Get or create the global agent factory."""
    global _global_factory
    if _global_factory is None:
        _global_factory = AgentFactory(backend_manager, tool_manager)
    return _global_factory