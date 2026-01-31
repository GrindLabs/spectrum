class BanError(RuntimeError):
    """Raised when a request is blocked by WAF protection."""


class CaptchaFoundError(RuntimeError):
    """Raised when a CAPTCHA is detected without a strategy."""
