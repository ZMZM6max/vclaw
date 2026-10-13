"""Tests for TaskManager task management system."""
import pytest
import sys
sys.path.insert(0, 'src')

from src.l5.task_manager import (
    TaskManager, Task, TaskStatus, TaskNotFoundError
)


class TestTaskCreation:
    """Tests for task creation."""

    def test_create_task_returns_task(self):
        """创建任务返回 Task 对象"""
        manager = TaskManager()
        task = manager.create("Test Task", "Description")

        assert isinstance(task, Task)
        assert task.subject == "Test Task"
        assert task.description == "Description"
        assert task.status == TaskStatus.PENDING

    def test_create_task_generates_id(self):
        """创建任务自动生成 UUID"""
        manager = TaskManager()
        task = manager.create("Test")

        assert isinstance(task.id, str)
        assert len(task.id) == 36  # UUID length

    def test_create_task_with_metadata(self):
        """创建任务带元数据"""
        manager = TaskManager()
        task = manager.create(
            "Test",
            metadata={"priority": "high", "category": "feature"}
        )

        assert task.metadata["priority"] == "high"
        assert task.metadata["category"] == "feature"

    def test_create_task_with_owner(self):
        """创建任务指定所有者"""
        manager = TaskManager()
        task = manager.create("Test", owner="agent-1")

        assert task.owner == "agent-1"


class TestTaskUpdate:
    """Tests for task updates."""

    def test_update_status(self):
        """更新任务状态"""
        manager = TaskManager()
        task = manager.create("Test")

        updated = manager.update(task.id, status=TaskStatus.IN_PROGRESS)

        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_subject(self):
        """更新任务标题"""
        manager = TaskManager()
        task = manager.create("Old Title")

        updated = manager.update(task.id, subject="New Title")

        assert updated.subject == "New Title"

    def test_update_metadata(self):
        """更新任务元数据"""
        manager = TaskManager()
        task = manager.create("Test")

        updated = manager.update(task.id, metadata={"result": "success"})

        assert updated.metadata["result"] == "success"

    def test_update_nonexistent_task_raises_error(self):
        """更新不存在的任务抛出异常"""
        manager = TaskManager()

        with pytest.raises(TaskNotFoundError):
            manager.update("nonexistent-id", status=TaskStatus.COMPLETED)


class TestTaskRetrieval:
    """Tests for task retrieval."""

    def test_get_task_by_id(self):
        """通过 ID 获取任务"""
        manager = TaskManager()
        task = manager.create("Test")

        retrieved = manager.get(task.id)

        assert retrieved is not None
        assert retrieved.id == task.id

    def test_get_nonexistent_task_returns_none(self):
        """获取不存在的任务返回 None"""
        manager = TaskManager()

        result = manager.get("nonexistent-id")

        assert result is None

    def test_list_all_tasks(self):
        """列出所有任务"""
        manager = TaskManager()
        manager.create("Task 1")
        manager.create("Task 2")

        tasks = manager.list_tasks()

        assert len(tasks) == 2

    def test_list_tasks_by_status(self):
        """按状态过滤任务"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        manager.update(task1.id, status=TaskStatus.COMPLETED)
        manager.create("Task 2")  # PENDING

        completed = manager.list_tasks(status=TaskStatus.COMPLETED)
        pending = manager.list_tasks(status=TaskStatus.PENDING)

        assert len(completed) == 1
        assert len(pending) == 1

    def test_list_tasks_by_owner(self):
        """按所有者过滤任务"""
        manager = TaskManager()
        manager.create("Task 1", owner="agent-1")
        manager.create("Task 2", owner="agent-2")

        tasks = manager.list_tasks(owner="agent-1")

        assert len(tasks) == 1
        assert tasks[0].owner == "agent-1"


class TestTaskDeletion:
    """Tests for task deletion."""

    def test_delete_task(self):
        """删除任务"""
        manager = TaskManager()
        task = manager.create("Test")

        result = manager.delete(task.id)

        assert result is True
        assert manager.get(task.id) is None

    def test_delete_nonexistent_task_returns_false(self):
        """删除不存在的任务返回 False"""
        manager = TaskManager()

        result = manager.delete("nonexistent-id")

        assert result is False

    def test_delete_removes_dependencies(self):
        """删除任务时移除依赖关系"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        manager.delete(task1.id)
        task2_after = manager.get(task2.id)

        assert task1.id not in task2_after.blocked_by


