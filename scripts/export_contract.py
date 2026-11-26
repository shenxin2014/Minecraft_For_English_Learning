"""从实际路由导出 OpenAPI，避免手写契约与实现漂移。"""

import yaml

from app.main import PROJECT_ROOT, app


def main() -> None:
    """把当前接口模型导出为 UTF-8 YAML。"""
    destination = PROJECT_ROOT / "contracts" / "openapi.yaml"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(
        yaml.safe_dump(app.openapi(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(destination)


if __name__ == "__main__":
    main()
