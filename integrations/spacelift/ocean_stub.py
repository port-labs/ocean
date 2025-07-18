class OceanIntegration:
    """
    Drop-in replacement for missing OceanIntegration class in SDK.
    Ensures `ocean run --module main:app` works correctly.
    """
    def __init__(self):
        pass

    async def fetch_all(self):
        """
        This must be implemented in your subclass.
        """
        raise NotImplementedError("You must override fetch_all in your integration.")
