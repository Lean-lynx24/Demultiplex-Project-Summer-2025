#!/bin/bash

# Script to run bcl2fastq and optionally compress the output.
# Designed to be the ENTRYPOINT for a Docker container.

# --- Default Settings ---
COMPRESS_OUTPUT=false

# --- Function to display usage information ---
usage() {
    echo "Usage: $0 -i <input_runfolder> -o <output_directory> [-c]"
    echo "  -i, --input      Path to the BCL runfolder directory."
    echo "  -o, --output     Path for the FASTQ output directory."
    echo "  -c, --compress   (Optional) Compress the output directory into a .7z archive upon completion."
    exit 1
}

# --- Parse Command-Line Arguments ---
INPUT_PATH=""
OUTPUT_DIR=""

while getopts ":i:o:ch" opt; do
  case ${opt} in
    i )
      INPUT_PATH=$OPTARG
      ;;
    o )
      OUTPUT_DIR=$OPTARG
      ;;
    c )
      COMPRESS_OUTPUT=true
      ;;
    h | \? ) # Handle -h or any unknown option
      usage
      ;;
  esac
done

# --- Validate Arguments ---
if [ -z "$INPUT_PATH" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Error: Both input (-i) and output (-o) directories are required arguments."
    usage
fi

if [ ! -d "$INPUT_PATH" ]; then
    echo "Error: Input runfolder '$INPUT_PATH' does not exist or is not a directory."
    exit 1
fi

# --- MODIFIED: Script now creates its own output directory ---
mkdir -p "$OUTPUT_DIR" || { echo "Error: Could not create output directory '$OUTPUT_DIR'."; exit 1; }
echo "Output will be saved to: '$OUTPUT_DIR'"


# --- Logic to automatically find the sample sheet ---
echo "Searching for sample sheet in '$INPUT_PATH'..."
sample_sheets_found=($(find "$INPUT_PATH" -maxdepth 1 -iname "Sample*.csv"))

if [ ${#sample_sheets_found[@]} -eq 0 ]; then
    echo "Error: No sample sheet found matching 'Sample*.csv' in '$INPUT_PATH'."
    exit 1
elif [ ${#sample_sheets_found[@]} -gt 1 ]; then
    echo "Error: Multiple sample sheets found. Please ensure only one exists."
    printf "Found: %s\n" "${sample_sheets_found[@]}"
    exit 1
fi
sample_sheet_path="${sample_sheets_found[0]}"
echo "Found sample sheet: $sample_sheet_path"


# --- Run bcl2fastq using the Conda installation ---
echo -e "\nStarting bcl2fastq..."
if bcl2fastq \
    --runfolder-dir "$INPUT_PATH" \
    --output-dir "$OUTPUT_DIR" \
    --sample-sheet "$sample_sheet_path" \
    --processing-threads "4" \
    --no-lane-splitting; then

    echo -e "\nbcl2fastq completed successfully. ✅"
else
    echo -e "\nError: bcl2fastq command failed. ❌"
    exit 1
fi

# --- Compression Step (Optional) ---
if [ "$COMPRESS_OUTPUT" = true ]; then
    echo -e "\nCompression requested. Archiving output directory..."
    output_parent_dir=$(dirname "$OUTPUT_DIR")
    output_base_name=$(basename "$OUTPUT_DIR")
    archive_path="${output_parent_dir}/${output_base_name}.7z"

    echo "Archive will be created at: $archive_path"

    if (cd "$output_parent_dir" && 7z a -t7z -m0=lzma2 -mx=9 -mfb=64 -md=32m -ms=on "$archive_path" "$output_base_name/"); then
        echo "Successfully created archive: $archive_path"
    else
        echo "Error: Compression failed."
        exit 1
    fi
fi

echo -e "\nScript finished."
