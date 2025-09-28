FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy dependency list and install
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code into container
COPY . .

# Copy environment file so container knows your Mongo URI
COPY .env .env

# Run the rebalancer by default
CMD ["python", "-m", "agents.portfolio_rebalancer.executor"]
