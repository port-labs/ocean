from pydantic import BaseSettings, validator
import yaml
import argparse


def load_from_yaml(cls, key, value):
    if value != None:
        return value

    with open(integrations_config_path, 'r') as stream:
        integrations_config = yaml.safe_load(stream)
    return integrations_config['port'].get(key)


class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"

    PORT_CLIENT_ID: str = None
    PORT_CLIENT_SECRET: str = None
    PORT_BASE_URL: str = None

    KAFKA_CONSUMER_BROKERS: str = "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-2-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-3-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"
    KAFKA_CONSUMER_SECURITY_PROTOCOL: str = "SASL_SSL"
    KAFKA_CONSUMER_AUTHENTICATION_MECHANISM: str = "SCRAM-SHA-512"
    KAFKA_SECURITY_ENABLED: bool = True

    @validator('PORT_CLIENT_ID')
    def port_client_id_validator(cls, v):
        return load_from_yaml(cls, 'clientId', v)

    @validator('PORT_CLIENT_SECRET')
    def port_client_secret_validator(cls, v):
        return load_from_yaml(cls, 'clientSecret', v)

    @validator('PORT_BASE_URL')
    def port_base_url_validator(cls, v):
        return load_from_yaml(cls, 'baseUrl', v)


# Parse the command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--integrations-config', type=str)
args = parser.parse_args()

# Extract the value of the 'integrations-config' argument
integrations_config_path = args.integrations_config

settings = Settings()
