"""
Advanced thinking system with ReAct agent integration.

This module provides sophisticated thinking functionality using the ReAct
pattern with comprehensive tool usage and reasoning capabilities.
"""
import asyncio
import os
from typing import Optional, Dict, Any, List, AsyncGenerator, Callable, Union
from dataclasses import dataclass

from ..logging import get_main_logger
from ..agents import ReActAgent, get_agent_factory, get_permission_manager
from ..tools import get_tool_manager


@dataclass
class ThinkingState:
    """State of the thinking process."""
    is_thinking: bool = False
    current_thought: str = ""
    full_thoughts: str = ""
    active_tools: List[str] = None
    completed_actions: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.active_tools is None:
            self.active_tools = []
        if self.completed_actions is None:
            self.completed_actions = []


class ThinkingManager:
    """Advanced thinking manager with ReAct agent integration."""
    
    def __init__(self, backend_manager, config):
        self.backend_manager = backend_manager
        self.config = config
        self.logger = get_main_logger()
        self.state = ThinkingState()
        
        # Initialize tool and agent systems
        self.tool_manager = get_tool_manager()
        self.permission_manager = get_permission_manager()
        self.agent_factory = get_agent_factory(backend_manager, self.tool_manager)
        
        # Current working agent
        self.current_agent: Optional[ReActAgent] = None
        
        # UI callbacks
        self.on_thinking_update: Optional[Callable[[str], None]] = None
        self.on_action_start: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
        self.on_action_complete: Optional[Callable[[str, str, Any], None]] = None
        self.on_action_error: Optional[Callable[[str, str, str], None]] = None
        self.on_thinking_complete: Optional[Callable[[str], None]] = None
    
    async def initialize(self, working_directory: Optional[str] = None):
        """Initialize the thinking manager with ReAct agent system."""
        try:
            # Set working directory
            if working_directory:
                self.tool_manager.set_working_directory(working_directory)
                self.permission_manager = get_permission_manager(working_directory)
            else:
                working_directory = os.getcwd()
                self.tool_manager.set_working_directory(working_directory)
            
            # Create ReAct agent
            self.current_agent = ReActAgent(
                backend_manager=self.backend_manager,
                tool_manager=self.tool_manager
            )
            
            if working_directory:
                self.current_agent.set_working_directory(working_directory)
            
            self.logger.info("Advanced thinking manager initialized with ReAct agent")
            
        except Exception as e:
            self.logger.error("Failed to initialize thinking manager", error=str(e))
            # Create fallback agent
            self.current_agent = None
    
    def _get_model_config(self, backend) -> Dict[str, Any]:
        """Get model configuration for Qwen-Agent based on backend."""
        # This is a simplified configuration - would need to be expanded
        # based on the actual backend types and their configurations
        return {
            'model': getattr(backend, '_current_model', 'qwen-plus'),
            'api_key': getattr(backend, 'api_key', None),
            'base_url': getattr(backend, 'base_url', None),
        }
    
    def _initialize_demo_tools(self) -> List[Dict[str, Any]]:
        """Initialize demo tools for testing."""
        # Simple demo tools for testing the thinking system
        tools = [
            {
                "name": "calculator",
                "description": "Perform basic mathematical calculations",
                "parameters": ["expression"]
            },
            {
                "name": "text_analyzer", 
                "description": "Analyze text and provide insights",
                "parameters": ["text"]
            },
            {
                "name": "web_search",
                "description": "Search for information on the web",
                "parameters": ["query"]
            }
        ]
        return tools
    
    def set_ui_callbacks(self, 
                        on_thinking_update: Callable[[str], None],
                        on_action_start: Callable[[str, str, Dict[str, Any]], None],
                        on_action_complete: Callable[[str, str, Any], None],
                        on_action_error: Callable[[str, str, str], None],
                        on_thinking_complete: Callable[[str], None]):
        """Set callbacks for UI updates."""
        self.on_thinking_update = on_thinking_update
        self.on_action_start = on_action_start
        self.on_action_complete = on_action_complete
        self.on_action_error = on_action_error
        self.on_thinking_complete = on_thinking_complete
    
    async def think_and_respond(self, user_input: Union[str, List[Dict[str, str]]]) -> AsyncGenerator[str, None]:
        """
        Process user message through ReAct agent and generate response.
        
        Args:
            user_input: Either a string message or list of conversation messages
        
        This is the main entry point that:
        1. Uses ReAct agent for sophisticated reasoning
        2. Shows thinking animation and tool usage
        3. Updates UI with action progress
        4. Yields final response with visual indicators
        """
        self.state.is_thinking = True
        self.state.current_thought = "🤔 Starting analysis..."
        self.state.full_thoughts = ""
        
        # Handle different input formats
        if isinstance(user_input, list):
            # Convert conversation history to current user message
            user_message = ""
            for msg in reversed(user_input):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                user_message = "Hello! How can I help you today?"
        else:
            user_message = user_input
        
        try:
            # Start thinking animation
            if self.on_thinking_update:
                await self.on_thinking_update(self.state.current_thought)
            
            if self.current_agent:
                # Use ReAct agent for sophisticated processing
                full_response = ""
                
                async for chunk in self.current_agent.process_message(user_message):
                    # Parse chunk for different types of content
                    if chunk.startswith("🤔"):
                        # Thinking indicator
                        self._update_thinking(chunk)
                    elif chunk.startswith("⏺"):
                        # Tool execution start
                        await self._handle_tool_execution_start(chunk)
                    elif chunk.startswith("⎿"):
                        # Tool execution complete
                        await self._handle_tool_execution_complete(chunk)
                    elif chunk.startswith("❌"):
                        # Error indicator
                        await self._handle_error_indicator(chunk)
                    else:
                        # Accumulate response for think tag filtering
                        full_response += chunk
                
                # Apply think tag filtering to the complete response
                if full_response:
                    visible_content, thinking_content = self._filter_thinking_tags(full_response)
                    
                    # Update thinking state with extracted thinking content
                    if thinking_content:
                        self.state.full_thoughts += thinking_content
                        self._update_thinking("Processing internal reasoning...")
                    
                    # Yield only the filtered visible content
                    if visible_content.strip():
                        yield visible_content
            else:
                # Fallback to direct backend
                async for chunk in self._fallback_direct_response(user_message):
                    yield chunk
            
            # Complete thinking process
            self.state.is_thinking = False
            if self.on_thinking_complete:
                await self.on_thinking_complete("Thinking completed")
                
        except Exception as e:
            self.state.is_thinking = False
            self.logger.error("Error in thinking process", error=str(e))
            yield f"❌ Error in thinking process: {str(e)}"
    
    async def _handle_tool_execution_start(self, chunk: str):
        """Handle tool execution start indicators."""
        # Extract tool name from chunk (simplified parsing)
        tool_name = "unknown"
        if ":" in chunk:
            try:
                tool_name = chunk.split(":")[1].strip().split()[0]
            except IndexError:
                pass
        
        self.state.active_tools.append(tool_name)
        if self.on_action_start:
            await self.on_action_start("", tool_name, {})
    
    async def _handle_tool_execution_complete(self, chunk: str):
        """Handle tool execution completion indicators."""
        # Extract tool name from chunk (simplified parsing)
        tool_name = "unknown"
        if ":" in chunk:
            try:
                tool_name = chunk.split(":")[1].strip().split()[0]
            except IndexError:
                pass
        
        if tool_name in self.state.active_tools:
            self.state.active_tools.remove(tool_name)
        
        self.state.completed_actions.append({
            'tool_name': tool_name,
            'result': 'Completed successfully',
            'status': 'completed'
        })
        
        if self.on_action_complete:
            await self.on_action_complete("", tool_name, "Completed successfully")
    
    async def _handle_error_indicator(self, chunk: str):
        """Handle error indicators."""
        self.logger.warning(f"Agent error: {chunk}")
        if self.on_action_error:
            await self.on_action_error("", "unknown", chunk)
    
    async def _fallback_direct_response(self, user_message: str) -> AsyncGenerator[str, None]:
        """Fallback to direct backend response when agent is not available."""
        try:
            from ..backends.base import LLMRequest
            
            messages = [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": user_message}
            ]
            
            request = LLMRequest(messages=messages, stream=True)
            
            async for response in self.backend_manager.generate(request):
                if response.is_partial and response.delta:
                    yield response.delta
                elif response.content and not response.is_partial:
                    yield response.content
                    
        except Exception as e:
            yield f"Error in fallback response: {str(e)}"
    
    async def _simulate_thinking_process(self, messages: List[Dict[str, str]]) -> AsyncGenerator[Dict[str, Any], None]:
        """Simulate thinking process with demo tools."""
        import asyncio
        
        # Get the last user message
        user_message = messages[-1].get('content', '') if messages else ''
        
        # Simulate thinking steps
        yield {'type': 'thinking', 'content': 'Reading and understanding your request...'}
        await asyncio.sleep(0.5)
        
        yield {'type': 'thinking', 'content': 'Considering what tools I might need...'}
        await asyncio.sleep(0.5)
        
        # Simulate tool usage based on message content
        if any(word in user_message.lower() for word in ['calculate', 'math', 'number', '+', '-', '*', '/']):
            # Simulate calculator tool
            yield {
                'type': 'action_start',
                'tool_name': 'calculator',
                'parameters': {'expression': 'extracted from user message'},
                'call_id': 'calc_001'
            }
            await asyncio.sleep(1)
            yield {
                'type': 'action_complete',
                'tool_name': 'calculator',
                'result': '42 (simulated calculation result)',
                'call_id': 'calc_001'
            }
            
        elif any(word in user_message.lower() for word in ['analyze', 'text', 'review', 'check']):
            # Simulate text analyzer tool
            yield {
                'type': 'action_start',
                'tool_name': 'text_analyzer',
                'parameters': {'text': user_message[:50] + '...'},
                'call_id': 'text_001'
            }
            await asyncio.sleep(1.5)
            yield {
                'type': 'action_complete',
                'tool_name': 'text_analyzer',
                'result': 'Text analysis complete: Professional tone, clear intent',
                'call_id': 'text_001'
            }
            
        elif any(word in user_message.lower() for word in ['search', 'find', 'look up', 'research']):
            # Simulate web search tool
            yield {
                'type': 'action_start', 
                'tool_name': 'web_search',
                'parameters': {'query': 'extracted search terms'},
                'call_id': 'search_001'
            }
            await asyncio.sleep(2)
            yield {
                'type': 'action_complete',
                'tool_name': 'web_search',
                'result': 'Found relevant information (simulated)',
                'call_id': 'search_001'
            }
        
        # Final thinking
        yield {'type': 'thinking', 'content': 'Synthesizing results and preparing response...'}
        await asyncio.sleep(0.5)
        
        # Generate response using backend with thinking tag filtering
        try:
            from ..backends.base import LLMRequest
            request = LLMRequest(messages=messages, stream=True)
            
            # Accumulate full response to process thinking tags
            full_response = ""
            async for response in self.backend_manager.generate(request):
                if response.is_partial and response.delta:
                    full_response += response.delta
                elif response.content and not response.is_partial:
                    full_response = response.content
            
            # Process the response to extract thinking and visible content
            visible_content, thinking_content = self._filter_thinking_tags(full_response)
            
            # Update thinking with extracted content if available
            if thinking_content:
                self.state.full_thoughts += thinking_content
                yield {'type': 'thinking', 'content': 'Processing internal reasoning...'}
            
            # Yield only the visible content to the user
            if visible_content.strip():
                yield {'type': 'response', 'content': visible_content}
            else:
                # Fallback if no visible content
                yield {'type': 'response', 'content': "I've processed your request using internal reasoning."}
                
        except Exception as e:
            yield {'type': 'response', 'content': f"I understand your request. However, I encountered an issue connecting to the backend: {str(e)}. The thinking system is working correctly though!"}
    
    async def _process_with_agent(self, messages: List[Dict[str, str]]) -> AsyncGenerator[Dict[str, Any], None]:
        """Process messages with Qwen-Agent and yield structured updates."""
        try:
            # Convert messages to Qwen-Agent format
            agent_messages = self._convert_messages(messages)
            
            # Use Qwen-Agent to process with streaming
            responses = self.assistant.run(
                messages=agent_messages,
                stream=True
            )
            
            async for response in responses:
                # Parse Qwen-Agent response and convert to our format
                async for parsed_chunk in self._parse_agent_response(response):
                    yield parsed_chunk
                
        except Exception as e:
            self.logger.error("Error processing with agent", error=str(e))
            yield {
                'type': 'response',
                'content': f"Error: {str(e)}"
            }
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convert TUI messages to Qwen-Agent format."""
        # Basic conversion - may need adjustment based on Qwen-Agent requirements
        return messages
    
    async def _parse_agent_response(self, response: Any) -> AsyncGenerator[Dict[str, Any], None]:
        """Parse Qwen-Agent response into structured updates with thinking tag filtering."""
        # This is a simplified parser - would need to be expanded based on
        # actual Qwen-Agent response format
        
        if hasattr(response, 'choices') and response.choices:
            choice = response.choices[0]
            
            if hasattr(choice, 'delta') and choice.delta:
                # Streaming response content - filter thinking tags
                if hasattr(choice.delta, 'content') and choice.delta.content:
                    visible_content, thinking_content = self._filter_thinking_tags(choice.delta.content)
                    
                    # If there's thinking content, update internal state
                    if thinking_content:
                        self.state.full_thoughts += thinking_content
                        yield {
                            'type': 'thinking',
                            'content': 'Processing internal reasoning...'
                        }
                    
                    # Only yield visible content
                    if visible_content.strip():
                        yield {
                            'type': 'response',
                            'content': visible_content
                        }
                
                # Tool calls
                if hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
                    for tool_call in choice.delta.tool_calls:
                        yield {
                            'type': 'action_start',
                            'tool_name': tool_call.function.name,
                            'parameters': tool_call.function.arguments,
                            'call_id': tool_call.id
                        }
        
        # Handle tool execution results
        if hasattr(response, 'tool_results'):
            for result in response.tool_results:
                if result.get('error'):
                    yield {
                        'type': 'action_error',
                        'tool_name': result.get('tool_name', 'unknown'),
                        'error': result.get('error')
                    }
                else:
                    yield {
                        'type': 'action_complete',
                        'tool_name': result.get('tool_name', 'unknown'),
                        'result': result.get('result')
                    }
    
    def _update_thinking(self, thought: str):
        """Update thinking state and UI."""
        self.state.current_thought = thought
        self.state.full_thoughts += f"{thought}\n"
        
        if self.on_thinking_update:
            # Schedule the async callback
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.on_thinking_update(thought))
            except RuntimeError:
                pass  # No event loop running
    
    async def _handle_action_start(self, action_data: Dict[str, Any]):
        """Handle start of tool action."""
        tool_name = action_data.get('tool_name', 'unknown')
        parameters = action_data.get('parameters', {})
        call_id = action_data.get('call_id', '')
        
        self.state.active_tools.append(tool_name)
        
        if self.on_action_start:
            await self.on_action_start(call_id, tool_name, parameters)
    
    async def _handle_action_complete(self, action_data: Dict[str, Any]):
        """Handle completion of tool action."""
        tool_name = action_data.get('tool_name', 'unknown')
        result = action_data.get('result')
        call_id = action_data.get('call_id', '')
        
        if tool_name in self.state.active_tools:
            self.state.active_tools.remove(tool_name)
        
        self.state.completed_actions.append({
            'tool_name': tool_name,
            'result': result,
            'status': 'completed'
        })
        
        if self.on_action_complete:
            await self.on_action_complete(call_id, tool_name, result)
    
    async def _handle_action_error(self, action_data: Dict[str, Any]):
        """Handle error in tool action."""
        tool_name = action_data.get('tool_name', 'unknown')
        error = action_data.get('error', 'Unknown error')
        call_id = action_data.get('call_id', '')
        
        if tool_name in self.state.active_tools:
            self.state.active_tools.remove(tool_name)
        
        self.state.completed_actions.append({
            'tool_name': tool_name,
            'error': error,
            'status': 'error'
        })
        
        if self.on_action_error:
            await self.on_action_error(call_id, tool_name, error)
    
    def get_thinking_state(self) -> ThinkingState:
        """Get current thinking state."""
        return self.state
    
    def _filter_thinking_tags(self, content: str) -> tuple[str, str]:
        """Filter out <think> tags and return (visible_content, thinking_content)."""
        import re
        
        # Extract all thinking content
        thinking_pattern = r'<think>(.*?)</think>'
        thinking_matches = re.findall(thinking_pattern, content, re.DOTALL | re.IGNORECASE)
        thinking_content = '\n'.join(thinking_matches) if thinking_matches else ''
        
        # Remove thinking tags from visible content, preserving spacing
        visible_content = re.sub(thinking_pattern, '\n\n', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Clean up extra whitespace - normalize multiple newlines to double newlines
        visible_content = re.sub(r'\n{3,}', '\n\n', visible_content)
        visible_content = re.sub(r'^\n+|\n+$', '', visible_content)  # Remove leading/trailing newlines
        
        return visible_content, thinking_content
    
    def reset_thinking_state(self):
        """Reset thinking state for new conversation."""
        self.state = ThinkingState()