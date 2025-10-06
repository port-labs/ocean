"""Debug script for Okta integration development"""

from port_ocean.context.ocean import ocean
from integration import OktaIntegration


if __name__ == "__main__":
    ocean.run(OktaIntegration, "/integrations/okta")