class TestTaskDependencies:
    """Tests for task dependencies."""

    def test_set_dependency(self):
        """设置任务依赖"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")

        result = manager.set_dependency(task2.id, task1.id)

        assert result is True
        assert task1.id in task2.blocked_by
        assert task2.id in task1.blocks

    def test_task_is_blocked(self):
        """检查任务是否被阻塞"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        assert task2.is_blocked() is True
        assert task1.is_blocked() is False

    def test_can_start_blocked_task(self):
        """被阻塞的任务不能开始"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        assert task2.can_start() is False
        assert task1.can_start() is True

    def test_remove_dependency(self):
        """移除任务依赖"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        manager.remove_dependency(task2.id, task1.id)

        assert task1.id not in task2.blocked_by
        assert task2.id not in task1.blocks

    def test_circular_dependency_detection(self):
        """循环依赖检测"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        # Trying to make task1 depend on task2 should raise error
        with pytest.raises(ValueError):
            manager.set_dependency(task1.id, task2.id)


class TestTaskCompletion:
    """Tests for task completion."""

    def test_complete_task(self):
        """完成任务"""
        manager = TaskManager()
        task = manager.create("Test")

        completed = manager.complete_task(task.id)

        assert completed.status == TaskStatus.COMPLETED

    def test_complete_task_stores_result(self):
        """完成任务存储结果"""
        manager = TaskManager()
        task = manager.create("Test")

        manager.complete_task(task.id, result="Success!")
        updated = manager.get(task.id)

        assert updated.metadata["result"] == "Success!"

    def test_complete_task_unblocks_dependents(self):
        """完成任务解除阻塞"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        manager.complete_task(task1.id)

        assert task2.is_blocked() is False
        assert task2.can_start() is True


class TestTaskQueries:
    """Tests for task queries."""

    def test_get_ready_tasks(self):
        """获取就绪任务"""
        manager = TaskManager()
        task1 = manager.create("Task 1")  # pending, not blocked
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)  # blocked
        task3 = manager.create("Task 3")
        manager.update(task3.id, status=TaskStatus.IN_PROGRESS)

        ready = manager.get_ready_tasks()

        assert len(ready) == 1
        assert ready[0].id == task1.id

    def test_list_blocked_tasks(self):
        """列出被阻塞的任务"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        task2 = manager.create("Task 2")
        manager.set_dependency(task2.id, task1.id)

        blocked = manager.list_tasks(blocked=True)
        not_blocked = manager.list_tasks(blocked=False)

        assert len(blocked) == 1
        assert len(not_blocked) == 1


class TestTaskStats:
    """Tests for task statistics."""

    def test_get_stats(self):
        """获取任务统计"""
        manager = TaskManager()
        task1 = manager.create("Task 1")
        manager.update(task1.id, status=TaskStatus.COMPLETED)
        manager.create("Task 2")  # pending
        manager.create("Task 3")  # pending

        stats = manager.get_stats()

        assert stats["completed"] == 1
        assert stats["pending"] == 2
        assert stats["total"] == 3


class TestTaskSerialization:
    """Tests for task serialization."""

    def test_task_to_dict(self):
        """任务转字典"""
        manager = TaskManager()
        task = manager.create("Test", metadata={"key": "value"})

        data = task.to_dict()

        assert data["subject"] == "Test"
        assert data["metadata"]["key"] == "value"
        assert data["status"] == "pending"

    def test_task_from_dict(self):
        """从字典创建任务"""
        original = Task(
            subject="Test",
            description="Description",
            status=TaskStatus.IN_PROGRESS,
            metadata={"priority": "high"}
        )

        data = original.to_dict()
        restored = Task.from_dict(data)

        assert restored.subject == original.subject
        assert restored.status == original.status
        assert restored.metadata == original.metadata
