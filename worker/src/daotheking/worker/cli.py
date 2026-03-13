from __future__ import annotations
import logging
from .config import WorkerSettings
from .service import WorkerService, build_worker_context


def main() -> int:
    """

    :return:
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = WorkerSettings.from_env()
    context = build_worker_context(settings)
    service = WorkerService(context)
    return service.run()


if __name__ == "__main__":
    raise SystemExit(main())
