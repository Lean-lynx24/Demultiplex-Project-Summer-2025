#!/bin/bash
SEARCH_DIR="${1:-.}"
CONTAINER_BASE_DIR="/data/fastq_mounts"

usage() {
    echo "Usage: $0 [search_directory]"
    echo ""
    echo "This script finds .fastq or .fastq.gz files within the specified directory"
    echo "and generates Docker volume mount arguments (-v host_path:container_path)."
    echo ""
    echo "Arguments:"
    echo "  search_directory  The root directory to start searching for FASTQ files."
    echo "                    Defaults to the current directory ('.') if not provided."
    echo ""
    echo "Example:"
    echo "  $0 /path/to/your/raw_data"
    echo "  $0 ."
    exit 1
}

if [ ! -d "$SEARCH_DIR" ]; then
    ech "Error: Search directory '$SEARCH_DIR' not found"
    usage
fi

echo "Searching for FASTQ files in: $SEARCH_DIR" echo ""
echo ""
#the next part of code will find all uniqe directory that conatian fastq or fastq.gz

FASTQ_DIRS=$(find "$SEARCH_DIR" -type f -regex ".*\.fastq\|.*\.fastq\.gz" -print0 | \
             xargs -0 -n1 dirname | \
             sort -u)

DOCKER_VOLUMES=""
MOUNT_COUNTER=0

if [ -z "$FASTQ_DIRS" ]; then
    echo "No FASTQ files found in '$SEARCH_DIR' or its subdirectories."
else
    echo "Found FASTQ directories:"
    echo "$FASTQ_DIRS"
    echo ""
    echo "--- Generating Docker Volume Mounts ---"
    echo ""

    while IFS= read -r dir; do
        # Generate a unique mount point inside the container based on the counter
        # This helps avoid conflicts if host paths have similar names but are distinct.
        CONTAINER_PATH="${CONTAINER_BASE_DIR}/dir_${MOUNT_COUNTER}"
        
        
        DOCKER_VOLUMES+=" -v \"$dir\":\"$CONTAINER_PATH\""
        
        echo "  Host Path:   \"$dir\""
        echo "  Container Path: \"$CONTAINER_PATH\""
        echo ""
        
        MOUNT_COUNTER=$((MOUNT_COUNTER + 1))
    done <<< "$FASTQ_DIRS"
fi

echo "--- Docker Command for BCL2FASTQ ---"
echo ""

# Placeholder for your Docker image and command
# Replace 'your_docker_image:tag' with your actual image.
# Replace 'your_command_inside_docker' with the command you want to run.
# You will need to adjust the command to access files from the CONTAINER_BASE_DIR
# and its subdirectories (e.g., /data/fastq_mounts/dir_0, /data/fastq_mounts/dir_1, etc.)
# based on how your analysis tool expects input paths.

if [ -z "$DOCKER_VOLUMES" ]; then
    echo "No Docker volume mounts generated as no FASTQ files were found."
    echo "Example without mounts (replace image and command):"
    echo "docker run flask-project12:tag BCL2FASTQ1" # Using your hardcoded values here
else
    echo "To run your Docker container with these files mounted, use a command like this:"
    echo ""
    echo "docker run \\"
    echo "  $DOCKER_VOLUMES \\"
    echo "  flask-project12:tag \\" # Using your hardcoded values here
    echo "  BCL2FASTQ1" # Using your hardcoded values here
    echo ""
fi 
echo ""
echo "Script finished."
