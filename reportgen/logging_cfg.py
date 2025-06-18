from logging.config import dictConfig


def setup_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "rich": {
                    "format": "[%(levelname)s] %(asctime)s — %(name)s: %(message)s"
                }
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": "rich"}
            },
            "root": {"level": level, "handlers": ["console"]},
        }
    )
