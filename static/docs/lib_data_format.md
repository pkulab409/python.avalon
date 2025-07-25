**JSON**格式是公有库/私有库的数据存储格式。具体如下：

## 公有库


### 1. 游戏开始

- **游戏开始时**， `referee` 将创建该局游戏的公有库 JSON 文档，路径为 `./data/{GAME_ID}/public_game_{GAME_ID}.json` 。例如一局游戏的编号是 12345，那么路径为 `./data/12345/public_game_12345.json` 。

  - 经过初始化后，这个 JSON 文档初始的内容是一个“空列表”：

  ```json
  []
  ```

- **分配角色时**， `referee` 将对局的初始信息加入到公有库 JSON 文档中。**分配角色的结果是不能被放到公有库的，否则用户对游戏一切的一切都了如指掌。**

  - 例如，这局游戏的 game_id 是 12345，七人局，那么分配角色后，规定的格式使得这个 JSON 文档将会变成这样：

  ```json
  [
    {
      "type": "game_start",
      "game_id": "12345",
      "player_count": 7,
      "timestamp": "2025-07-23 02:00:04.796",
      "round": 0
    }
  ]
  ```

### 2. 夜晚阶段

- 夜晚阶段非常私密，没有实质性的信息会被放到公有库中来。只有在夜晚阶段结束后，公有库会加上一句冷冰冰的记录如下：

```json
[
  {
    "type": "game_start",
    "game_id": 12345,
    "player_count": 7,
    "map_size": 9
  },
  {  // --- 以下信息将被追加 ---
    "type": "night_phase_complete",
    "timestamp": "2025-07-23 02:00:04.810",
    "round": 0
  }
]
```

### 3. 【任务】轮次开始

- 【任务】轮次的开始，是指定该轮队长和该轮任务人数。这些信息会被放到公有库中：

```json
[
  {
    "type": "game_start",
    "game_id": 12345,
    "player_count": 7,
    "map_size": 9
  },
  {
    "type": "night_phase_complete",
    "timestamp": "2025-07-23 02:00:04.810",
    "round": 0
  },
  {  // --- 以下信息将被追加 ---
    "type": "mission_start",
    "round": 1,\游戏进入第一轮
    "leader": 5,\队长是5号玩家
    "member_count": 2,\这一轮要选2人组队
    "timestamp": "2025-07-23 02:00:04.816"
  }
]
```

### 4. 队长选人

- 假如第1轮第一次队长选人的队长是5号，并且选择了5,1号玩家作为次轮任务的执行者，那么公有库将会加入一条格式如下的记录：

```json
{
  "type": "team_proposed",
    "round": 1,
    "vote_round": 1,
    "leader": 5,
    "members": [
      5,
      1
    ],
    "timestamp": "2025-07-23 02:01:16.159"
}
```

### 5. 发言

- 例如第二轮，当前队长是3号，执行完所有玩家的 `say()` 函数后，公有库添加如下记录：

```json
{
  "type": "global_speech",
    "round": 1,
    "speeches": [
      [
        5,
        "这轮信息有点混乱，我还在观察。"
      ],
      [
        6,
        "这轮信息有些混乱，我还在观察。"
      ],
      [
        7,
        "这轮信息混乱，我还在观察。"
      ],
      [
        1,
        "这轮信息很混乱，我还在观察。"
      ],
      [
        2,
        "这轮信息特别混乱，我还在观察。"
      ],
      [
        3,
        "这轮信息混乱得快炸了，我还在观察。"
      ],
      [
        4,
        "这轮信息毁灭了地球，我还在观察。"
      ]
    ],
    "timestamp": "2025-07-23 02:04:23.510"
  },
}
```


### 6. 第一轮公投表决（是否认同队伍执行任务）

- 假如第1轮中的一次公投表决被通过（除了6号玩家外均投通过票），那么公有库将会加入一条格式如下的记录：

