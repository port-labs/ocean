import asyncio
import threading
from asyncio import ensure_future
from functools import wraps
from traceback import format_exception
from typing import Any, Callable, Coroutine

from loguru import logger
from starlette.concurrency import run_in_threadpool

NoArgsNoReturnFuncT = Callable[[], None]
NoArgsNoReturnAsyncFuncT = Callable[[], Coroutine[Any, Any, None]]
NoArgsNoReturnDecorator = Callable[
    [NoArgsNoReturnFuncT | NoArgsNoReturnAsyncFuncT], NoArgsNoReturnAsyncFuncT
]


def repeat_every(
    seconds: float,
    wait_first: bool = False,
    raise_exceptions: bool = False,
    max_repetitions: int | None = None,
) -> NoArgsNoReturnDecorator:
    """
    This function returns a decorator that modifies a function so it is periodically re-executed after its first call.

    The function it decorates should accept no arguments and return nothing. If necessary, this can be accomplished
    by using `functools.partial` or otherwise wrapping the target function prior to decoration.

    Parameters
    ----------
    seconds: float
        The number of seconds to wait between repeated calls
    wait_first: bool (default False)
        If True, the function will wait for a single period before the first call
    raise_exceptions: bool (default False)
        If True, errors raised by the decorated function will be raised to the event loop's exception handler.
        Note that if an error is raised, the repeated execution will stop.
        Otherwise, exceptions are just logged and the execution continues to repeat.
        See https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.set_exception_handler for more info.
    max_repetitions: Optional[int] (default None)
        The maximum number of times to call the repeated function. If `None`, the function is repeated forever.
    """

    def decorator(
        func: NoArgsNoReturnAsyncFuncT | NoArgsNoReturnFuncT,
    ) -> NoArgsNoReturnAsyncFuncT:
        """
        Converts the decorated function into a repeated, periodically-called version of itself.
        """
        is_coroutine = asyncio.iscoroutinefunction(func)

        @wraps(func)
        async def wrapped() -> None:
            repetitions = 0

            async def loop() -> None:
                nonlocal repetitions

                if wait_first:
                    await asyncio.sleep(seconds)
                while max_repetitions is None or repetitions < max_repetitions:
                    # count the repetition even if an exception is raised
                    repetitions += 1
                    try:
                        if is_coroutine:
                            await func()  # type: ignore
                        else:
                            await run_in_threadpool(func)
                    except Exception as exc:
                        formatted_exception = "".join(
                            format_exception(type(exc), exc, exc.__traceback__)
                        )
                        logger.error(formatted_exception)
                        if raise_exceptions:
                            raise exc
                    await asyncio.sleep(seconds)

            ensure_future(loop())

        return wrapped

    return decorator


async def schedule_repeated_task(
    function: Callable[..., Coroutine[Any, Any, None]],
    interval: int,
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Schedule a repeated task that will run the given function every `interval` seconds
    """
    loop = asyncio.get_event_loop()
    repeated_function = repeat_every(
        seconds=interval,
        wait_first=True,
    )(
        lambda: threading.Thread(
            target=lambda: asyncio.run_coroutine_threadsafe(
                function(*args, **kwargs), loop
            )
        ).start()
    )
    await repeated_function()
