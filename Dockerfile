# Dockerfile for the FASTQ Demultiplexing Worker
# This container will run the Python script to demultiplex FASTQ files.

# Use a Python base image
FROM python:3.9-slim-buster

# Set environment variables to prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install any necessary system dependencies if your Python script or its libraries need them.
# For the current demux_script.py, no specific system dependencies are strictly needed
# beyond what python:3.9-slim-buster provides for basic file operations.
# If you later add libraries that require system packages (e.g., HDF5, BLAS),
# you would add them here.

# Set the working directory inside the container
WORKDIR /app

# Copy the Python demultiplexing script into the container
COPY demultiplex.py /app/demultiplex.py

# Make the script executable (optional, but good practice for scripts)
RUN chmod +x /app/demultiplex.py

# Set the entrypoint to run your Python script
# This makes the container behave like an executable of your script.
ENTRYPOINT ["python", "/app/demultiplex.py"]

# Define default arguments. These can be overridden when running the container.
# For example, `docker run demux_tool --read1 R1.fastq.gz ...`
# We use 'dummy' values here as they are required by argparse, but will be
# replaced by the Flask app's command.
CMD ["--read1", "dummy_r1.fastq.gz", "--read2", "dummy_r2.fastq.gz", "--demux_summary", "dummy_summary.txt", "--out_dir", "dummy_output"]
