FROM python:3.9-slim

WORKDIR /app

# Install poetry
RUN pip install poetry==1.4.2

# Copy project files
COPY pyproject.toml poetry.lock* ./
COPY . .

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the integration
CMD ["python", "-m", "port_ocean"]
