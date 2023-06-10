import click


@click.group()
def portlink(**kwargs):
    pass


@portlink.command()
@click.argument("path")
def start(path: str, **kwargs):
    from framework.port_connect import connect

    connect(path)


if __name__ == "__main__":
    portlink()
