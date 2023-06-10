import click


@click.group()
def cli(**kwargs):
    pass


@cli.command()
@click.argument("path")
def start(path: str, **kwargs):
    from ocean.port_ocean import connect

    connect(path)


if __name__ == "__main__":
    cli()
