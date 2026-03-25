# Follow ScoutX 打包导出

如果你要把当前仓库里的：

- [skills/follow_scoutx](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx)

拆成一个单独 skill 仓库，可以直接使用：

- [export_follow_scoutx_skill.sh](/Users/yangchao/codebuddy/ScoutX/scripts/export_follow_scoutx_skill.sh)

## 默认导出

```bash
bash scripts/export_follow_scoutx_skill.sh
```

默认会生成：

```text
dist/follow_scoutx-skill/
```

其中包含：

- `SKILL.md`
- `README.md`
- `service.json`
- `scripts/follow_scoutx.py`
- `prompts/*.md`

其中导出的 `README.md` 来自：

- [repo_README.md](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx/repo_README.md)

## 覆盖已有导出目录

```bash
OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

## 导出到自定义目录

```bash
DEST_DIR=/tmp/follow_scoutx-skill OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

## 典型后续步骤

1. 运行导出脚本
2. 进入导出目录
3. 新建一个独立 Git 仓库
4. 把 `service.json` 改成你真实的中心托管地址
5. 再推到单独的 GitHub 仓库
