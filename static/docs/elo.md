## 什么是 ELO 评分系统？

ELO 评分系统是一种用于衡量玩家或团队相对技能水平的数学方法，最初由匈牙利裔美国物理学家 Arpad Elo 设计，主要用于国际象棋等竞技游戏的排名。如今，它广泛应用于电子竞技（如《英雄联盟》《星际争霸》）、体育赛事（如足球、篮球）以及其他竞争性场景（如在线匹配系统）。

<div style="height: 20px;"></div>

### 核心原理

ELO 系统的核心思想基于以下几个重要概念：

<div style="height: 15px;"></div>

**🎯 评分反映实力**：每个玩家有一个初始分数（如 1000 或 1500），分数越高代表实力越强。

**⚖️ 胜负影响评分**：比赛后，胜者从败者处获得分数，分数变动幅度取决于双方赛前的评分差距。

**📈 高分玩家赢低分玩家**：分数变动较小（符合预期）。

**🎉 低分玩家赢高分玩家**：分数变动较大（爆冷门）。

**🔮 概率预测**：通过双方评分差，可以预测比赛胜负的概率。

<div style="height: 30px;"></div>

---

## 一、基础规则

### 1. 游戏胜负

- **蓝方（4人）**：需要完成3次任务成功
- **红方（3人）**：需要破坏3次任务或刺杀梅林
- **最终胜负**：只有一方胜利（无平局，除非游戏意外中止触发惩罚）

<div style="height: 20px;"></div>

### 2. ELO天梯

- 按照 ELO 机制，《图灵阿瓦隆》游戏平台中显示的 `分数` 即某位玩家的 **ELO 分数**
- 当用户注册之后，其**自动被赋予 1200 分的初始 ELO 积分**，并开始参与 ELO 天梯排名
- 参与对战游戏，平台主要根据游戏胜负增加/减少您的 ELO 分数（详情见后文）
- **目标**：踊跃参与对战，积极优化代码，努力成为大师，努力成为金字塔的塔尖！

<div style="height: 30px;"></div>

---

## 二、ELO分数计算机制

### 1. 基础公式

所有玩家根据**胜负结果**调整分数：

$$
\Delta ELO = K \times (\text{结果} - \text{预期胜率})
$$

<div style="height: 20px;"></div>

- **结果**：胜利为 $1$ ，失败为 $0$
- **预期胜率**：根据双方队伍平均ELO计算（公式见下文）
- **$K$ 值**：100

<div style="height: 30px;"></div>

### 2. 改进版的ELO评分

我们将使用改进版的ELO评分系统，结合了队伍表现和个体资源贡献。以下是核心公式的解析：

<div style="height: 20px;"></div>

**步骤1：Token标准化计算**

每个玩家的token消耗被加权处理，输出token权重为输入的3倍：

$$
\text{tokens\_standard}_i = \frac{\text{input}_i + 3 \times \text{output}_i}{4} \quad (i=0,1,...,6)
$$

<div style="height: 20px;"></div>

**步骤2：基准Token平均值**

计算所有玩家的标准化token平均值，并设定下限：

$$
\text{tokens\_avg} = \max\left(3000, \frac{1}{7}\sum_{i=0}^{6} \text{tokens\_standard}_i\right)
$$

<div style="height: 20px;"></div>

**步骤3：Token消耗比例**

计算每个玩家的token消耗相对于基准值的比例：

$$
\text{proportion}_i = \frac{\text{tokens\_standard}_i}{\text{tokens\_avg}}
$$

<div style="height: 20px;"></div>

**步骤4：队伍ELO调和平均**

计算队伍ELO的调和平均值（缓和低分玩家的影响）：

$$
\text{team\_avg} = \frac{N}{\sum \min\left(1, \frac{1}{\text{elo\_score}}\right)}
$$

<div style="height: 20px;"></div>

其中 $N$ 为队伍人数， $\text{elo\_score}$ 为玩家ELO

<div style="height: 20px;"></div>

**步骤5：基础期望胜率**

使用标准ELO公式计算两队期望胜率：

$$
E_{\text{red}} = \frac{1}{1 + 10^{(\text{team\_avg}_{\text{blue}} - \text{team\_avg}_{\text{red}})/400}} 
$$

<div style="height: 20px;"></div>

$$
E_{\text{blue}} = \frac{1}{1 + 10^{(\text{team\_avg}_{\text{red}} - \text{team\_avg}_{\text{blue}})/400}}
$$

<div style="height: 20px;"></div>

**步骤6：期望胜率调整规则**

根据token消耗比例动态调整期望值：

$$
E_{\text{adjusted}} = \min\left(1,\ E_{\text{base}} \times \left(0.9 + \frac{\max(\text{proportion}_i - 1,\ 0)}{3}\right)\right)
$$

<div style="height: 20px;"></div>

**步骤7：ELO变化计算**

使用线性响应公式计算ELO变化量：

$$
\Delta = 100 \times (S_{\text{actual}} - E_{\text{adjusted}})
$$

<div style="height: 20px;"></div>

其中 $S_{\text{actual}}=1$ 当队伍胜利，否则 $0$

<div style="height: 20px;"></div>

**步骤8：最终ELO计算**

强制设置ELO下限并更新分数：

$$
\text{new\_elo} = \max(100,\ \text{old\_elo} + \text{round}(\Delta))
$$

<div style="height: 30px;"></div>

**💡 设计理念**：
- 使用调和平均弱化低水平队友的影响
- 通过资源消耗系数动态调整预期胜率，鼓励合理分配计算资源

<div style="height: 30px;"></div>

### 3. 犯规惩罚

若一局中出现某位玩家代码报错或输出信息不合理等犯规行为，**游戏立即结束，进行犯规处理**：

<div style="height: 20px;"></div>

**处理方式**：  

1. **扣除犯规玩家分值如下：**

   - 基础惩罚为30分，加上队伍差距的10%
   - 根据错误类型设置不同倍数:严重错误(1.5倍)，返回值错误(1.2倍)
   - 根据错误方法添加额外惩罚:移动错误(+10分)，队伍选择错误(+15分)，投票错误(+20分)
   - 确保惩罚最低20分，最高100分

2. 本局判定为**平局**，其他玩家ELO不变

<div style="height: 30px;"></div>

---

## 三、计算示例

### 场景描述

- **蓝方**平均ELO 1500，**红方**平均ELO 1550

### 计算步骤

**步骤1：预期胜率**

$$
\text{预期胜率}_{\text{蓝方}} = \frac{1}{1 + 10^{(1550-1500)/400}} \approx 0.45
$$

<div style="height: 30px;"></div>

**步骤2：加/减分**

<div style="height: 10px;"></div>

$$
\Delta ELO = 20 \times (1 - 0.45) = 20 \times 0.55 = +11
$$

<div style="height: 20px;"></div>

四舍五入后，该玩家最终ELO**增加**11分。

*对于失败的玩家， $\Delta ELO < 0$ ，该玩家最终遭到减分。*

<div style="height: 30px;"></div>

---