```json
{
  "type": "public_vote",
  "round": 1,
  "votes": {
    "1": true,
    "2": true,
    "3": true,
    "4": true,
    "5": true,
    "6": false,
    "7": true
  },
  "approve_count": 6,
  "result": "approved",
  "timestamp": "2025-07-23 02:07:19.594"
}
```

- 假如第1轮中的第一次公投表决**未**被通过（1-2号玩家投赞成，3-7号投出反对），那么公有库将会加入一条格式如下的记录和一条轮换队长记录：

```json
{
  "type": "public_vote",
  "round": 1,
  "votes": {
    "1": true,
    "2": true,
    "3": false,
    "4": false,
    "5": false,
    "6": false,
    "7": false
  },
  "approve_count": 2,
  "result": "approved",
  "timestamp": "2025-07-23 02:07:19.594"
}
```

```json
{
  "type": "team_rejected",
  "round": 1,
  "vote_round": 1,
  "approve_count": 2,
  "next_leader": 4,
}
```

- 如第1轮中，公投遭到连续5轮否决，即将触发强制组队执行任务，公有库会在任务执行前添加一条记录：

```json
{"type": "consecutive_rejections", "round": 1}
```

### 7. 第二轮投票表决（任务是否成功）

- 假如第4轮中的投票表决**未**被通过，有3人投出失败票，那么公有库将会加入一条格式如下的记录和一条回合结果的记录：

```json
{  // 任务执行记录
  "type": "mission_execution",
  "round": 4,
  "fail_votes": 3,
  "success": false
}
```

```json
{  // 回合结果记录
  "type": "mission_result",
  "round": 4,
  "result": "fail",  // 成功："success"
  "blue_wins": 2,
  "red_wins": 2
}
```

### 8. 蓝方即将胜利、刺杀、蓝/红方胜利、游戏结束

- 假如第三轮结束后，蓝方即将胜利（红方一轮也没赢），刺客玩家（5号）选择刺杀对象为1号且刺杀成功，那么公有库将会加入一条刺杀记录和一条游戏结束记录（**此时公布玩家身份**）：

```json
{  // 刺杀记录
  "type": "assassination",
  "assassin": 5,
  "target": 1,
  "target_role": "Merlin",
  "success": true
}
```

```json
{  // 游戏结束记录
  "type": "game_end",
  "result": {
    "blue_wins": 3,
    "red_wins": 0,
    "rounds_played": 3,
    "roles": {
      "1": "Merlin",
      // ...
    },
    "public_log_file": "...",  // 文件位置
    "winner": "red",
    "win_reason": "assassination_success"
  }
}
```

- 假如第三轮结束后，蓝方即将胜利（红方一轮也没赢），刺客玩家（5号）选择刺杀对象为1号但刺杀失败，那么公有库将会加入一条刺杀记录和一条游戏结束记录（**此时公布玩家身份**）：

```json
{  // 刺杀记录
  "type": "assassination",
  "assassin": 5,
  "target": 1,
  "target_role": "Oberon",
  "success": false
}
```

```json
{  // 游戏结束记录
  "type": "game_end",
  "result": {
    "blue_wins": 3,
    "red_wins": 0,
    "rounds_played": 3,
    "roles": {
      "1": "Merlin",
      // ...
    },
    "public_log_file": "...",  // 文件位置
    "winner": "blue",
    "win_reason": "missions_complete_and_assassination_failed"
  }
}
```

- 假如第三轮结束后，红方胜利（蓝方一轮也没赢），那么公有库将会加入一条游戏结束记录（**此时公布玩家身份**）：

```json
{
  "type": "game_end",
  "result": {
    "blue_wins": 0,
    "red_wins": 3,
    "rounds_played": 3,
    "roles": {
      "1": "Merlin",
      // ...
    },
    "public_log_file": "...",  // 文件位置
    "winner": "red",
    "win_reason": "missions_failed"
  }
}
```

### \*9. 程序意外终止

- 遇到程序意外终止，**公有库的记录随即终止**，服务器程序抛出 Critical Error。

