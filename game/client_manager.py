import heapq
import threading
import time
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
import logging
import atexit
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ClientManager")


"""
.env文件格式示例：

# 默认配置
# 该配置会被优先加载
# 如果没有后缀的配置，则会加载后缀为1的配置
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL_NAME=

OPENAI_API_KEY_1=
OPENAI_BASE_URL_1=
OPENAI_MODEL_NAME_1=

# 之后后缀递增
OPENAI_API_KEY_2=
OPENAI_BASE_URL_2=
OPENAI_MODEL_NAME_2=

.......

可以无限增加列表
"""


class ClientManager:
    """
    用于管理游戏中的openai client实例
    该类实现了单例模式，确保在整个游戏中只有一个管理器实例。
    该实例负责创建和管理与OpenAI API的连接。
    该类使用一个优先队列来存储和管理多个client实例。
    优先队列按照每个client的使用状态进行排序，以便在需要时快速获取最少使用的client实例。
    该类还提供了获取和释放client实例的方法，以便在游戏中进行API调用。
    初始化的时候读取多个OPENAI_API_KEY,OPENAI_BASE_URL,OPENAI_MODEL_NAME以创建client实例
    该类还提供了一个方法来获取当前可用的client实例列表。
    在GameHelper中使用时，直接调用ClientManager.get_client()方法获取client实例。
    不存在线程问题，一个次调用结束之后迅速释放client实例
    """

    _instance = None
    _lock = threading.RLock()

    @dataclass(order=True)
    class _ClientItem:
        """用于在优先队列中存储client的数据类"""

        active_count: int = field(default=0)  # 当前活跃使用次数，作为排序依据
        total_count: int = field(default=0, compare=False)  # 累计使用次数
        client_id: str = field(default="", compare=False)  # 客户端ID
        client: Any = field(default=None, compare=False)  # OpenAI客户端实例
        client_name: str = field(default="", compare=False)  # 客户端名称
        client_model_name: str = field(default="", compare=False)  # 客户端模型名称
        # 不再需要在客户端项中存储时间

    def __new__(cls, *args, **kwargs):
        """实现单例模式"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ClientManager, cls).__new__(cls)
                cls._instance._initialized = False
                logger.info("Creating new singleton instance")
            return cls._instance

    def __init__(self):
        """初始化ClientManager"""
        # 避免重复初始化
        if getattr(self, "_initialized", False):
            logger.debug("Instance already initialized, skipping initialization")
            return

        with self._lock:
            logger.info("Initializing client manager")
            self._clients_heap = []  # 优先队列，存储可用的client
            self._clients_map = {}  # 所有client的字典，键为client_id

            # 添加使用时间跟踪
            self._usage_sessions = {}  # 使用会话字典，键为会话ID
            self._client_sessions = defaultdict(list)  # 每个客户端对应的活跃会话列表
            self._usage_time_log = []  # 使用时间记录
            self._time_log_file = os.path.join(
                os.path.dirname(__file__), "client_usage_times.json"
            )
            self._log_write_interval = 10  # 每10次释放操作写入一次文件
            self._log_write_counter = 0

            # 注册退出处理函数
            atexit.register(self._write_logs_on_exit)

            self._initialized = True

            # 初始化client实例
            self._init_clients()
            logger.info(
                f"Initialization complete with {len(self._clients_map)} clients in pool"
            )
            # 在初始化其他内容之前添加
            self._shutdown_flag = threading.Event()
            # 启动监控线程，定期检查未释放会话
            self._monitor_thread = threading.Thread(
                target=self._monitor_unreleased_sessions, daemon=True
            )
            self._monitor_thread.start()

    def _init_clients(self):
        """初始化client实例，按后缀匹配环境变量创建多个client实例"""
        logger.info("Starting client instances initialization")
        # 1. 首先尝试加载当前目录下的.env文件
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            logger.info(f"Loading .env file from: {env_path}")
            load_dotenv(env_path)
        else:
            # 尝试从项目根目录加载
            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..")
            )
            env_path = os.path.join(project_root, ".env")
            if os.path.exists(env_path):
                logger.info(f"Loading .env file from project root: {env_path}")
                load_dotenv(env_path)
            else:
                logger.warning(f".env file not found at project root: {env_path}.")
                # 尝试默认加载（搜索当前工作目录和父目录）
                if load_dotenv():
                    logger.info(
                        "Successfully loaded .env using default search (CWD or parent dirs)."
                    )
                else:
                    logger.warning(
                        "Could not find .env file. Will try using system environment variables."
                    )
                # 先尝试加载无后缀的客户端配置
        client_count = 0
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        model_name = os.environ.get("OPENAI_MODEL_NAME")

        if api_key and base_url and model_name:
            logger.info(f"Found default OpenAI configuration without suffix")
            try:
                logger.info(f"Creating default client with model: {model_name}")
                new_client = OpenAI(
                    api_key=api_key, base_url=base_url, timeout=None  # 设置为无超时限制
                )
                try:
                    # 验证客户端是否正常工作
                    # models = new_client.models.list()
                    logger.info(f"Default client connection verified successfully")
                except Exception as conn_err:
                    raise Exception(f"Default API connection test failed: {conn_err}")

                # 创建client_id
                client_count += 1
                client_id = f"client_{client_count}"
                self._add_client(client_id, new_client, model_name)
                logger.info(
                    f"Successfully created default client, client_id={client_id}"
                )
            except Exception as e:
                logger.error(f"Error creating default client: {e}", exc_info=True)
        else:
            logger.info(
                "No default OpenAI configuration found, checking suffix-based configs"
            )

        # 检查环境变量是否成功加载
        loaded_env = False
        for key in os.environ:
            if key.startswith("OPENAI_API_KEY_"):
                loaded_env = True
                logger.info(f"Found indexed variable {key}")
                break

        if loaded_env:
            logger.info("Successfully loaded .env file")
        else:
            logger.warning("No OPENAI_API_KEY_X variables found in environment")

        # 直接按顺序从1开始尝试加载客户端配置
        suffix_num = 1

        # 持续尝试递增的后缀直到找不到配置
        while True:
            api_key = os.environ.get(f"OPENAI_API_KEY_{suffix_num}")  # 注意下划线
            base_url = os.environ.get(f"OPENAI_BASE_URL_{suffix_num}")  # 注意下划线
            model_name = os.environ.get(f"OPENAI_MODEL_NAME_{suffix_num}")  # 注意下划线

            logger.info(
                f"Checking config for suffix {suffix_num}: API key={bool(api_key)}, base URL={bool(base_url)}, model name={bool(model_name)}"
            )

            # 如果找不到这个后缀的配置，则认为已经到达末尾，退出循环
            if not api_key or not base_url or not model_name:
                logger.info(f"No more configurations found after suffix {suffix_num}")
                break

            try:
                logger.info(
                    f"Creating client with suffix {suffix_num}, model: {model_name}"
                )
                new_client = OpenAI(api_key=api_key, base_url=base_url)
                try:
                    # 执行一个轻量级的操作，验证客户端是否正常工作
                    # models = new_client.models.list()
                    # 不尝试获取长度，只确认API调用成功
                    logger.info(f"Client connection verified successfully")
                except Exception as conn_err:
                    raise Exception(f"API connection test failed: {conn_err}")

                # 创建client_id
                client_count += 1
                client_id = f"client_{client_count}"
                self._add_client(client_id, new_client, model_name)
                logger.info(
                    f"Successfully created client with suffix {suffix_num}, client_id={client_id}"
                )
            except Exception as e:
                logger.error(
                    f"Error creating client with suffix {suffix_num}: {e}",
                    exc_info=True,
                )

            # 尝试下一个后缀
            suffix_num += 1

        logger.info(f"Client initialization complete. Created {client_count} clients.")

    def _add_client(self, client_id, client_instance, model_name):
        """将client实例添加到管理器中"""
        with self._lock:
            logger.info(f"Adding client {client_id} with model {model_name} to pool")

            # 创建客户端项
            client_item = self._ClientItem(
                active_count=0,
                total_count=0,
                client_id=client_id,
                client=client_instance,
                client_model_name=model_name,
            )

            # 添加到堆和字典中
            heapq.heappush(self._clients_heap, client_item)
            self._clients_map[client_id] = client_item

            logger.info(
                f"Client {client_id} added to pool. Pool size now: {len(self._clients_map)}"
            )

    def get_client(self):
        """
        获取一个client实例
        返回一个元组: (client_instance, client_id, client_model_name)
        """
        with self._lock:
            if not self._clients_heap:
                logger.error("No available OpenAI clients in pool")
                return None, None, None

            # 取出使用次数最少的client
            client_item = heapq.heappop(self._clients_heap)

            # 增加使用计数
            client_item.active_count += 1
            client_item.total_count += 1

            # 创建会话ID并记录开始时间
            session_id = str(uuid.uuid4())
            start_time = time.time()

            # 记录会话信息
            self._usage_sessions[session_id] = {
                "client_id": client_item.client_id,
                "start_time": start_time,
                "model": client_item.client_model_name,
            }

            # 添加到客户端活跃会话列表
            self._client_sessions[client_item.client_id].append(session_id)

            # 将client_item放回优先队列
            heapq.heappush(self._clients_heap, client_item)

            logger.info(
                f"Retrieved client {client_item.client_id} (model: {client_item.client_model_name}). "
                f"Active count: {client_item.active_count}, Total: {client_item.total_count}, "
                f"Session: {session_id}"
            )

            # 将会话ID附加到client_id后返回，用于释放时识别
            return (
                client_item.client,
                f"{client_item.client_id}:{session_id}",
                client_item.client_model_name,
            )

    def release_client(self, client_id_with_session):
        """释放一个client实例"""
        with self._lock:
            # 解析client_id和session_id
            try:
                client_id, session_id = client_id_with_session.split(":", 1)
            except ValueError:
                # 兼容旧代码，可能没有session_id
                client_id = client_id_with_session
                session_id = None
                logger.warning(
                    f"Release called without session ID for client {client_id}"
                )

            if client_id not in self._clients_map:
                logger.warning(f"Attempting to release unknown client: {client_id}")
                return

            # 获取client项
            client_item = self._clients_map[client_id]

            # 处理使用时间记录
            if session_id and session_id in self._usage_sessions:
                # 计算使用时间
                session_data = self._usage_sessions.pop(session_id)
                end_time = time.time()
                usage_time = end_time - session_data["start_time"]

                # 从活跃会话列表中移除
                if session_id in self._client_sessions[client_id]:
                    self._client_sessions[client_id].remove(session_id)

                # 记录使用时间
                log_entry = {
                    "client_id": client_id,
                    "session_id": session_id,
                    "model": session_data["model"],
                    "start_time": session_data["start_time"],
                    "end_time": end_time,
                    "usage_time": usage_time,
                    "completed": True,  # 标记为正常完成
                }
                self._usage_time_log.append(log_entry)

                # 立即写入日志文件，确保不会丢失
                try:
                    self._write_logs_to_file()
                    logger.debug(
                        f"Successfully logged usage for client {client_id}, session {session_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to write usage log: {e}")
                    # 即使写入失败，也继续执行释放逻辑

                logger.info(
                    f"Client {client_id} session {session_id} usage time: {usage_time:.4f} seconds"
                )
            else:
                logger.warning(
                    f"No session data found for client {client_id}, session {session_id}"
                )

            # 减少活跃使用计数
            if client_item.active_count > 0:
                client_item.active_count -= 1
                logger.info(
                    f"Released client {client_id}. Active count: {client_item.active_count}"
                )
            else:
                logger.warning(f"Client {client_id} already has zero active count")

    def _write_logs_to_file(self):
        """将使用时间记录写入文件"""
        try:
            if not self._usage_time_log:
                return

            # 读取现有日志
            existing_logs = []
            if os.path.exists(self._time_log_file):
                try:
                    with open(self._time_log_file, "r") as f:
                        existing_logs = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    logger.warning(
                        f"Could not read existing log file, creating new one"
                    )
                    existing_logs = []

            # 添加新日志
            existing_logs.extend(self._usage_time_log)

            # 写入文件
            with open(self._time_log_file, "w") as f:
                json.dump(existing_logs, f, indent=2)

            logger.debug(f"Wrote {len(self._usage_time_log)} log entries to file")

            # 清空内存中的日志
            self._usage_time_log = []

        except Exception as e:
            logger.error(f"Error writing usage time logs to file: {e}", exc_info=True)

    def _write_logs_on_exit(self):
        """在程序退出时写入剩余的日志"""
        with self._lock:
            # 处理所有未完成的会话
            current_time = time.time()
            for session_id, session_data in list(self._usage_sessions.items()):
                # 为未完成的会话创建记录，标记为未完成
                usage_time = current_time - session_data["start_time"]
                self._usage_time_log.append(
                    {
                        "client_id": session_data["client_id"],
                        "session_id": session_id,
                        "model": session_data["model"],
                        "start_time": session_data["start_time"],
                        "end_time": current_time,
                        "usage_time": usage_time,
                        "completed": False,  # 标记为未完成的会话
                    }
                )

            # 写入所有日志
            if self._usage_time_log:
                self._write_logs_to_file()
                logger.info(f"Wrote {len(self._usage_time_log)} remaining logs on exit")

    def _monitor_unreleased_sessions(self):
        """监控未释放的会话，定期清理"""
        while not self._shutdown_flag.is_set():
            try:
                current_time = time.time()
                timeout_threshold = 300  # 5分钟超时

                with self._lock:
                    expired_sessions = []
                    for session_id, session_data in self._usage_sessions.items():
                        if (
                            current_time - session_data["start_time"]
                            > timeout_threshold
                        ):
                            expired_sessions.append(session_id)

                    # 清理过期会话
                    for session_id in expired_sessions:
                        logger.warning(f"Force releasing expired session: {session_id}")
                        session_data = self._usage_sessions.pop(session_id)

                        # 记录强制释放的使用时间
                        usage_time = current_time - session_data["start_time"]
                        log_entry = {
                            "client_id": session_data["client_id"],
                            "session_id": session_id,
                            "model": session_data["model"],
                            "start_time": session_data["start_time"],
                            "end_time": current_time,
                            "usage_time": usage_time,
                            "completed": False,  # 标记为强制结束
                            "reason": "timeout",
                        }
                        self._usage_time_log.append(log_entry)

                        # 减少客户端活跃计数
                        client_id = session_data["client_id"]
                        if client_id in self._clients_map:
                            client_item = self._clients_map[client_id]
                            if client_item.active_count > 0:
                                client_item.active_count -= 1

                # 休眠一段时间，但可中断
                self._shutdown_flag.wait(60)  # 每分钟检查一次
            except Exception as e:
                logger.error(f"监控会话时出错: {e}")
                time.sleep(120)  # 出错时延长休眠时间

    def get_client_stats(self):
        """获取所有client的统计信息"""
        with self._lock:
            stats = {
                client_id: {
                    "active_count": item.active_count,
                    "total_count": item.total_count,
                    "model_name": item.client_model_name,
                }
                for client_id, item in self._clients_map.items()
            }
            logger.info(f"Retrieved client stats for {len(stats)} clients")
            return stats

    def get_client_count(self):
        """获取client总数"""
        with self._lock:
            count = len(self._clients_map)
            logger.info(f"Total client count: {count}")
            return count

    def get_available_count(self):
        """获取当前可用的client数量"""
        with self._lock:
            count = len(self._clients_heap)
            logger.info(f"Available client count: {count}")
            return count

    def log_client_status(self):
        """记录当前所有客户端状态（用于调试）"""
        with self._lock:
            logger.info("======== CLIENT MANAGER STATUS ========")
            logger.info(f"Total clients: {len(self._clients_map)}")
            logger.info(f"Available clients: {len(self._clients_heap)}")

            # 按照活跃度排序的客户端列表
            sorted_clients = sorted(
                self._clients_map.values(),
                key=lambda x: (x.active_count, x.total_count),
            )

            for idx, client in enumerate(sorted_clients):
                logger.info(
                    f"Client #{idx+1}: ID={client.client_id}, Model={client.client_model_name}, "
                    f"Active={client.active_count}, Total={client.total_count}"
                )
            logger.info("======================================")

    def shutdown(self):
        """优雅关闭ClientManager，确保资源正确释放"""
        logger.info("正在关闭ClientManager...")

        # 设置关闭标志，通知监控线程终止
        self._shutdown_flag.set()

        # 等待监控线程结束
        if hasattr(self, "_monitor_thread") and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)  # 最多等待2秒

        # 首先移除 atexit 注册的处理函数，避免重复调用
        try:
            atexit.unregister(self._write_logs_on_exit)
            logger.info("已移除退出时的日志写入处理函数")
        except Exception as e:
            logger.warning(f"移除退出处理函数失败: {str(e)}")

        # 处理所有未完成的会话并写入日志
        try:
            self._write_logs_on_exit()
        except Exception as e:
            logger.error(f"写入退出日志时出错: {str(e)}")

        # 清空所有客户端会话
        with self._lock:
            self._usage_sessions.clear()
            self._client_sessions.clear()

            # 重置所有客户端的活跃计数
            for client_id, client_item in self._clients_map.items():
                if client_item.active_count > 0:
                    logger.warning(
                        f"重置客户端 {client_id} 的活跃计数从 {client_item.active_count} 到 0"
                    )
                    client_item.active_count = 0

        logger.info("ClientManager已关闭")


def get_client_manager():
    """获取ClientManager单例实例"""
    # 使用双重检查锁定模式确保线程安全和效率
    if ClientManager._instance is None:
        with ClientManager._lock:  # 这里的锁是 ClientManager 类的锁，用于保护单例实例化过程
            if ClientManager._instance is None:
                logger.info("Creating new ClientManager singleton instance.")
                try:
                    instance = ClientManager()  # 调用 __new__ 和 __init__
                    # __init__ 内部会调用 _init_clients

                    # 检查初始化是否成功（例如，是否有客户端成功创建）
                    # _initialized 标志在 __init__ 中设置
                    if not getattr(instance, "_initialized", False):
                        # 这个情况理论上不应该发生，因为 __init__ 会设置它，除非 __init__ 提前异常退出
                        logger.error(
                            "ClientManager instance flag '_initialized' is false after creation."
                        )
                        raise RuntimeError(
                            "ClientManager failed to initialize properly."
                        )

                    if instance.get_client_count() == 0:
                        logger.error(
                            "ClientManager initialized, but no OpenAI clients are available. "
                            "Check configurations and logs."
                        )
                        # 决定是否在这里抛出异常，或者允许管理器存在但无可用客户端
                        # 抛出异常更早暴露问题
                        raise RuntimeError(
                            "No OpenAI clients available after ClientManager initialization. "
                            "Please check API configurations and network connectivity."
                        )
                    ClientManager._instance = instance
                    logger.info(
                        "ClientManager singleton instance created successfully."
                    )
                except Exception as e:
                    logger.critical(
                        f"Failed to create ClientManager singleton: {e}", exc_info=True
                    )
                    # 如果创建失败，_instance 仍然是 None，下次调用会重试或持续失败
                    raise  # 将异常重新抛出，让调用者知道初始化失败

    return ClientManager._instance
