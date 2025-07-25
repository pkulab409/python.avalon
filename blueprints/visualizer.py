from flask import (
    Blueprint,
    render_template,
    request,
    abort,
    jsonify,
    redirect,
    url_for,
    flash,
    current_app,
    send_file,
)
from flask_login import login_required, current_user
import json
import os
from datetime import datetime
from config.config import Config
import math
from copy import deepcopy
import uuid
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
import logging
from pathlib import Path
from database.models import Battle, User, BattlePlayer
from database.action import get_battle_by_id
import threading
from jinja2 import Undefined

# 创建蓝图
visualizer_bp = Blueprint("visualizer", __name__, template_folder="templates")


def clean_undefined_objects(obj):
    """递归清理数据中的 Undefined 对象"""

    if isinstance(obj, Undefined):
        return None
    elif isinstance(obj, dict):
        return {k: clean_undefined_objects(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_undefined_objects(item) for item in obj]
    else:
        return obj


@visualizer_bp.route("/game/<game_id>")
def game_index(game_id):
    """游戏对局索引页面 - 简单重定向到重放页面"""
    return redirect(url_for("visualizer.game_replay", game_id=game_id))


@visualizer_bp.route("/replay/<game_id>")
def game_replay(game_id):
    """游戏对局重放页面"""

    def _get_user_names(game_id) -> list:
        from database import get_battle_by_id

        battle_obj = get_battle_by_id(game_id)
        if not battle_obj:
            # 数据库查不到，从日志文件推断
            data_dir = Config._yaml_config.get("DATA_DIR", "./data")
            log_file = os.path.join(data_dir, f"{game_id}/archive_game_{game_id}.json")
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        game_data = json.load(f)
                    for event in game_data:
                        if event.get("event_type") == "RoleAssign":
                            roles_data = event.get("event_data", {})
                            # 创建按player_id索引的用户名数组
                            max_players = 7
                            usernames = ["未知"] * max_players
                            for pid_str in roles_data.keys():
                                pid = int(pid_str)
                                if 1 <= pid <= max_players:
                                    usernames[pid - 1] = f"玩家{pid}"
                            return usernames
                except Exception as e:
                    print(f"自动提取用户名失败: {e}")
            # 实在没有就返回空
            return []

        # 获取所有BattlePlayer并创建按position索引的用户名数组
        # 确保数组索引与player_id的对应关系：player_usernames[player_id - 1] = username
        max_players = 7  # 阿瓦隆最多7个玩家
        usernames = ["未知"] * max_players  # 初始化

        try:
            battle_players = battle_obj.players.all()
            for bp in battle_players:
                if bp.user and bp.user.username and bp.position is not None:
                    # position应该等于游戏中的player_id，从1开始
                    if 1 <= bp.position <= max_players:
                        usernames[bp.position - 1] = bp.user.username
        except Exception as e:
            print(f"获取用户名失败: {e}")
            # 如果出错，使用原来的方法作为后备
            player_objs = battle_obj.get_players()
            return [player.username for player in player_objs]

        return usernames

    try:
        # 处理示例回放的特殊情况
        if game_id == "example":
            # 获取 visualizer.py 文件所在的目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建相对于 visualizer.py 的 example replay 文件路径
            # visualizer.py 在 blueprints/
            # 目标文件在 static/example/
            # 需要向上走一层 (..) 到 /，再进入 static/example/
            example_replay_path = os.path.join(
                current_dir, "..", "static/example", "archive_game_example.json"
            )
            # 标准化路径 (例如，处理 '..')
            log_file = os.path.normpath(example_replay_path)

            # 检查计算出的路径是否存在
            if not os.path.exists(log_file):
                flash("示例回放文件不存在，请确保已正确配置。", "warning")
                return render_template("error.html", message="示例回放文件不存在")

        else:
            # 原有的游戏日志文件路径构建逻辑
            log_file = os.path.join(
                Config._yaml_config.get("DATA_DIR", "./data"),
                f"{game_id}/archive_game_{game_id}.json",
            )

        print(f"尝试读取文件: {log_file}")
        print(f"文件存在: {os.path.exists(log_file)}")

        # 检查文件是否存在
        if not os.path.exists(log_file):
            flash(f"错误：找不到对局记录文件 {os.path.basename(log_file)}", "danger")
            return render_template("error.html", message="对局记录不存在")

        # 读取游戏日志文件
        with open(log_file, "r", encoding="utf-8") as f:
            try:
                game_data = json.load(f)
            except json.JSONDecodeError as json_err:
                flash(
                    f"错误：无法解析对局记录文件 {log_file}。错误：{json_err}", "danger"
                )
                return render_template(
                    "error.html", message=f"加载对局记录时出错: 无效的JSON文件"
                )

        # 验证JSON基本格式
        if not isinstance(game_data, list) or not game_data:
            flash(f"错误：对局记录文件 {log_file} 格式无效或为空。", "danger")
            return render_template(
                "error.html", message=f"加载对局记录时出错: 文件格式无效或为空"
            )

        # 提取基本游戏信息
        game_info = extract_game_info(game_data, game_id)

        # 处理游戏事件
        game_events = process_game_events(game_data)

        # 在返回模板之前清理数据
        game_events = clean_undefined_objects(game_events)
        game_info = clean_undefined_objects(game_info)

        return render_template(
            "visualizer/medieval_style_replay_page.html",
            game_id=game_id,
            game_info=game_info,
            game_events=game_events,
            player_usernames=_get_user_names(game_id),
        )
    except Exception as e:
        flash(f"加载对局记录时发生意外错误: {str(e)}", "danger")
        # Log the full error for debugging
        print(f"Error loading replay {game_id}: {e}")
        import traceback

        traceback.print_exc()
        return render_template("error.html", message=f"加载对局记录时出错: {str(e)}")


@visualizer_bp.route("/upload", methods=["GET"])
def upload_game_json():
    """游戏对局JSON上传页面"""
    return render_template("visualizer/upload.html")


@visualizer_bp.route("/upload", methods=["POST"])
def process_upload():
    """处理上传的游戏对局JSON文件"""
    if "game_json" not in request.files:
        flash("未选择文件", "danger")
        return redirect(request.url)

    file = request.files["game_json"]
    if file.filename == "":
        flash("未选择文件", "danger")
        return redirect(request.url)

    if file and allowed_json_file(file.filename):
        try:
            # 读取文件内容进行验证
            file_content = file.read()
            try:
                json_data = json.loads(file_content)
            except json.JSONDecodeError:
                flash("无效的JSON文件", "danger")
                return redirect(request.url)

            file.seek(0)  # 重置文件指针以便保存

            # 验证是否符合游戏对局格式
            if not is_valid_game_json(json_data):
                flash("上传的JSON文件格式不符合游戏对局要求", "danger")
                return redirect(request.url)

            # 为上传的文件生成唯一ID (使用原始文件名中的ID，如果存在且符合格式)
            # 尝试从文件名提取 game_id
            base_name = os.path.splitext(secure_filename(file.filename))[0]
            if base_name.startswith("game_") and base_name.endswith("_archive"):
                potential_id = base_name[len("game_") : -len("_archive")]
                # 简单的UUID格式检查 (不严格)
                if len(potential_id) > 10:  # Basic check
                    game_id = potential_id
                    filename = f"{game_id}/archive_game_{game_id}.json"
                    print(f"Using game_id from filename: {game_id}")
                else:
                    game_id = str(uuid.uuid4())
                    filename = f"{game_id}/archive_game_{game_id}.json"
                    print(f"Generated new game_id: {game_id}")
            else:
                game_id = str(uuid.uuid4())
                filename = f"{game_id}/archive_game_{game_id}.json"
                print(f"Generated new game_id: {game_id}")

            # 确保目录存在
            data_dir = Config._yaml_config.get("DATA_DIR", "./data")
            os.makedirs(data_dir, exist_ok=True)

            # 保存文件
            file_path = os.path.join(data_dir, filename)

            # 确保目标子目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            if not os.path.exists(file_path):
                file.save(file_path)

            flash("文件上传成功，正在跳转到可视化页面", "success")
            return redirect(url_for("visualizer.game_replay", game_id=game_id))

        except Exception as e:
            flash(f"上传失败: {str(e)}", "danger")
            print(f"Upload error: {e}")
            import traceback

            traceback.print_exc()
            return redirect(request.url)
    else:
        flash("只允许上传JSON文件", "danger")
        return redirect(request.url)


def allowed_json_file(filename):
    """检查是否为允许的JSON文件"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "json"


def is_valid_game_json(json_data):
    """验证JSON是否符合游戏对局格式 (基于 observer.py)"""
    if not isinstance(json_data, list) or len(json_data) == 0:
        print("Validation failed: Not a list or empty.")
        return False

    # 可以添加更多检查，例如是否存在 RoleAssign, RoundStart 等
    has_role_assign = any(
        event.get("event_type") == "RoleAssign" for event in json_data
    )
    if not has_role_assign:
        print(
            "Validation warning: Missing RoleAssign event."
        )  # Warning, not necessarily invalid

    return True


def extract_game_info(game_data, game_id_from_url):
    """从游戏数据中提取基本信息 (基于 observer.py)"""
    game_info = {
        "game_id": game_id_from_url,  # Use ID from URL/filename as primary
        "player_count": 0,
        "map_size": 0,
        "start_time": None,
        "end_time": None,
        "winner": "未知",
        "rounds_played": 0,
        "roles": {},
        "win_reason": "未知",
        "blue_wins": 0,
        "red_wins": 0,
        "is_completed": False,  # Assume not completed until GameResult is found
        "start_time_formatted": "未知",
        "end_time_formatted": "未知",
        "duration": "未知",
    }
    last_round_num = 0
    last_scoreboard = None

    # 从游戏开始事件提取信息
    for event in game_data:
        event_type = event.get("event_type")
        event_data = event.get("event_data")
        timestamp = event.get("timestamp")  # Get timestamp from event

        if event_type == "GameStart":
            game_info["player_count"] = event.get("player_count", 0)
            game_info["map_size"] = event.get("map_size", 0)
            game_info["start_time"] = timestamp  # Use event timestamp
            # Use battle_id from event if needed, but prefer URL one
            # game_info["game_id"] = event.get("battle_id", game_id_from_url)

        elif event_type == "RoleAssign":
            # Ensure keys are strings if they are numbers in JSON
            game_info["roles"] = (
                {str(k): v for k, v in event_data.items()}
                if isinstance(event_data, dict)
                else {}
            )

        elif event_type == "RoundStart":
            if isinstance(event_data, int):
                last_round_num = max(last_round_num, event_data)

        elif event_type == "ScoreBoard":
            if isinstance(event_data, list) and len(event_data) == 2:
                last_scoreboard = event_data  # Store the latest scoreboard

        # 从游戏结束事件提取信息
        elif event_type == "GameResult":
            if isinstance(event_data, (list, tuple)) and len(event_data) >= 2:
                game_info["winner"] = event_data[
                    0
                ].lower()  # Ensure lowercase 'blue' or 'red'
                game_info["win_reason"] = event_data[1]
                game_info["end_time"] = timestamp  # Use event timestamp
                game_info["is_completed"] = True

        elif event_type == "FinalScore":
            if isinstance(event_data, list) and len(event_data) == 2:
                game_info["blue_wins"] = event_data[0]
                game_info["red_wins"] = event_data[1]
                game_info["rounds_played"] = (
                    game_info["blue_wins"] + game_info["red_wins"]
                )

    # 如果游戏未正常结束 (没有 GameResult)
    if not game_info["is_completed"]:
        game_info["end_time_formatted"] = "游戏未正常结束"
        game_info["win_reason"] = "游戏未记录结束状态"
        # 使用最后记录的回合数和计分板（如果存在）
        game_info["rounds_played"] = last_round_num
        if last_scoreboard:
            game_info["blue_wins"] = last_scoreboard[0]
            game_info["red_wins"] = last_scoreboard[1]
            # Try to infer winner based on last score if game didn't finish
            if game_info["blue_wins"] >= 3:
                game_info["winner"] = "blue"
                game_info["win_reason"] = "游戏中断时蓝方已达3胜"
            elif game_info["red_wins"] >= 3:
                game_info["winner"] = "red"
                game_info["win_reason"] = "游戏中断时红方已达3胜"

    # 格式化时间戳
    time_format_in = "%Y-%m-%d %H:%M:%S"  # Format from observer
    time_format_out = "%Y-%m-%d %H:%M"  # Shorter format for display

    if game_info["start_time"]:
        try:
            # Handle potential fractional seconds if present
            dt_start = datetime.strptime(
                game_info["start_time"].split(".")[0], time_format_in
            )
            game_info["start_time_formatted"] = dt_start.strftime(time_format_out)
        except (ValueError, TypeError):
            game_info["start_time_formatted"] = str(game_info["start_time"])  # Fallback

    if game_info["end_time"] and game_info["is_completed"]:
        try:
            dt_end = datetime.strptime(
                game_info["end_time"].split(".")[0], time_format_in
            )
            game_info["end_time_formatted"] = dt_end.strftime(time_format_out)
        except (ValueError, TypeError):
            # Keep "游戏未正常结束" or fallback
            if game_info["end_time_formatted"] == "未知":
                game_info["end_time_formatted"] = str(game_info["end_time"])

    # 计算游戏时长
    if game_info["start_time"] and game_info["end_time"] and game_info["is_completed"]:
        try:
            start = datetime.strptime(
                game_info["start_time"].split(".")[0], time_format_in
            )
            end = datetime.strptime(game_info["end_time"].split(".")[0], time_format_in)
            duration = end - start
            total_seconds = duration.total_seconds()
            if total_seconds >= 0:
                minutes = math.floor(total_seconds / 60)
                seconds = math.floor(total_seconds % 60)
                game_info["duration"] = f"{minutes}分{seconds}秒"
            else:
                game_info["duration"] = "时间戳错误"
        except (ValueError, TypeError):
            game_info["duration"] = "无法计算"
    elif not game_info["is_completed"]:
        game_info["duration"] = "未完成"

    # Ensure roles has string keys for template
    game_info["roles"] = {str(k): v for k, v in game_info.get("roles", {}).items()}

    return game_info


def process_game_events(game_data):
    """处理游戏事件用于可视化 (基于 observer.py)"""
    events_by_round = {}
    round_num = 0
    assassination_info = None

    for event in game_data:
        event_type = event.get("event_type")
        event_data = event.get("event_data")

        # --- Special Events Handling ---
        if event_type == "Assass":
            if isinstance(event_data, list) and len(event_data) == 4:
                assassination_info = {
                    "assassin": str(event_data[0]),  # Ensure string ID
                    "target": str(event_data[1]),  # Ensure string ID
                    "target_role": event_data[2],
                    "success": event_data[3] == "Success",
                }
            continue  # Processed special event

        # --- Round Based Events Handling ---
        if event_type == "RoundStart":
            if isinstance(event_data, int):
                round_num = event_data
                if round_num > 0 and round_num not in events_by_round:
                    # Initialize round structure when RoundStart is encountered
                    events_by_round[round_num] = {
                        "round": round_num,
                        "leader": None,
                        "team_members": [],
                        # Combined list of events: [(type, data)]
                        "events": [],
                        # {success: bool, fail_votes: int}
                        "mission_execution": None,
                        # {success: bool} - Simplified for badge
                        "mission_result": None,
                    }
            continue  # Processed RoundStart

        # Only process other events if a valid round structure exists
        if round_num > 0 and round_num in events_by_round:
            current_round = events_by_round[round_num]

            if event_type == "Leader":
                current_round["leader"] = str(event_data)  # Ensure string ID
                print(
                    f"Leader event - Round {round_num}, Leader: {current_round['leader']}"
                )
            elif event_type == "TeamPropose":
                # Ensure members are strings
                members = (
                    [str(m) for m in event_data] if isinstance(event_data, list) else []
                )
                current_round["team_members"] = members
                # 使用当前回合的leader信息，如果没有则设为None
                leader_id = current_round.get("leader")
                # 调试信息
                print(
                    f"TeamPropose event - Round {round_num}, Leader: {leader_id}, Members: {members}"
                )
                current_round["events"].append(
                    {
                        "type": "team_propose",
                        "data": {
                            "leader": leader_id,
                            "team_members": members,
                        },
                    }
                )
            elif event_type == "PublicSpeech":
                if isinstance(event_data, (list, tuple)) and len(event_data) == 2:
                    # 标记为公开发言
                    current_round["events"].append(
                        {
                            "type": "speech",
                            "data": (
                                str(event_data[0]),
                                event_data[1],
                                "public",
                                ["ALL"],
                            ),
                        }
                    )
            elif event_type == "PublicVote":
                if isinstance(event_data, (list, tuple)) and len(event_data) == 2:
                    # 检查是否需要创建新的投票尝试
                    if (
                        not current_round["events"]
                        or current_round["events"][-1]["type"] != "vote_attempt"
                    ):
                        current_round["events"].append(
                            {
                                "type": "vote_attempt",
                                "data": {
                                    "votes": {},
                                    "approved": None,
                                    "approve_count": 0,
                                    "reject_count": 0,
                                },
                            }
                        )
                    # 更新最新的投票尝试
                    current_round["events"][-1]["data"]["votes"][str(event_data[0])] = (
                        event_data[1] == "Approve"
                    )
            elif event_type == "PublicVoteResult":
                if isinstance(event_data, list) and len(event_data) == 2:
                    # 确保存在投票尝试
                    if (
                        not current_round["events"]
                        or current_round["events"][-1]["type"] != "vote_attempt"
                    ):
                        current_round["events"].append(
                            {
                                "type": "vote_attempt",
                                "data": {
                                    "votes": {},
                                    "approved": None,
                                    "approve_count": 0,
                                    "reject_count": 0,
                                },
                            }
                        )
                    # 更新投票结果
                    current_round["events"][-1]["data"]["approve_count"] = event_data[0]
                    current_round["events"][-1]["data"]["reject_count"] = event_data[1]
            elif event_type == "MissionApproved":
                # 确保存在投票尝试
                if (
                    not current_round["events"]
                    or current_round["events"][-1]["type"] != "vote_attempt"
                ):
                    current_round["events"].append(
                        {
                            "type": "vote_attempt",
                            "data": {
                                "votes": {},
                                "approved": None,
                                "approve_count": 0,
                                "reject_count": 0,
                            },
                        }
                    )
                # 更新投票结果
                current_round["events"][-1]["data"]["approved"] = True
            elif event_type == "MissionRejected":
                # 确保存在投票尝试
                if (
                    not current_round["events"]
                    or current_round["events"][-1]["type"] != "vote_attempt"
                ):
                    current_round["events"].append(
                        {
                            "type": "vote_attempt",
                            "data": {
                                "votes": {},
                                "approved": None,
                                "approve_count": 0,
                                "reject_count": 0,
                            },
                        }
                    )
                # 更新投票结果
                current_round["events"][-1]["data"]["approved"] = False
            elif event_type == "MissionVote":
                if isinstance(event_data, dict):
                    fail_votes = sum(1 for vote in event_data.values() if not vote)
                    # Initialize mission_execution if not already done
                    if current_round["mission_execution"] is None:
                        current_round["mission_execution"] = {}
                    current_round["mission_execution"]["fail_votes"] = fail_votes
            elif event_type == "MissionResult":
                if isinstance(event_data, (list, tuple)) and len(event_data) == 2:
                    success = event_data[1] == "Success"
                    if current_round["mission_execution"] is None:
                        current_round["mission_execution"] = {}
                    current_round["mission_execution"]["success"] = success
                    # Also store simplified mission result for badge color
                    current_round["mission_result"] = {"success": success}

    # Convert dict to list and sort by round number
    game_events_list = sorted(events_by_round.values(), key=lambda x: x["round"])

    # Append assassination info at the end if it exists
    if assassination_info:
        game_events_list.append(
            {
                "round": "assassination",  # Special key for template logic
                "assassination": assassination_info,
            }
        )

    return game_events_list
