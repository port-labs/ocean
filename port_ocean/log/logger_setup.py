import atexit
import logging
import re
import sys
from logging import LogRecord
from logging.handlers import QueueHandler, QueueListener
from queue import Queue

import loguru
from loguru import logger

from port_ocean.config.settings import LogLevelType
from port_ocean.log.handlers import HTTPMemoryHandler

# https://github.com/h33tlit/secret-regex-list
p = {
    "Cloudinary": r"cloudinary:\/\/.*",
    "Firebase URL": r".*firebaseio\.com",
    "Slack Token": r"(xox[p|b|o|a]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32})",
    "RSA private key": r"-----BEGIN RSA PRIVATE KEY-----",
    "SSH (DSA) private key": r"-----BEGIN DSA PRIVATE KEY-----",
    "SSH (EC) private key": r"-----BEGIN EC PRIVATE KEY-----",
    "PGP private key block": r"-----BEGIN PGP PRIVATE KEY BLOCK-----",
    "Amazon AWS Access Key ID": r"AKIA[0-9A-Z]{16}",
    "Amazon MWS Auth Token": r"amzn\\.mws\\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "AWS API Key": r"AKIA[0-9A-Z]{16}",
    "Facebook Access Token": r"EAACEdEose0cBA[0-9A-Za-z]+",
    "Facebook OAuth": r"[f|F][a|A][c|C][e|E][b|B][o|O][o|O][k|K].*['|\"][0-9a-f]{32}['|\"]",
    "GitHub": r"[g|G][i|I][t|T][h|H][u|U][b|B].*['|\"][0-9a-zA-Z]{35,40}['|\"]",
    "Generic API Key": r"[a|A][p|P][i|I][_]?[k|K][e|E][y|Y].*['|\"][0-9a-zA-Z]{32,45}['|\"]",
    "Generic Secret": r"[s|S][e|E][c|C][r|R][e|E][t|T].*['|\"][0-9a-zA-Z]{32,45}['|\"]",
    "Google API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google Cloud Platform API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google Cloud Platform OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\\.apps\\.googleusercontent\\.com",
    "Google Drive API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google Drive OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\\.apps\\.googleusercontent\\.com",
    "Google (GCP) Service-account": r'"type": "service_account"',
    "Google Gmail API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google Gmail OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\\.apps\\.googleusercontent\\.com",
    "Google OAuth Access Token": r"ya29\\.[0-9A-Za-z\\-_]+",
    "Google YouTube API Key": r"AIza[0-9A-Za-z\\-_]{35}",
    "Google YouTube OAuth": r"[0-9]+-[0-9A-Za-z_]{32}\\.apps\\.googleusercontent\\.com",
    "Heroku API Key": r"[h|H][e|E][r|R][o|O][k|K][u|U].*[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}",
    "MailChimp API Key": r"[0-9a-f]{32}-us[0-9]{1,2}",
    "Mailgun API Key": r"key-[0-9a-zA-Z]{32}",
    "Password in URL": r"[a-zA-Z]{3,10}:\/\/[^\/\\s:@]{3,20}:[^\/\\s:@]{3,20}@.{1,100}[\"'\\s]",
    "PayPal Braintree Access Token": r"access_token\\$production\\$[0-9a-z]{16}\\$[0-9a-f]{32}",
    "Picatic API Key": r"sk_live_[0-9a-z]{32}",
    "Slack Webhook": r"https:\/\/hooks.slack.com\/services\/T[a-zA-Z0-9_]{8}\/B[a-zA-Z0-9_]{8}\/[a-zA-Z0-9_]{24}",
    "Stripe API Key": r"sk_live_[0-9a-zA-Z]{24}",
    "Stripe Restricted API Key": r"rk_live_[0-9a-zA-Z]{24}",
    "Square Access Token": r"sq0atp-[0-9A-Za-z\\-_]{22}",
    "Square OAuth Secret": r"sq0csp-[0-9A-Za-z\\-_]{43}",
    "Twilio API Key": r"SK[0-9a-fA-F]{32}",
    "Twitter Access Token": r"[t|T][w|W][i|I][t|T][t|T][e|E][r|R].*[1-9][0-9]+-[0-9a-zA-Z]{40}",
    "Twitter OAuth": r"[t|T][w|W][i|I][t|T][t|T][e|E][r|R].*['|\"][0-9a-zA-Z]{35,44}['|\"]",
    "JWT": r"[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*",
    "Connection String": r"[a-zA-Z]+:\/\/[^/\s]+:[^/\s]+@[^/\s]+\/[^/\s]+",
}


def f(record: "loguru.Record") -> bool:
    sensitive_data_pattern = [re.compile(pattenrn) for pattenrn in p.values()]
    for pattern in sensitive_data_pattern:
        record["message"] = pattern.sub("[REDACTED]", record["message"])

    return True


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        # Define a regular expression to match sensitive data
        sensitive_data_pattern = [re.compile(pattenrn) for pattenrn in p.values()]
        for pattern in sensitive_data_pattern:
            record.msg = pattern.sub("[REDACTED]", record.msg)

        return True


def setup_logger(level: LogLevelType) -> None:
    logger_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )
    if level == "DEBUG":
        logger_format += " | {extra}"

    logger.remove()
    logger.add(
        sys.stdout,
        level=level.upper(),
        format=logger_format,
        enqueue=True,  # process logs in background
        diagnose=False,  # hide variable values in log backtrace
        filter=f,
    )
    logger.configure(patcher=exception_deserializer)

    queue: Queue[LogRecord] = Queue()

    handler = QueueHandler(queue)

    logger.add(
        handler,
        level=level.upper(),
        format="{message}",
        diagnose=False,  # hide variable values in log backtrace
        enqueue=True,  # process logs in background
    )

    queue_listener = QueueListener(
        queue, HTTPMemoryHandler(50, flush_interval=60, flush_size=1024)
    )
    queue_listener.start()
    atexit.register(queue_listener.stop)


def exception_deserializer(record: "loguru.Record") -> None:
    """
    Workaround for when trying to log exception objects with loguru.
    loguru doesn't able to deserialize `Exception` subclasses.
    https://github.com/Delgan/loguru/issues/504#issuecomment-917365972
    """
    exception: loguru.RecordException | None = record["exception"]
    if exception is not None:
        fixed = Exception(str(exception.value))
        record["exception"] = exception._replace(value=fixed)
