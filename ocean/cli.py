import click


@click.group()
def cli_start(**kwargs) -> None:
    pass


@cli_start.command()
@click.argument("path")
def sail(path: str, **kwargs) -> None:
    from ocean.port_ocean import run

    run(path)


if __name__ == "__main__":
    cli_start()
