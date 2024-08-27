from port_ocean.utils import http_async_client

from random import randint

from typing import List
from .types import PunCategory, Pun, Funny

API_URL = "https://icanhazdadjoke.com/search"
USER_AGENT = "Ocean Framework Dummy Integration (https://github.com/port-labs/ocean)"


async def get_puns(category: PunCategory) -> List[Pun]:
    amount = randint(2, 19)
    url = f"{API_URL}?term={category.name}&limit={amount}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    raw_jokes = response.json()

    jokes = [
        Pun(
            **{
                "id": joke["id"],
                "name": f'{"".join(joke["joke"][:7]).strip()}...',
                "funny": Funny.YAAS if randint(0, 2) % 2 == 0 else Funny.NOPE,
                "score": randint(1, 100),
                "category": category,
                "text": joke["joke"],
            }
        )
        for joke in raw_jokes["results"]
    ]

    return jokes
