# Use slim Python base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Copy .env into container (important for Render/GCP)
COPY . .
CMD ["python", "-m", "agents.portfolio_rebalancer.executor"]

