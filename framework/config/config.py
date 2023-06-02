from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    LOG_LEVEL: str = "INFO"

    PORT_CLIENT_ID: str
    PORT_CLIENT_SECRET: str
    PORT_BASE_URL: str

    # That's the default production brokers of Port
    KAFKA_CONSUMER_BROKERS: str = "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-2-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196,b-3-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"

    KAFKA_CONSUMER_SECURITY_PROTOCOL: str = "SASL_SSL"
    KAFKA_CONSUMER_AUTHENTICATION_MECHANISM: str = "SCRAM-SHA-512"
    KAFKA_SECURITY_ENABLED: bool = True


settings = Settings()
