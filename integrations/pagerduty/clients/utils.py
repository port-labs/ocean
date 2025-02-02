from datetime import datetime, timedelta
import httpx
from loguru import logger
import time
from port_ocean.helpers.retry import CustomTokenRefreshABC, IntegrationRetryStrategyABC


def get_date_range_for_last_n_months(n: int) -> tuple[str, str]:
    now = datetime.utcnow()
    start_date = (now - timedelta(days=30 * n)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )  # using ISO 8601 format
    end_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (start_date, end_date)


def get_date_range_for_upcoming_n_months(n: int) -> tuple[str, str]:
    now = datetime.utcnow()
    start_date = now.strftime("%Y-%m-%dT%H:%M:%SZ")  # using ISO 8601 format
    end_date = (now + timedelta(days=30 * n)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (start_date, end_date)

class RetryWithRefreshStrategy(IntegrationRetryStrategyABC, CustomTokenRefreshABC):
    def __init__(self, max_token_retries: int, token_refresh_backoff_interval: int, config_file_path: str | None = None):
        self.max_token_retries = max_token_retries
        self.token_refresh_backoff_interval = token_refresh_backoff_interval
        self.config_file_path = config_file_path

    def check_token_invalidity(response: httpx.Response) -> bool:
        """
        Check if the token in the HTTPX response is invalid or has expired based on PagerDuty's documentation.
        https://developer.pagerduty.com/docs/authentication
        Args:
        response (httpx.Response): The HTTPX response object to check.
        Returns:
        bool: True if the token is invalid, expired, or unauthorized; False otherwise.
        """
        if response.status_code == 401:
            return True
        try:
            json_response = response.json()
            if 'error' in json_response:
                error_details = json_response['error']
                if 'token' in error_details.get('message', '').lower() or \
                'expired' in error_details.get('message', '').lower() or \
                'unauthorized' in error_details.get('message', '').lower():
                    return True
        except ValueError:
            pass

        return False

    def token_refresh_handler(self, response: httpx.Response, max_token_retries: int, token_refresh_backoff_interval: int, config_file_path: str | None = None) -> bool:
        retry_count = response.extensions.get("token_retry_count", 0)

        logger.debug("Start token refresh validation")
        if retry_count >= max_token_retries:
            logger.error("Max token retries exceeded, raising error")
            response.raise_for_status()
            return False

        logger.info(f"Token invalid/expired, refreshing and retrying (attempt {retry_count + 1}/{max_token_retries})")
        # Update token retry count
        response.extensions["token_retry_count"] = retry_count + 1

        # Assuming the refresh process takes some time, we sleep for a bit before retrying
        #TODO: check if the tokens are different, if so, no need to wait. (? wait before refresh or after ?)
        time.sleep(token_refresh_backoff_interval)

        if config_file_path is not None:
            try:
                logger.debug(f"Loading configuration from file: {config_file_path}")
                refresh_success = self.refresh_token_from_file(self, config_file_path)
            except Exception as e:
                logger.error(f"Failed to load configuration from file: {e}")
                return False
        else:
            logger.error("No token refresh method available")
            return False

        if not refresh_success:
            logger.error("Unable to refresh token")
            return False

        return True

    async def should_retry_async_handler(self, response: httpx.Response) -> bool:
        logger.debug("PagerDutyClient - validate token invalidity")
        if self.config_file_path is None:
            return self.base_retry_async_handler(response, self.http_client.transport._retry_status_codes)
        else:
            is_invalid_token = self.check_token_invalidity(response)

            if not is_invalid_token:
                logger.debug("Unable to identify token as invalid")
                return self.base_retry_async_handler(response, self.http_client.transport._retry_status_codes)

            try:
                logger.debug("Attempting to refresh invalid token")
                return self.token_refresh_handler(self, response, self.max_token_retries, self.token_refresh_backoff_interval, self.config_file_path)
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                pass
        return False
