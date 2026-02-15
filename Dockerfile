FROM python:3.9-slim

WORKDIR /app

# Install system dependencies if any (none for now)

# Install python dependencies
# In a real repo this would be requirements.txt
RUN pip install --no-cache-dir cryptography fastapi uvicorn pydantic

# Copy source code
COPY . /app

# Create keys directory volume mount point
VOLUME /app/.keys

# Expose port
EXPOSE 8000

# Run the server
# We use python -m struct to ensure relative imports work or just point to the file
# Ideally we should install the package, but for v0 this works.
CMD ["uvicorn", "src.attestation.server:app", "--host", "0.0.0.0", "--port", "8000"]
