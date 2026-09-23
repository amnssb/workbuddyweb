# 更新日志

## v1.0.65（未发布）

- 重写更新逻辑为单仓库模型：管理端与上游统一跟随本仓库 `amnssb/workbuddyweb`。
- 新增 `deploy/update.py` 更新执行器，补齐此前缺失的「一键更新」脚本。
- 新增 Dockerfile 内 docker CLI + compose v2 插件，容器形态挂 `docker.sock` 后可一键更新上游。
- 新增发布包签名信任锚（`deploy/release-signing-key.pub`、`deploy/verify-release.sh`）。

## v1.0.64

- 初始版本。
