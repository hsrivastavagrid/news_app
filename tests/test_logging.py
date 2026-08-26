import logging
from app.logging_config import setup_logging, new_request_id, request_id_ctx

def test_setup_logging_and_request_id():
    setup_logging()
    rid = new_request_id()
    assert request_id_ctx.get() == rid
    logger = logging.getLogger("newspulse")
    logger.info("test log line")
    assert logger.isEnabledFor(logging.INFO)
