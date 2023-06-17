import cProfile
import pstats


class Profiler:
    def __enter__(self):
        self.pr = cProfile.Profile()
        self.pr.enable()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pr.disable()
        ps = pstats.Stats(self.pr).sort_stats("cumulative")
        ps.print_stats()