---

## 私有库

为了方便玩家在调试代码时提供自定义的反馈，私有库允许玩家自行写入任何信息，并在游戏结束后允许查看个人的私有库内容。

### 私有库相关函数

以下函数可以在Player代码中被调用：

#### 1. `read_public_lib() -> list[dict]`
**功能**：读取所有玩家可见的公共对局记录库，包含全局对战信息。

- **返回值**：
  - `list[dict]`: 返回一个字典列表，每个字典表示一条对局记录。  

- **调用示例**：
  ```python
  history = read_public_lib()
  ```

#### 2. `read_private_lib() -> list[dict]`
**功能**：读取仅对当前玩家可见的私有存储数据。

- **返回值**：
  - `list[dict]`: 返回一个字典列表，每个字典表示一条记录。 字典中，键 `"content"` 对应的值是先前写入的文本内容。

- **调用示例**：
  ```python
  private_data = read_private_lib()
  ```

#### 3. `write_into_private(content: str) -> None`
**功能**：向当前玩家的私有存储中追加写入内容。

- **参数**：
  - `content` (str): 需要保存的文本内容。

- **调用示例**：
  ```python
  write_into_private('suspects: 3,5')
  ```
### 私有库内容

- **私有库初始化**：初始化的私有库 JSON 如下：

```json
{
  "logs": [],
  "llm_history": [{"role": "system", "content": "你是一个专家。"}],
  "llm_call_counts": [0, 0, 0, 0, 0, 0],
}
```

- **给予用户的发挥空间**：用户可以将任意字符串添加到私有库 JSON 的 `logs` 字段下。

  - 例如，用户使用了如下代码向私有库中存储信息：

  ```python
  from game.avalon_game_helper import write_into_private

  write_into_private("1号玩家动机不纯。")
  write_into_private("2号玩家这轮的说话只有我能听到。他说他是梅林，坏人是5,6,7号。")
  ```

  - 此时，服务器将**在这些字符串前面贴上时间戳**，并让私有库追加这些记录：

  ```json
  {
    "logs": [
      {
        "timestamp": 1745396437.1877804,
        "content": "1号玩家动机不纯。"
      }
    ]
  }
  ```

- **LLM 聊天记录保留**：用户和LLM的聊天记录在私有库 JSON 的 `llm_history` 字段下。例如：

```json
{
  "logs": [
    {
      "timestamp": 1745396437.1877804,
      "content": "1号玩家动机不纯。"
    }
  ],
  "llm_history": [
    {
      "role": "system",
      "content": "\n你是一个专业助理。\n"
    },
    {
      "role": "user",
      "content": "\n        【任务背景】\n        你是阿瓦隆游戏中的4号玩家，角色是Oberon。\n        现在是第0轮任务，队长7号选择了队员[7, 1]。\n        你需要决定是否同意这个队伍执行任务。\n        \n        【你的身份信息】\n        你属于邪恶方。\n        \n【历史队伍组成】\n第1轮: 队长7号，队员[7, 1]\n\n【玩家评估】\n1号玩家: 中立\n2号玩家: 中立\n3号玩家: 中立\n5号玩家: 中立\n6号玩家: 中立\n7号玩家: 可信\n\n            【决策要求】\n            作为邪恶方，你需要评估这个队伍是否有利于你们。\n            如果队伍中有你或其他邪恶方成员，你可能希望同意。\n            如果连续4次投票都被否决，第5次会强制通过，需要考虑战略价值。\n            当前连续否决次数: 0\n            请直接回答\"同意\"或\"反对\"。\n            "
    },
    {
      "role": "assistant",
      "content": "反对"
    }
  ],
  "llm_call_counts": [0, 1, 1, 1, 0, 0]
}
```

这样，用户在下一次调用LLM时，先前的聊天记录 (`context`) 会被自动导入。

- **LLM 调用次数记录**：用户在第 `round` 轮调用一次 LLM， `llm_call_counts[round] += 1`。
