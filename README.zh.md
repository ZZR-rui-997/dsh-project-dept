# dsh-project-dept

给 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 用的「验收优先」工作流 skill：把一次复杂工作当成**一个可验收的板块**来做——开工前过闸门，验收由没动手的人独立做，干完不许自己标完成。

<sub>English: [README.md](README.md)</sub>

## 为什么要有它

Agent 会调度，但**不会判断对不对**。「我拆成四个 agent，都跑完了」完全不能说明交付物经不经得起别人挑刺。这个 skill 补的是缺掉的那一半：一套把「开工 → 拆解 → 交付 → 验收 → 归档」写明白的规程，外加一个能**拦下不该开工的活**的脚本。

## 装了什么

- **一个 `project-dept` skill**：用户说「按项目部开工 / 开个板块 / 组团队做这块 / 检查要独立」时加载。
- **一个 `loop-ops` skill**：对一份已成形的交付物跑有限轮「审稿 → 修 → 复审」循环。每轮换全新审稿人（防谄媚）、状态落盘可续跑、编辑白名单防越改越偏、轮次硬上限（默认 2 轮，最多 3 轮）。它负责把硬伤修完，`project-dept` 的三层验收负责判定能不能交。
- **开工闸门** `scripts/dept_gate.py`：退出码 `0` 通过、`1` 禁止开工、`2` 必须先由负责人逐条处置遗留债务（做掉 / 写明理由与复查日期后豁免 / 降级范围）才开工、`3` 表示闸门根本没跑，**不许当通过**。
- **三层验收**：自检 → **由局外人独立盲审** → 终审；盲审方不得先看作者的推理过程。
- **基准自审**：当「已知正确」的参照物本身可能过期（旧报告、上一轮审计结论、上一版文件），先审基准，再拿它当据点。
- **完整闭环 + 交付登记簿**：让「完成」是一次被记录的决定，而不是一种感觉。

## 安装

### 作为 bundle（推荐）

skill 由插件自己通过 `ctx.skills.register()` 注册，装包即生效，不会往你的配置目录里塞副本。安装走 profile 的插件管理器（**Plugins → Add plugin**，指向包目录或已发布的包），或在市场收录后从 **Plugins → Discover** 里安装。

### 作为普通 skill

不想装 bundle 的话，把 skill 目录直接放进被扫描的根目录：

```bash
# 只给某个项目
cp -r skills/project-dept skills/loop-ops <你的项目>/.dsh/skills/
# 或者给所有项目
cp -r skills/project-dept skills/loop-ops ~/.dsh/skills/
```

两条路暴露的是同样两个技能，内容完全一致；bundle 只是省掉手工复制，并随包升级。`loop-ops` 把 `project-dept` 声明为前置：循环负责把硬伤修完，`project-dept` 的三层验收负责判定能不能交。

## 怎么用

1. 项目里放一份 `dept.config.json`（模板与脚手架见 `references/project-scaffold.md`），再加一个 `AGENTS.md` 指向台账目录（默认 `_team/`）。
2. 开工前跑闸门：

   ```bash
   python scripts/dept_gate.py --root <你的项目目录>
   ```

3. 让 agent 开板块。它会**用一行告诉你它判断出的两个轴值**（交付物类型、严谨级别），你可以低成本纠正；随后只加载这两个轴值命中的片段，不会把所有参考文件一股脑读进去。
4. 按三层验收交付；没有独立复核记录，它不会把板块标成完成。

## 目录里有什么

```
skills/project-dept/
skills/loop-ops/
├── SKILL.md                 # 模型真正读的规程
├── manifest.yaml            # 两个轴、必读清单、按需参考
├── README.md / README_EN.md
├── VERIFICATION.md          # 复核日志：14 个版本，每次为什么被打回
├── references/              # 深参：盲审、基准、反模式…
├── static/core/             # 立场、六步工作流、输出契约
├── static/fragments/        # 按两个轴选中的片段
├── scripts/dept_gate.py     # 可执行闸门
├── scripts/check_doc.py     # 文档一致性检查
├── evals/evals.json         # 路由与行为用例
└── tests/test_helpers.py
```

`tests/bundle.test.js`（`node tests/bundle.test.js`）会验证：加载器能不能解析包内 frontmatter、注册给 skill registry 的定义是否完整、以及**正文里声明要读的每个文件是否真的打进包里了**——这个 skill 自己就把「声明了却读不到」当缺陷，所以包也按同一标准测。

## 如实说明的限制

- **正文是中文写的**。规程本身与语言无关，但英文读者读到的会是中文指令；英文版正文尚未提供，英文 README 只是摘要，不是那个 skill。
- **`find_config` 从当前工作目录向上找** `dept.config.json`，所以 shell 必须从项目目录里启动，闸门才找得到配置。
- **闸门需要 Python 3** 在 `PATH` 上（或者显式给解释器路径）。
- **没有界面**：这是一个工作流 skill + 两个脚本，除了插件卡片之外没有可看的东西。
- **它不替代专业 skill**：它管「怎么组织与怎么验收」，某个专业的具体参数与写法属于那个专业自己的 skill。

## 这个包的自我验证

`VERIFICATION.md` 记录了这套规程是怎么被打磨出来的：每一版都是「独立复核判不通过 → 逐条修复」，条目里写的是**具体反例**（跨章悬空引用按 `(章号, 编号)` 二元组比较才修掉的那个假 PASS、混键排序导致的崩溃……）。这份记录才是它值得信任的理由，而不是「听起来很严谨」的措辞。

## 许可

MIT，见 [LICENSE](LICENSE)。