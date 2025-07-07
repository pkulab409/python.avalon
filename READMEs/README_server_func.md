🧭大作业对战平台 用户文档

---

# 调用服务器功能

服务器为大家提供了辅助 API 工具包，用户可以通过 [指导](./code_submission_guide.md#可调用的辅助API) 导入。为与后文保持一致，我们在这里重复一遍大家所写的游戏代码的 import 过程。

```python
from game.avalon_game_helper import (
    write_into_private,
    read_private_lib,
    read_public_lib,
    askLLM
)
```

## 对局中的公有库  

对局中， **公有库（Public Library）** 提供了对局中的公开信息，这对代码的决策分析非常重要。

### 函数调用示例

```python
public_records = read_public_lib()
# 返回示例：
# [
#   {"type": "game_start", "game_id": 12345, "player_count": 7, "map_size": 9},
#   {"type": "night_phase_complete"},
#   ...
# ]
```

### 返回数据格式详解

`read_public_lib()` 返回一个 **Python 列表**，列表由一串 **Python 字典**组成，每个字典代表一条游戏事件。

每个代表游戏事件的字典里，**一定会出现 `"type"` 键**。它对应不同的值，表示不同的游戏事件类型。

`"type"` 键对应的值不同，字典中**余下的键值对**也不同。`"type"` 键对应的值与后续键值对的对应关系如下：

#### **`"game_start"`**：游戏开始
  - <span style="font-size: small;">（后面的键值对见下，冒号前面的字符串是键，冒号后面表示值的数据类型）</span>
  - `"game_id": int`：游戏唯一编号
  - `"player_count": int`：玩家总数
  - `"map_size": int`：地图尺寸

#### **`"night_phase_complete"`**：夜晚阶段结束，无额外字段
  - ~~（你总不会认为能在此处偷偷摸摸地拿到所有角色的身份吧？）~~

#### **`"mission_start"`**：任务回合开始
  - `"round: int"`：回合序号（1~5）
  - `"leader": int`：本回合队长玩家ID
  - `"member_count": int`

#### **`"team_proposed"`**：队长提名团队
  - `"round": int`：回合序号
  - `"vote_round": int`：本回合第几次投票
  - `"leader": int`：提名者（队长）ID
  - `"members": list[int]`：被提名的玩家ID列表
  - \* 从这里开始，调用公有库显得重要了。我们在这里附上 Python 示例：

  ```python
  # 假如第2轮发言前，需要查看第1轮的最后一次队长提名团队信息
  # 其他代码省略……
  self.cur_round = 2

  def say() -> str:
      '''发言'''
      last_round_team = {}
      public_records = read_public_lib()
      idx = len(public_records) - 1
      while True:
          if public_records[idx]["type"] == "team_proposed" and public_records[idx]["round"] == self.cur_round - 1:
              last_round_team["leader"] = public_records[idx]["leader"]
              last_round_team["members"] = public_records[idx]["members"]
              break
          if idx < 0:  # 请大家注意异常处理！
              return "我还在思考。"
          idx -= 1
      return f"请大家参考上轮队伍信息。队长是{last_round_team["leader"]}号，队员是{" ".join(map(str, last_round_team["members"]))}，对比这一轮，说明……"
  ```

#### **`"global_speech"`**：全图广播发言
  - `"round": int`：回合序号
  - `"speeches": list[list]`：发言列表，格式 `[[player_id, text], [player_id, text], …]`

#### **`"movement"`**：玩家移动记录
  - `"round": int`：回合序号
  - `"movements": list[dict]`：列表，每项是一个字典，键值对如下：
    - `"player_id": int`：移动的玩家ID
    - `"requested_moves": list[str]`：请求的移动方向列表
    - `"executed_moves": list[str]`：实际执行的移动列表
    - `"final_position": list[int]`：最终坐标 `[x, y]`

#### **`limited_speech`**：有听力范围限制的发言
  - `"round": int`：回合序号

#### **`"public_vote"`**：公投表决
  - `"round": int`：回合序号
  - `"votes": dict`：字典，键为玩家ID（字符串类型），值为 `True`/`False`
  - `"approve_count": int`：赞成票数
  - `"result": str`：结果字符串，可能为 `"approved"`、`"rejected"`

#### **`"team_rejected"`**：团队被否决
  - `"round": int`：回合序号
  - `"vote_round": int`：本回合第几次投票
  - `"approve_count": int`：当次赞成票数
  - `"next_leader": int`：下一个队长玩家ID

#### **`"consecutive_rejections"`**：连续否决触发强制组队
  - `"round": int`：回合序号

#### **`"mission_execution"`**：任务执行
  - `"round": int`：回合序号
  - `"fail_votes": int`：失败票数
  - `"success": bool`：布尔，`True` 表示任务成功

#### **`"mission_result"`**：任务结果总结
  - `"round":int`：回合序号
  - `"result": str`：`"success"` 或 `"fail"`
  - `"blue_wins": int`：目前为止，蓝方胜利轮数
  - `"red_wins": int`：目前为止，红方胜利轮数

#### **`"assassination"`**：刺杀阶段
  - `"assassin": int`：刺客玩家ID
  - `"target": int`：目标玩家ID
  - `"target_role": str`：目标角色名称（公开）
  - `"success": bool`：布尔，是否刺杀成功

#### **`"game_end"`**：游戏结束
  - `"result": dict`：字典，包含以下键值对：
    - `"blue_wins": int`、`"red_wins": int`（轮数）
    - `"rounds_played": int`（总回合数）
    - `"roles": dict`：玩家角色映射 `{player_id: role}`
    - `"public_log_file": str`：完整日志文件路径
    - `"winner": str`：`"blue"` 或 `"red"`
    - `"win_reason": str`：获胜原因，如 `"assassination_success"`

---

## 对局中的私有库

对局中，一些私人的“小心思”可以放在 **私有库（Private Library）** 中，增加效率。

- **写入私有库**：\

  - 可以通过下面代码将任意字符串写入私有库中。

  ```python
  write_into_private("1号玩家动机不纯。")
  write_into_private("3号玩家动机不纯。")
  ```

  - `write_into_private` 函数被执行之后，服务器会将您所输入的字符串贴上时间戳之后存储到私有库中。

- **读取私有库**：

  - 可以通过下面代码读取私有库的所有内容。

  ```python
  private_data = read_private_lib()  # 返回一个字典列表，每个字典表示一条记录。
  # 返回示例：
  # [
  #     {
  #       "timestamp": 1745396437.1877804,
  #       "content": "1号玩家动机不纯。"
  #     },
  #     {
  #       "timestamp": 1745396438.1877804,
  #       "content": "3号玩家动机不纯。"
  #     },
  # ]
  ```

---

## 大语言模型API

**注意：我们对大语言模型做出了 token 调用限制，以防止程序对大语言模型的过度依赖。**

**具体限制策略：**

1. **一次输入/输出限制**

  - 输入提示（`prompt`）长度最多 **500 tokens** 

  - llm输出响应自动截断至 **500 tokens** 

2. **总输入/输出限制**

  - $输入长度 \times \frac{1}{4} + 输出长度 \times \frac{3}{4}$ 不能超过 **3000**

  - 如果超出 3000不会报错，但会给予一定的 **ELO 分数惩罚**