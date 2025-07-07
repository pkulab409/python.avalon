import threading
import os
from datetime import datetime
from inspect import getfile


settings = {
    "referee.AvalonReferee": 0,
    "observer.Observer": 0,
    "avalon_game_helper.GameHelper": 0,
    "1": 0,
    "2": 0,
    "3": 0,
    "4": 0,
    "5": 0,
    "6": 0,
    "7": 0,
    "8": 0,
    "9": 0,
    "10": 0,
    "11": 0,
    "12": 0,
}


class DebugDecorator:
    def __init__(self, battle_id):
        # 获取当前脚本的绝对路径
        current_file = os.path.abspath(__file__)
        filename = f"_decorator_out_{battle_id}.log"  # 日志文件名

        # 增强路径安全性检测
        current_file = os.path.abspath(
            getfile(self.__class__)
        )  # 准确获取类定义文件路径
        target_dir = os.path.abspath(  # 构造绝对路径
            os.path.join(os.path.dirname(current_file), "..", "data", str(battle_id))
        )

        # 路径验证与创建
        self.filename = os.path.join(target_dir, filename)
        os.makedirs(target_dir, exist_ok=True)  # 自动创建所有缺失目录

        print(f"✅ 目标目录确认：{os.path.abspath(target_dir)}")
        print(f"📁 日志文件将保存至：{os.path.abspath(self.filename)}")

        self.local_data = threading.local()
        self.lock = threading.RLock()

    def _log(self, event_type, func_name, stack, args, result=None):
        """日志处理方法"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        thread_id = threading.get_ident()

        # 控制台输出(有颜色)
        console_msg = (
            f"[{timestamp}] [Thread-{thread_id}] "
            f"[{event_type}] 函数名: \033[34m{func_name}\033[0m\n"
            f"      嵌套层级: {len(stack)}\n"
            f"      调用关系: \033[33m{' → '.join(stack)}\033[0m\n"
            f"      接收参数: args={args}\n"
            f"      返回值: \033[32m{result}\033[0m\n"
        )
        print(console_msg)

        # 文件输出（无颜色）
        file_msg = (
            f"[{timestamp}] [Thread-{thread_id}] [{event_type}] "
            f"函数名: {func_name} | 层级: {len(stack)} | "
            f"调用链: {'→'.join(stack)} | 参数: args={args} | "
            f"返回值: {result}\n"
        )

        with self.lock:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(file_msg)

    def __call__(self, func):
        def wrapper(*args):

            # 初始化result，设置未initial，与None区分开，同时避免未定义
            result = "initial"

            if not hasattr(self.local_data, "stack"):
                self.local_data.stack = []

            self.local_data.stack.append(func.__name__)
            current_stack = self.local_data.stack.copy()

            self._log("Call", func.__name__, current_stack, args)

            try:
                result = func(*args)
            finally:
                self.local_data.stack.pop()
                self._log("Done", func.__name__, current_stack, args, result=result)

            return result

        return wrapper

    def decorate_instance(self, instance):
        """动态装饰一个实例的所有非私有方法"""
        for name in dir(instance):
            if not name.startswith("_"):  # 跳过私有方法
                attr = getattr(instance, name)
                if callable(attr):
                    setattr(instance, name, self(attr))  # 用__call__装饰方法
        return instance

    # 会报错目前
    def _decorate_instance(self, instance):
        """动态装饰一个实例的所有私有方法"""
        for name in dir(instance):
            if name.startswith("_"):  # 跳过非私有方法
                attr = getattr(instance, name)
                if callable(attr):
                    setattr(instance, name, self(attr))  # 用__call__装饰方法
        return instance
