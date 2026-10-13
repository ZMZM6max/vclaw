"""Task management system for L5 Tools & Capabilities.

Provides task lifecycle management with dependencies, status tracking, and metadata.
"""
import uuid
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task definition with lifecycle management.

    Attributes:
        id: Unique task identifier (UUID)
        subject: Brief task title
        description: Detailed task description
        status: Current task status
        created_at: Creation timestamp
        updated_at: Last update timestamp
        metadata: Additional task metadata
        active_form: Present continuous description (for spinner display)
        owner: Agent ID that owns this task
        blocks: List of task IDs this task blocks
        blocked_by: List of task IDs blocking this task
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""
    description: str = ""
    status: TaskStatus = field(default=TaskStatus.PENDING)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active_form: Optional[str] = None
    owner: Optional[str] = None
    blocks: List[str] = field(default_factory=list)
    blocked_by: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "active_form": self.active_form,
            "owner": self.owner,
            "blocks": self.blocks.copy(),
            "blocked_by": self.blocked_by.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create task from dictionary."""
        task = cls(
            id=data.get("id", str(uuid.uuid4())),
            subject=data.get("subject", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            active_form=data.get("active_form"),
            owner=data.get("owner"),
            blocks=data.get("blocks", []),
            blocked_by=data.get("blocked_by", [])
        )
        return task

    def is_blocked(self) -> bool:
        """Check if task is blocked by dependencies."""
        return len(self.blocked_by) > 0

    def can_start(self) -> bool:
        """Check if task can be started (not blocked and pending)."""
        return not self.is_blocked() and self.status == TaskStatus.PENDING

    def __repr__(self) -> str:
        return f"Task({self.id[:8]}: [{self.status.value}] {self.subject})"


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""
    pass


class TaskManager:
    """Task manager for lifecycle management and dependency tracking."""

    def __init__(self):
        """Initialize the task manager."""
        self._tasks: Dict[str, Task] = {}

    def create(self, subject: str, description: str = "", **kwargs) -> Task:
        """Create a new task.

        Args:
            subject: Brief task title
            description: Detailed task description
            **kwargs: Additional task attributes (metadata, owner, active_form, etc.)

        Returns:
            The created Task object
        """
        task = Task(
            subject=subject,
            description=description,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata=kwargs.get("metadata", {}),
            active_form=kwargs.get("active_form"),
            owner=kwargs.get("owner"),
            blocks=kwargs.get("blocks", []),
            blocked_by=kwargs.get("blocked_by", [])
        )
        self._tasks[task.id] = task
        return task

    def update(self, task_id: str, status: TaskStatus = None, **kwargs) -> Task:
        """Update a task's status and attributes.

        Args:
            task_id: The task ID to update
            status: New status (optional)
            **kwargs: Additional attributes to update

        Returns:
            The updated Task object

        Raises:
            TaskNotFoundError: If task not found
        """
        task = self._tasks.get(task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")

        if status:
            task.status = status

        if "subject" in kwargs:
            task.subject = kwargs["subject"]
        if "description" in kwargs:
            task.description = kwargs["description"]
        if "metadata" in kwargs:
            task.metadata.update(kwargs["metadata"])
        if "active_form" in kwargs:
            task.active_form = kwargs["active_form"]
        if "owner" in kwargs:
            task.owner = kwargs["owner"]

        task.updated_at = datetime.now()
        return task

    def list_tasks(
        self,
        status: TaskStatus = None,
        owner: str = None,
        blocked: bool = None
    ) -> List[Task]:
        """List tasks with optional filtering.

        Args:
            status: Filter by status
            owner: Filter by owner
            blocked: Filter by blocked state (True=blocked, False=not blocked)

        Returns:
            List of Task objects matching filters
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]
        if owner:
            tasks = [t for t in tasks if t.owner == owner]
        if blocked is not None:
            tasks = [t for t in tasks if t.is_blocked() == blocked]

        # Sort by created_at descending (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def get(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: The task ID

        Returns:
            Task object or None if not found
        """
        return self._tasks.get(task_id)

    def delete(self, task_id: str) -> bool:
        """Delete a task.

        Args:
            task_id: The task ID to delete

        Returns:
            True if deleted, False if not found
        """
        if task_id in self._tasks:
            # Remove from other tasks' blocked_by and blocks lists
            for task in self._tasks.values():
                if task_id in task.blocked_by:
                    task.blocked_by.remove(task_id)
                if task_id in task.blocks:
                    task.blocks.remove(task_id)

            del self._tasks[task_id]
            return True
        return False

    def set_dependency(self, task_id: str, blocked_by: str) -> bool:
        """Set a task dependency (task_id is blocked by blocked_by).

        Args:
            task_id: The task that is blocked
            blocked_by: The task that is blocking

        Returns:
            True if dependency set, False if either task not found

        Raises:
            ValueError: If circular dependency detected
        """
        task = self._tasks.get(task_id)
        blocker = self._tasks.get(blocked_by)

        if not task or not blocker:
            return False

        # Check for circular dependency
        if self._would_create_cycle(task_id, blocked_by):
            raise ValueError(f"Circular dependency: {task_id} already blocks {blocked_by}")

        # Add dependency
        if blocked_by not in task.blocked_by:
            task.blocked_by.append(blocked_by)
        if task_id not in blocker.blocks:
            blocker.blocks.append(task_id)

        task.updated_at = datetime.now()
        blocker.updated_at = datetime.now()
        return True

    def remove_dependency(self, task_id: str, blocked_by: str) -> bool:
        """Remove a task dependency.

        Args:
            task_id: The task that is blocked
            blocked_by: The task that is blocking

        Returns:
            True if dependency removed, False if not found
        """
        task = self._tasks.get(task_id)
        blocker = self._tasks.get(blocked_by)

        if not task or not blocker:
            return False

        if blocked_by in task.blocked_by:
            task.blocked_by.remove(blocked_by)
        if task_id in blocker.blocks:
            blocker.blocks.remove(task_id)

        task.updated_at = datetime.now()
        blocker.updated_at = datetime.now()
        return True

    def _would_create_cycle(self, task_id: str, blocked_by: str) -> bool:
        """Check if adding this dependency would create a cycle."""
        # If task_id already blocks blocked_by (directly or transitively),
        # then adding blocked_by -> task_id would create a cycle
        visited = set()
        stack = [task_id]

        while stack:
            current = stack.pop()
            if current == blocked_by:
                return True
            if current in visited:
                continue
            visited.add(current)

            current_task = self._tasks.get(current)
            if current_task:
                stack.extend(current_task.blocks)

        return False

    def get_ready_tasks(self) -> List[Task]:
        """Get all tasks that are ready to start (not blocked, status=pending)."""
        return [t for t in self._tasks.values() if t.can_start()]

    def complete_task(self, task_id: str, result: str = None) -> Task:
        """Complete a task and unblock dependent tasks.

        Args:
            task_id: The task to complete
            result: Optional result description

        Returns:
            The completed task

        Raises:
            TaskNotFoundError: If task not found
        """
        task = self.update(task_id, status=TaskStatus.COMPLETED)

        if result:
            task.metadata["result"] = result

        # Unblock tasks that were blocked by this one
        for blocked_task_id in task.blocks:
            blocked_task = self._tasks.get(blocked_task_id)
            if blocked_task and task_id in blocked_task.blocked_by:
                blocked_task.blocked_by.remove(task_id)
                blocked_task.updated_at = datetime.now()

        return task

    def get_stats(self) -> Dict[str, int]:
        """Get task statistics."""
        stats = {status.value: 0 for status in TaskStatus}
        for task in self._tasks.values():
            stats[task.status.value] += 1
        stats["total"] = len(self._tasks)
        stats["blocked"] = sum(1 for t in self._tasks.values() if t.is_blocked())
        return stats

    def clear(self) -> None:
        """Remove all tasks."""
        self._tasks.clear()

    def __len__(self) -> int:
        """Return number of tasks."""
        return len(self._tasks)

    def __repr__(self) -> str:
        return f"TaskManager(tasks={len(self._tasks)})"
