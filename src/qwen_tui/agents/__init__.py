"""
Agent system for Qwen-TUI with Claude Code-quality capabilities.

This package provides sophisticated agents with ReAct patterns, tool usage,
permission systems, and comprehensive reasoning capabilities.
"""

from .base import BaseAgent, CodingAgent, AnalysisAgent, AgentMode, ReasoningPhase
from .react import ReActAgent, ActionType, AgentAction
from .factory import AgentFactory, AgentType, AgentOrchestrator, get_agent_factory
from .permissions import (
    PermissionManager, RiskLevel, PermissionAction, RiskAssessment,
    CommandClassifier, FileAccessController, get_permission_manager
)

__all__ = [
    # Base agent classes
    "BaseAgent",
    "CodingAgent", 
    "AnalysisAgent",
    "AgentMode",
    "ReasoningPhase",
    
    # ReAct agent system
    "ReActAgent",
    "ActionType",
    "AgentAction",
    
    # Agent factory and orchestration
    "AgentFactory",
    "AgentType",
    "AgentOrchestrator",
    "get_agent_factory",
    
    # Permission system
    "PermissionManager",
    "RiskLevel",
    "PermissionAction", 
    "RiskAssessment",
    "CommandClassifier",
    "FileAccessController",
    "get_permission_manager",
]