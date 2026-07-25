import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:11111/v1")
os.environ.setdefault("LLM_MODEL", "test-model")

from database import CREATE_SESSIONS_TABLE, CREATE_USERS_TABLE, get_db
from deps import verify_api_key
from routers import batch as batch_router
from routers import context as context_router
from routers import project as project_router
from routers import threads as threads_router
from routers import users as users_router


class _FakeLLMClient:
    """伪造的 LLM 客户端，用于上下文组装。"""

    async def generate_response(self, messages, response_model=None):
        return {"summary": "stub summary"}


class _FakeGraphiti:
    """伪造的 Graphiti 实例，避免测试依赖真实图数据库。"""

    def __init__(self):
        self.driver = object()
        self.llm_client = _FakeLLMClient()
        self._episodes: list[SimpleNamespace] = []

    async def add_episode(self, **kwargs):
        """空实现：写入 episode 时直接忽略。"""
        pass

    async def retrieve_episodes(self, reference_time, last_n, group_ids):
        """返回内存中的伪造 episode 列表。"""
        return self._episodes[:last_n]

    async def remove_episode(self, uuid):
        """空实现：删除 episode 时直接忽略。"""
        pass

    async def search(self, query, group_ids, num_results):
        """空实现：图搜索返回空列表。"""
        return []


