# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the cache to reduce image size.
# --system: Install packages into the system Python, useful for some base images.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY app.py .

# Make port 8501 available to the world outside this container
# This is the default port Streamlit runs on.
# Cloud Run will automatically use the $PORT environment variable.
EXPOSE 8501

# Define environment variable for the port (Cloud Run will set this)
ENV PORT 8501

# Run app.py when the container launches
# Use exec to make Streamlit the main process (PID 1)
# --server.address=0.0.0.0 to allow connections from outside the container
# --server.port=$PORT to respect the port set by Cloud Run
# --server.enableCORS=false and --server.enableXsrfProtection=false are often needed when behind a proxy like IAP or a load balancer.
# Adjust --server.headless=true if you encounter issues with Streamlit trying to open a browser.
CMD exec streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false