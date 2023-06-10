import click


@click.group()
def cli_start(**kwargs):
    pass


@cli_start.command()
@click.argument("path")
def sail(path: str, **kwargs):
    from ocean.port_ocean import connect

    connect(path)


if __name__ == "__main__":
    cli_start()
