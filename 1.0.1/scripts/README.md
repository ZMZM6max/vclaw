# Scripts

## run_layer_health.py

层连通性诊断器，按阶段跑测试并产出报告。

```bash
python scripts/run_layer_health.py                # 全跑
python scripts/run_layer_health.py --skip e2e     # 跳过 E2E
python scripts/run_layer_health.py --from stage2  # 从阶段 2 开始
python scripts/run_layer_health.py --json-only    # 只输出 JSON
```

## preflight_check.py

前置环境检查。

```bash
python scripts/preflight_check.py
```
