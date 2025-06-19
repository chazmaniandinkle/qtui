"""
Permission system with risk assessment for agent operations.

This module provides security controls and risk evaluation for tool usage,
following Claude Code's permission model.
"""
import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..logging import get_main_logger


class RiskLevel(Enum):
    """Risk levels for operations."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionAction(Enum):
    """Actions the permission system can take."""
    ALLOW = "allow"
    PROMPT = "prompt"
    BLOCK = "block"


@dataclass
class RiskAssessment:
    """Result of risk assessment for an operation."""
    risk_level: RiskLevel
    action: PermissionAction
    reasons: List[str]
    warnings: List[str]
    suggestions: List[str]


class CommandClassifier:
    """Classifies commands by risk level and type."""
    
    def __init__(self):
        self.logger = get_main_logger()
        
        # Critical risk patterns (always block or require confirmation)
        self.critical_patterns = [
            r'\brm\s+-rf\s+/',  # rm -rf /
            r'\bdd\s+if=/dev/zero',  # dd with zero device
            r'\bformat\s+',  # Format commands
            r'\bmkfs\.',  # Filesystem creation
            r'\bfdisk\s+',  # Disk partitioning
            r'\bsudo\s+rm\s+-rf',  # sudo rm -rf
            r':\(\)\{\s*:|&\s*\}',  # Fork bomb pattern
        ]
        
        # High risk patterns (require confirmation)
        self.high_risk_patterns = [
            r'\brm\s+-rf\s+',  # rm -rf (not root)
            r'\bsudo\s+',  # Any sudo command
            r'\bsu\s+',  # Switch user
            r'\bchmod\s+777',  # Overly permissive chmod
            r'\bchown\s+',  # Change ownership
            r'\bmv\s+.*\s+/',  # Move to root
            r'\bcp\s+.*\s+/',  # Copy to root
            r'>\s*/dev/sd[a-z]',  # Write to disk devices
            r'\bcrontab\s+',  # Modify cron
            r'\bkill\s+-9',  # Force kill
            r'\bpkill\s+',  # Kill processes by name
            r'\bkillall\s+',  # Kill all processes
        ]
        
        # Medium risk patterns (warn but allow)
        self.medium_risk_patterns = [
            r'\brm\s+.*\*',  # rm with wildcards
            r'\bmv\s+.*\*',  # mv with wildcards
            r'\bcp\s+-r\s+',  # Recursive copy
            r'\bfind\s+.*-delete',  # Find with delete
            r'\bxargs\s+rm',  # xargs rm
            r'>\s*/etc/',  # Write to /etc
            r'\bchmod\s+.*[0-7]{3}',  # chmod commands
            r'\btar\s+.*--overwrite',  # Tar with overwrite
            r'\bgit\s+reset\s+--hard',  # Hard git reset
            r'\bgit\s+clean\s+-f',  # Force git clean
        ]
        
        # Safe patterns (explicitly safe operations)
        self.safe_patterns = [
            r'^ls\s+',
            r'^cat\s+',
            r'^head\s+',
            r'^tail\s+',
            r'^grep\s+',
            r'^find\s+.*-type\s+f',  # Find files only
            r'^git\s+status',
            r'^git\s+log',
            r'^git\s+diff',
            r'^pwd$',
            r'^whoami$',
            r'^date$',
            r'^echo\s+',
            r'^which\s+',
            r'^type\s+',
        ]
        
        # File operation patterns
        self.file_write_patterns = [
            r'>\s*[^>]',  # Single redirect
            r'>>\s*',  # Append redirect
            r'\bcp\s+',  # Copy
            r'\bmv\s+',  # Move
            r'\btouch\s+',  # Touch
            r'\bmkdir\s+',  # Make directory
        ]
        
        # Network operation patterns
        self.network_patterns = [
            r'\bcurl\s+',
            r'\bwget\s+',
            r'\bssh\s+',
            r'\bscp\s+',
            r'\bftp\s+',
            r'\btelnet\s+',
            r'\bnc\s+',  # netcat
        ]

    def classify_command(self, command: str) -> RiskAssessment:
        """Classify a command and assess its risk."""
        command = command.strip()
        
        if not command:
            return RiskAssessment(
                risk_level=RiskLevel.SAFE,
                action=PermissionAction.ALLOW,
                reasons=["Empty command"],
                warnings=[],
                suggestions=[]
            )
        
        reasons = []
        warnings = []
        suggestions = []
        
        # Check for critical patterns
        for pattern in self.critical_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"Critical operation detected: {pattern}")
                warnings.append("This command could cause severe system damage")
                suggestions.append("Consider if this operation is really necessary")
                return RiskAssessment(
                    risk_level=RiskLevel.CRITICAL,
                    action=PermissionAction.BLOCK,
                    reasons=reasons,
                    warnings=warnings,
                    suggestions=suggestions
                )
        
        # Check for high risk patterns
        for pattern in self.high_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"High-risk operation: {pattern}")
                warnings.append("This command requires elevated privileges or could cause data loss")
                suggestions.append("Verify the command parameters carefully")
                return RiskAssessment(
                    risk_level=RiskLevel.HIGH,
                    action=PermissionAction.PROMPT,
                    reasons=reasons,
                    warnings=warnings,
                    suggestions=suggestions
                )
        
        # Check for medium risk patterns
        for pattern in self.medium_risk_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"Medium-risk operation: {pattern}")
                warnings.append("This command could modify or delete files")
                suggestions.append("Double-check file paths and parameters")
                return RiskAssessment(
                    risk_level=RiskLevel.MEDIUM,
                    action=PermissionAction.PROMPT,
                    reasons=reasons,
                    warnings=warnings,
                    suggestions=suggestions
                )
        
        # Check for safe patterns
        for pattern in self.safe_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                reasons.append(f"Safe read-only operation: {pattern}")
                return RiskAssessment(
                    risk_level=RiskLevel.SAFE,
                    action=PermissionAction.ALLOW,
                    reasons=reasons,
                    warnings=warnings,
                    suggestions=suggestions
                )
        
        # Check file operations
        is_file_write = any(re.search(pattern, command, re.IGNORECASE) 
                           for pattern in self.file_write_patterns)
        
        # Check network operations
        is_network = any(re.search(pattern, command, re.IGNORECASE) 
                        for pattern in self.network_patterns)
        
        # Classify based on operation type
        if is_network:
            reasons.append("Network operation detected")
            warnings.append("This command will make network connections")
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                action=PermissionAction.PROMPT,
                reasons=reasons,
                warnings=warnings,
                suggestions=["Verify network destinations are trusted"]
            )
        
        if is_file_write:
            reasons.append("File modification operation")
            warnings.append("This command will modify the filesystem")
            return RiskAssessment(
                risk_level=RiskLevel.LOW,
                action=PermissionAction.PROMPT,
                reasons=reasons,
                warnings=warnings,
                suggestions=["Ensure you have backups of important files"]
            )
        
        # Default to low risk for unknown commands
        reasons.append("Unknown command pattern")
        return RiskAssessment(
            risk_level=RiskLevel.LOW,
            action=PermissionAction.ALLOW,
            reasons=reasons,
            warnings=["Command pattern not recognized"],
            suggestions=["Verify command syntax and intent"]
        )


class FileAccessController:
    """Controls file access permissions."""
    
    def __init__(self, working_directory: Optional[str] = None):
        self.working_directory = Path(working_directory) if working_directory else Path.cwd()
        self.logger = get_main_logger()
        
        # Protected directories (require confirmation)
        self.protected_dirs = {
            "/etc", "/usr", "/var", "/boot", "/sys", "/proc", "/dev",
            "/bin", "/sbin", "/lib", "/lib64", "/opt"
        }
        
        # Critical files (block access)
        self.critical_files = {
            "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/boot/grub/grub.cfg",
            "/etc/fstab", "/etc/hosts", "/etc/ssh/sshd_config"
        }

    def assess_file_access(self, file_path: str, operation: str) -> RiskAssessment:
        """Assess the risk of accessing a file."""
        try:
            path = Path(file_path).resolve()
        except Exception:
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                action=PermissionAction.BLOCK,
                reasons=["Invalid file path"],
                warnings=["Cannot resolve file path"],
                suggestions=["Check path syntax"]
            )
        
        reasons = []
        warnings = []
        suggestions = []
        
        # Check for critical files
        if str(path) in self.critical_files:
            reasons.append(f"Access to critical system file: {path}")
            warnings.append("This file is critical for system operation")
            suggestions.append("System files should only be modified by administrators")
            return RiskAssessment(
                risk_level=RiskLevel.CRITICAL,
                action=PermissionAction.BLOCK,
                reasons=reasons,
                warnings=warnings,
                suggestions=suggestions
            )
        
        # Check for protected directories
        for protected_dir in self.protected_dirs:
            if str(path).startswith(protected_dir):
                reasons.append(f"Access to protected directory: {protected_dir}")
                warnings.append("This directory contains system files")
                suggestions.append("Ensure you have proper permissions")
                
                action = PermissionAction.BLOCK if operation in ("write", "delete") else PermissionAction.PROMPT
                risk = RiskLevel.HIGH if operation in ("write", "delete") else RiskLevel.MEDIUM
                
                return RiskAssessment(
                    risk_level=risk,
                    action=action,
                    reasons=reasons,
                    warnings=warnings,
                    suggestions=suggestions
                )
        
        # Check if outside working directory
        try:
            path.relative_to(self.working_directory)
        except ValueError:
            reasons.append("File outside working directory")
            warnings.append(f"File is outside the current working directory: {self.working_directory}")
            suggestions.append("Consider if access to external files is necessary")
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                action=PermissionAction.PROMPT,
                reasons=reasons,
                warnings=warnings,
                suggestions=suggestions
            )
        
        # File operations within working directory are generally safe
        reasons.append("File access within working directory")
        return RiskAssessment(
            risk_level=RiskLevel.SAFE,
            action=PermissionAction.ALLOW,
            reasons=reasons,
            warnings=warnings,
            suggestions=suggestions
        )


class PermissionManager:
    """Main permission manager coordinating all security checks."""
    
    def __init__(self, working_directory: Optional[str] = None, yolo_mode: bool = False):
        self.working_directory = working_directory
        self.yolo_mode = yolo_mode  # Skip all permissions (--dangerously-skip-permissions)
        self.logger = get_main_logger()
        
        self.command_classifier = CommandClassifier()
        self.file_controller = FileAccessController(working_directory)
        
        # Track permission decisions
        self.permission_history: List[Dict[str, Any]] = []

    def assess_tool_permission(self, tool_name: str, parameters: Dict[str, Any]) -> RiskAssessment:
        """Assess permission for tool usage."""
        if self.yolo_mode:
            return RiskAssessment(
                risk_level=RiskLevel.SAFE,
                action=PermissionAction.ALLOW,
                reasons=["YOLO mode enabled - all permissions bypassed"],
                warnings=["Safety checks disabled"],
                suggestions=[]
            )
        
        # Tool-specific permission checks
        if tool_name == "Bash":
            command = parameters.get("command", "")
            return self.command_classifier.classify_command(command)
        
        elif tool_name in ("Write", "Edit", "MultiEdit"):
            file_path = parameters.get("file_path", "")
            return self.file_controller.assess_file_access(file_path, "write")
        
        elif tool_name == "Read":
            file_path = parameters.get("file_path", "")
            return self.file_controller.assess_file_access(file_path, "read")
        
        elif tool_name in ("Grep", "Glob", "LS"):
            # Search tools are generally safe
            return RiskAssessment(
                risk_level=RiskLevel.SAFE,
                action=PermissionAction.ALLOW,
                reasons=["Read-only search operation"],
                warnings=[],
                suggestions=[]
            )
        
        elif tool_name == "Task":
            # Task delegation inherits permissions of subtasks
            return RiskAssessment(
                risk_level=RiskLevel.LOW,
                action=PermissionAction.ALLOW,
                reasons=["Task delegation - permissions checked at execution"],
                warnings=["Subtasks will be subject to their own permission checks"],
                suggestions=[]
            )
        
        else:
            # Unknown tools get medium risk
            return RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                action=PermissionAction.PROMPT,
                reasons=[f"Unknown tool: {tool_name}"],
                warnings=["Tool not recognized by permission system"],
                suggestions=["Verify tool functionality and safety"]
            )

    def log_permission_decision(self, tool_name: str, parameters: Dict[str, Any], 
                               assessment: RiskAssessment, decision: str) -> None:
        """Log a permission decision for audit purposes."""
        import time
        
        entry = {
            "timestamp": time.time(),
            "tool_name": tool_name,
            "parameters": parameters,
            "assessment": {
                "risk_level": assessment.risk_level.value,
                "action": assessment.action.value,
                "reasons": assessment.reasons,
                "warnings": assessment.warnings
            },
            "decision": decision
        }
        
        self.permission_history.append(entry)
        self.logger.info(f"Permission decision: {decision} for {tool_name}", 
                        risk_level=assessment.risk_level.value)

    def get_permission_summary(self) -> str:
        """Get a summary of recent permission decisions."""
        if not self.permission_history:
            return "No permission decisions recorded."
        
        summary = "## Recent Permission Decisions\n\n"
        for entry in self.permission_history[-10:]:
            timestamp = time.strftime("%H:%M:%S", time.localtime(entry["timestamp"]))
            tool_name = entry["tool_name"]
            decision = entry["decision"]
            risk_level = entry["assessment"]["risk_level"]
            
            summary += f"- **{timestamp}** [{risk_level.upper()}] {tool_name}: {decision}\n"
        
        return summary

    def enable_yolo_mode(self) -> None:
        """Enable YOLO mode (bypass all permissions)."""
        self.yolo_mode = True
        self.logger.warning("YOLO mode enabled - all safety checks bypassed!")

    def disable_yolo_mode(self) -> None:
        """Disable YOLO mode (re-enable permissions)."""
        self.yolo_mode = False
        self.logger.info("YOLO mode disabled - safety checks re-enabled")


# Global permission manager
_global_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(working_directory: Optional[str] = None, 
                          yolo_mode: bool = False) -> PermissionManager:
    """Get or create the global permission manager."""
    global _global_permission_manager
    if _global_permission_manager is None:
        _global_permission_manager = PermissionManager(working_directory, yolo_mode)
    return _global_permission_manager