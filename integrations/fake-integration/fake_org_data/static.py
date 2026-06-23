from .types import Address, FakeDepartment, FakeLead, FakeOffice, FakeTeam, Geo


DEPARTMENTS = ["hr", "marketing", "finance", "support", "morpazia"]

FAKE_DEPARTMENTS = [FakeDepartment(id=x, name=x) for x in DEPARTMENTS]

FAKE_OFFICES = [
    FakeOffice(
        id="office-hq",
        name="HQ",
        address=Address(
            city="Tel Aviv",
            country="Israel",
            lines=["Rothschild 1", "Floor 12"],
            geo=Geo(lat=32.0644, lng=34.7747),
        ),
    ),
    FakeOffice(
        id="office-nyc",
        name="NYC",
        address=Address(
            city="New York",
            country="USA",
            lines=["5th Ave 100", "Suite 400"],
            geo=Geo(lat=40.7128, lng=-74.0060),
        ),
    ),
    FakeOffice(
        id="office-london",
        name="London",
        address=Address(
            city="London",
            country="UK",
            lines=["Baker Street 221B"],
            geo=Geo(lat=51.5074, lng=-0.1278),
        ),
    ),
    FakeOffice(
        id="office-berlin",
        name="Berlin",
        address=Address(
            city="Berlin",
            country="Germany",
            lines=["Unter den Linden 5", "Wing B"],
            geo=Geo(lat=52.5200, lng=13.4050),
        ),
    ),
    FakeOffice(
        id="office-paris",
        name="Paris",
        address=Address(
            city="Paris",
            country="France",
            lines=["Rue de Rivoli 10"],
            geo=Geo(lat=48.8566, lng=2.3522),
        ),
    ),
    FakeOffice(
        id="office-tokyo",
        name="Tokyo",
        address=Address(
            city="Tokyo",
            country="Japan",
            lines=["Shibuya 2-1", "Tower 3"],
            geo=Geo(lat=35.6762, lng=139.6503),
        ),
    ),
    FakeOffice(
        id="office-sydney",
        name="Sydney",
        address=Address(
            city="Sydney",
            country="Australia",
            lines=["George Street 50"],
            geo=Geo(lat=-33.8688, lng=151.2093),
        ),
    ),
    FakeOffice(
        id="office-toronto",
        name="Toronto",
        address=Address(
            city="Toronto",
            country="Canada",
            lines=["King Street 200", "Unit 9"],
            geo=Geo(lat=43.6532, lng=-79.3832),
        ),
    ),
]

FAKE_TEAMS = [
    FakeTeam(
        id="team-platform",
        name="Platform",
        department=FAKE_DEPARTMENTS[0],
        lead=FakeLead(name="Alex Rivera", email="alex@example.com"),
    ),
    FakeTeam(
        id="team-integrations",
        name="Integrations",
        department=FAKE_DEPARTMENTS[0],
        lead=FakeLead(name="Sam Chen", email="sam@example.com"),
    ),
    FakeTeam(
        id="team-growth",
        name="Growth",
        department=FAKE_DEPARTMENTS[1],
        lead=FakeLead(name="Jordan Lee", email="jordan@example.com"),
    ),
    FakeTeam(
        id="team-brand",
        name="Brand",
        department=FAKE_DEPARTMENTS[1],
        lead=FakeLead(name="Taylor Kim", email="taylor@example.com"),
    ),
    FakeTeam(
        id="team-finance-ops",
        name="Finance Ops",
        department=FAKE_DEPARTMENTS[2],
        lead=FakeLead(name="Morgan Blake", email="morgan@example.com"),
    ),
    FakeTeam(
        id="team-payroll",
        name="Payroll",
        department=FAKE_DEPARTMENTS[2],
        lead=FakeLead(name="Casey Wong", email="casey@example.com"),
    ),
    FakeTeam(
        id="team-support-l1",
        name="Support L1",
        department=FAKE_DEPARTMENTS[3],
        lead=FakeLead(name="Riley Park", email="riley@example.com"),
    ),
    FakeTeam(
        id="team-support-l2",
        name="Support L2",
        department=FAKE_DEPARTMENTS[3],
        lead=FakeLead(name="Drew Patel", email="drew@example.com"),
    ),
    FakeTeam(
        id="team-research",
        name="Research",
        department=FAKE_DEPARTMENTS[4],
        lead=FakeLead(name="Quinn Adams", email="quinn@example.com"),
    ),
    FakeTeam(
        id="team-labs",
        name="Labs",
        department=FAKE_DEPARTMENTS[4],
        lead=FakeLead(name="Jamie Fox", email="jamie@example.com"),
    ),
    FakeTeam(
        id="team-security",
        name="Security",
        department=FAKE_DEPARTMENTS[0],
        lead=FakeLead(name="Avery Stone", email="avery@example.com"),
    ),
    FakeTeam(
        id="team-data",
        name="Data",
        department=FAKE_DEPARTMENTS[4],
        lead=FakeLead(name="Blake Hart", email="blake@example.com"),
    ),
]

DEFAULT_PROJECT_COUNT = 40
