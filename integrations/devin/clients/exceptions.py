class DevinPaginationError(Exception):
    # Raising after a partial list makes Ocean skip delete for unfetched pages.
    pass