class ZepCloudCompatTests(unittest.TestCase):
    """验证新增的 zep-cloud SDK 兼容端点。"""

    def setUp(self):
        """每个测试用例前创建独立 SQLite 文件与 FastAPI 应用。"""
        self._fd, self._db_path = tempfile.mkstemp(suffix=".db")
        os.close(self._fd)

        asyncio.run(self._init_db())

        self.app = FastAPI()
        self.app.state.graphiti = _FakeGraphiti()

        # 注册需要测试的路由
        self.app.include_router(threads_router.router)
        self.app.include_router(threads_router.message_router)
        self.app.include_router(users_router.router)
        self.app.include_router(project_router.router)
        self.app.include_router(context_router.router)
        self.app.include_router(batch_router.router)

        # 覆盖依赖：使用独立数据库并关闭鉴权
        self.app.dependency_overrides[get_db] = self._override_get_db
        self.app.dependency_overrides[verify_api_key] = lambda: None

        self.client = TestClient(self.app)

    def tearDown(self):
        """清理测试数据库。"""
        self.client.close()
        try:
            os.remove(self._db_path)
        except FileNotFoundError:
            pass

    async def _init_db(self):
        """初始化测试数据库的表结构。"""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(CREATE_USERS_TABLE)
            await db.execute(CREATE_SESSIONS_TABLE)
            await db.commit()

    async def _override_get_db(self):
        """提供指向临时数据库的连接。"""
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        try:
            yield db
        finally:
            await db.close()

    def test_thread_lifecycle(self):
        """测试 Thread 的创建、列表、获取与删除。"""
        create_resp = self.client.post("/api/v2/threads", json={"user_id": "user-1"})
        self.assertEqual(create_resp.status_code, 200)
        thread = create_resp.json()
        self.assertEqual(thread["user_id"], "user-1")
        self.assertIn("thread_id", thread)

        list_resp = self.client.get("/api/v2/threads")
        self.assertEqual(list_resp.status_code, 200)
        list_data = list_resp.json()
        self.assertEqual(list_data["total_count"], 1)
        self.assertEqual(len(list_data["threads"]), 1)

        get_resp = self.client.get(f"/api/v2/threads/{thread['thread_id']}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["thread_id"], thread["thread_id"])

        del_resp = self.client.delete(f"/api/v2/threads/{thread['thread_id']}")
        self.assertEqual(del_resp.status_code, 200)

        get_after = self.client.get(f"/api/v2/threads/{thread['thread_id']}")
        self.assertEqual(get_after.status_code, 404)

    def test_thread_messages(self):
        """测试向 Thread 添加消息并获取消息列表。"""
        create_resp = self.client.post("/api/v2/threads", json={"user_id": "user-1"})
        thread_id = create_resp.json()["thread_id"]

        add_resp = self.client.post(
            f"/api/v2/threads/{thread_id}/messages",
            json={
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                ]
            },
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertTrue(add_resp.json()["ok"])

        get_resp = self.client.get(f"/api/v2/threads/{thread_id}/messages")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertIn("messages", data)

    def test_user_threads_and_warm(self):
        """测试用户创建、用户 Thread 列表以及 warm 端点。"""
        user_resp = self.client.post(
            "/api/v2/users",
            json={"user_id": "user-2", "email": "u2@example.com"},
        )
        self.assertEqual(user_resp.status_code, 200)

        thread_resp = self.client.post("/api/v2/threads", json={"user_id": "user-2"})
        self.assertEqual(thread_resp.status_code, 200)

        user_threads = self.client.get("/api/v2/users/user-2/threads")
        self.assertEqual(user_threads.status_code, 200)
        self.assertEqual(user_threads.json()["total_count"], 1)

        warm_resp = self.client.get("/api/v2/users/user-2/warm")
        self.assertEqual(warm_resp.status_code, 200)
        self.assertTrue(warm_resp.json()["success"])

        node_resp = self.client.get("/api/v2/users/user-2/node")
        self.assertEqual(node_resp.status_code, 200)
        self.assertEqual(node_resp.json()["user_id"], "user-2")

    def test_context_template_crud(self):
        """测试上下文模板的增删改查。"""
        create_resp = self.client.post(
            "/api/v2/context-templates",
            json={"name": "test", "template": "{{context}}"},
        )
        self.assertEqual(create_resp.status_code, 200)
        template_id = create_resp.json()["template_id"]

        list_resp = self.client.get("/api/v2/context-templates")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["total_count"], 1)

        get_resp = self.client.get(f"/api/v2/context-templates/{template_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["template_id"], template_id)

        update_resp = self.client.put(
            f"/api/v2/context-templates/{template_id}",
            json={"template": "updated {{context}}"},
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["template"], "updated {{context}}")

        del_resp = self.client.delete(f"/api/v2/context-templates/{template_id}")
        self.assertEqual(del_resp.status_code, 200)

        get_after = self.client.get(f"/api/v2/context-templates/{template_id}")
        self.assertEqual(get_after.status_code, 404)

    def test_batch_crud(self):
        """测试 Batch 的创建、列表、获取与删除。"""
        create_resp = self.client.post("/api/v2/batches", json={"description": "test batch"})
        self.assertEqual(create_resp.status_code, 200)
        batch_id = create_resp.json()["batch_id"]

        list_resp = self.client.get("/api/v2/batches")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["total_count"], 1)

        get_resp = self.client.get(f"/api/v2/batches/{batch_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["batch_id"], batch_id)

        add_resp = self.client.post(
            f"/api/v2/batches/{batch_id}/items",
            json=[{"operation": "add_message", "payload": {"x": 1}}],
        )
        self.assertEqual(add_resp.status_code, 200)
        self.assertEqual(add_resp.json()["total_count"], 1)

        process_resp = self.client.post(f"/api/v2/batches/{batch_id}/process")
        self.assertEqual(process_resp.status_code, 200)
        self.assertEqual(process_resp.json()["status"], "processed")

        del_resp = self.client.delete(f"/api/v2/batches/{batch_id}")
        self.assertEqual(del_resp.status_code, 200)

    def test_project_info(self):
        """测试项目信息读取与更新。"""
        get_resp = self.client.get("/api/v2/projects/info")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["name"], "OpenZep")

        patch_resp = self.client.patch(
            "/api/v2/projects/info",
            json={"default_time_zone": "Asia/Shanghai"},
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["default_time_zone"], "Asia/Shanghai")


if __name__ == "__main__":
    unittest.main()
