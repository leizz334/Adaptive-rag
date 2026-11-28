# 贡献指南

## 依赖管理

依赖的唯一来源是 `pyproject.toml`：运行时依赖写在 `[project.dependencies]`，可选组写在 `[project.optional-dependencies]`（`dev`、`rerank`、`docs`）。仓库不再维护单独的 `requirements.txt`，避免两份版本清单漂移。

`uv.lock` 是提交进仓库的锁定版本清单，用于复现完整依赖树。CI 会跑 `uv lock --check`，一旦它与 `pyproject.toml` 不同步就会失败。

```bash
uv sync --extra dev          # 按 uv.lock 精确复现开发环境（推荐）
uv lock --check              # 改过 pyproject 后校验锁文件是否同步

pip install -e ".[dev]"      # 开发（含 pytest、ruff、mypy）
pip install -e ".[rerank]"   # 本地 bge 召回 + Cross-Encoder 精排
pip install -e ".[docs]"     # Unstructured 解析 PDF/Office/HTML/图片
```

## 代码规范

项目使用 Python 3.11+。修改后运行回归测试并检查新增代码的格式、导入和类型。

```bash
ruff format .
ruff check .
mypy
python -m compileall -q app eval
pytest -q
```

评测脚本与历史数据的复算命令见 [评测说明](eval/README.md)。

提交前请确保不提交 `.env`、密钥、数据库文件和评测生成物。业务逻辑应放在分层目录中，通过 schema 传递数据，避免在路由层直接访问基础设施。
