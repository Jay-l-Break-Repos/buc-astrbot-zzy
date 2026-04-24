import abc
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
from astrbot.core.db.po import Stats, LLMHistory, ATRIVision, Conversation, NotificationTemplate


@dataclass
class BaseDatabase(abc.ABC):
    """
    数据库基类
    """

    def __init__(self) -> None:
        pass

    def insert_base_metrics(self, metrics: dict):
        """插入基础指标数据"""
        self.insert_platform_metrics(metrics["platform_stats"])
        self.insert_plugin_metrics(metrics["plugin_stats"])
        self.insert_command_metrics(metrics["command_stats"])
        self.insert_llm_metrics(metrics["llm_stats"])

    @abc.abstractmethod
    def insert_platform_metrics(self, metrics: dict):
        """插入平台指标数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def insert_plugin_metrics(self, metrics: dict):
        """插入插件指标数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def insert_command_metrics(self, metrics: dict):
        """插入指令指标数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def insert_llm_metrics(self, metrics: dict):
        """插入 LLM 指标数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def update_llm_history(self, session_id: str, content: str, provider_type: str):
        """更新 LLM 历史记录。当不存在 session_id 时插入"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_llm_history(
        self, session_id: str = None, provider_type: str = None
    ) -> List[LLMHistory]:
        """获取 LLM 历史记录, 如果 session_id 为 None, 返回所有"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_base_stats(self, offset_sec: int = 86400) -> Stats:
        """获取基础统计数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_total_message_count(self) -> int:
        """获取总消息数"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_grouped_base_stats(self, offset_sec: int = 86400) -> Stats:
        """获取基础统计数据(合并)"""
        raise NotImplementedError

    @abc.abstractmethod
    def insert_atri_vision_data(self, vision_data: ATRIVision):
        """插入 ATRI 视觉数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_atri_vision_data(self) -> List[ATRIVision]:
        """获取 ATRI 视觉数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_atri_vision_data_by_path_or_id(
        self, url_or_path: str, id: str
    ) -> ATRIVision:
        """通过 url 或 path 获取 ATRI 视觉数据"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_conversation_by_user_id(self, user_id: str, cid: str) -> Conversation:
        """通过 user_id 和 cid 获取 Conversation"""
        raise NotImplementedError

    @abc.abstractmethod
    def new_conversation(self, user_id: str, cid: str):
        """新建 Conversation"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_conversations(self, user_id: str) -> List[Conversation]:
        raise NotImplementedError

    @abc.abstractmethod
    def update_conversation(self, user_id: str, cid: str, history: str):
        """更新 Conversation"""
        raise NotImplementedError

    @abc.abstractmethod
    def delete_conversation(self, user_id: str, cid: str):
        """删除 Conversation"""
        raise NotImplementedError

    @abc.abstractmethod
    def update_conversation_title(self, user_id: str, cid: str, title: str):
        """更新 Conversation 标题"""
        raise NotImplementedError

    @abc.abstractmethod
    def update_conversation_persona_id(self, user_id: str, cid: str, persona_id: str):
        """更新 Conversation Persona ID"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_all_conversations(
        self, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取所有对话，支持分页"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_filtered_conversations(
        self,
        page: int = 1,
        page_size: int = 20,
        platforms: List[str] = None,
        message_types: List[str] = None,
        search_query: str = None,
        exclude_ids: List[str] = None,
        exclude_platforms: List[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取筛选后的对话列表"""
        raise NotImplementedError

    # -------------------------------------------------------------------------
    # Notification Template CRUD
    # -------------------------------------------------------------------------

    @abc.abstractmethod
    def create_notification_template(self, name: str, body: str) -> NotificationTemplate:
        """创建一个新的通知模板。

        Args:
            name: 模板的唯一名称。
            body: 模板正文，可包含 {{ variable }} 占位符。

        Returns:
            新创建的 NotificationTemplate 对象。

        Raises:
            ValueError: 当 name 已存在时抛出。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_notification_templates(self) -> List[NotificationTemplate]:
        """返回所有通知模板列表（按创建时间升序）。"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_notification_template_by_id(self, template_id: int) -> Optional[NotificationTemplate]:
        """通过主键 ID 查询单个通知模板。

        Returns:
            对应的 NotificationTemplate，若不存在则返回 None。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def update_notification_template(
        self, template_id: int, name: str = None, body: str = None
    ) -> Optional[NotificationTemplate]:
        """更新通知模板的 name 和/或 body 字段。

        Args:
            template_id: 要更新的模板 ID。
            name: 新名称（可选）。
            body: 新正文（可选）。

        Returns:
            更新后的 NotificationTemplate，若 ID 不存在则返回 None。

        Raises:
            ValueError: 当新 name 与其他模板冲突时抛出。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delete_notification_template(self, template_id: int) -> bool:
        """删除指定 ID 的通知模板。

        Returns:
            True 表示删除成功，False 表示 ID 不存在。
        """
        raise NotImplementedError
