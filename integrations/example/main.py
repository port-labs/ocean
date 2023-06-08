from framework.context.integration import portlink


@portlink.on_resync()
async def resync():
    return []


@portlink.on_start()
async def start():
    print('start')


@portlink.router.post('/test')
async def a():
    await portlink.register_entities([dict(a=1)])
    return dict(a=1)
