install:
	$(MAKE) -f ../_infra/Makefile install
	. .venv/bin/activate && pip install -e ../../

%:
	$(MAKE) -f ../_infra/Makefile $@
