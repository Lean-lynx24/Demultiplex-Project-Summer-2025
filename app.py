import os
import sys
import subprocess
import posixpath
import glob
from flask import Flask, render_template, request, Response, stream_with_context, redirect, url_for, send_from_directory, render_template_string, jsonify
from queue import Queue, Empty
from threading import Thread
import webbrowser
from threading import Timer
import time

# --- CONFIGURATION ---
app = Flask(__name__, root_path=sys.path[0])
DATA_ROOT = "data"
os.makedirs(DATA_ROOT, exist_ok=True)

BCL2FASTQ_IMAGE_NAME = "bcl2fastonlyscript:latest"
CONTAINER_MOUNT_POINT = "/data"

# Global state variables
process_running = False
current_process_params = {}

# --- NEW HELPER FUNCTION ---
# This function runs in a background thread to read lines from the subprocess
# without blocking the main application.
def enqueue_output(out, queue):
    for line in iter(out.readline, ''):
        queue.put(line)
    out.close()

# --- TEMPLATE ---
RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Process Results</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1a202c; }
        ::-webkit-scrollbar-thumb { background: #4a5568; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #718096; }
    </style>
</head>
<body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
    <div class="bg-white p-6 rounded-lg shadow-xl w-full max-w-4xl">
        <h1 class="text-3xl font-bold text-gray-800 mb-4 text-center">Process Output</h1>
        <div id="output" class="bg-gray-900 text-green-400 font-mono p-4 rounded-md overflow-y-auto h-96 whitespace-pre-wrap text-sm">
            Waiting for process output...
        </div>
        <div class="mt-6 flex justify-center">
            <a id="back-button" href="/" class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md transition duration-300 ease-in-out shadow-lg">
                Go Back
            </a>
        </div>
    </div>

    <script>
        const outputDiv = document.getElementById('output');
        let fullLogContent = "";
        const eventSource = new EventSource('/stream_output');

        eventSource.onmessage = function(event) {
            const data = event.data;

            if (data.startsWith('__RESULTS_URL__:')) {
                const url = data.substring('__RESULTS_URL__:'.length);
                fullLogContent += '\\n✔ PROCESS COMPLETE. Redirecting to results page...';
                outputDiv.textContent = fullLogContent;
                eventSource.close();
                window.location.href = url;
            } else if (data.includes('__PROCESS_FAILED__')) {
                fullLogContent += '\\n❌ PROCESS FAILED. Check logs for details. You can now go back.\\n';
                eventSource.close();
            } else {
                 fullLogContent += data + '\\n';
            }
            outputDiv.textContent = fullLogContent;
            outputDiv.scrollTop = outputDiv.scrollHeight;
        };

        eventSource.onerror = function(err) {
            console.error('EventSource failed:', err);
            outputDiv.textContent += '\\n--- Error: Process Stream Disconnected ---';
            eventSource.close();
        };
    </script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def index():
    """Renders the main page, listing available run folders."""
    try:
        run_folders = [f for f in os.listdir(DATA_ROOT) if os.path.isdir(os.path.join(DATA_ROOT, f))]
    except FileNotFoundError:
        run_folders = []
    return render_template('index.html', run_folders=run_folders)

@app.route('/start_process', methods=['POST'])
def start_process():
    """Starts the background process, ensuring only one runs at a time."""
    global process_running, current_process_params
    if process_running:
        return jsonify({"success": False, "message": "A process is already running."}), 409

    process_running = True
    current_process_params = request.form.to_dict()

    if not current_process_params.get('runfolder_name'):
         return jsonify({"success": False, "message": "No run folder selected."}), 400

    return jsonify({"success": True, "results_url": url_for('processing_page')})

@app.route('/processing')
def processing_page():
    """Displays the page that streams the live log output."""
    return render_template_string(RESULTS_TEMPLATE)

@app.route('/results/<path:run_folder_name>')
def results_page(run_folder_name):
    """Serves the final bcl2fastq HTML report."""
    report_directory = os.path.join(DATA_ROOT, run_folder_name, 'bcl2fastq_output')
    report_file = os.path.join(report_directory, 'index.html')

    if not os.path.exists(report_file):
        return "Report not found. The process may still be running or it failed to generate the report.", 404

    return send_from_directory(report_directory, 'index.html')


@app.route('/stream_output')
def stream_output():
    """
    Handles the core logic: runs the docker container and streams the output with a heartbeat
    to prevent browser timeouts.
    """
    def generate():
        global process_running, current_process_params
        if not process_running:
            yield "data: No process is currently running.\n\n"
            return

        runfolder_name = current_process_params.get('runfolder_name')
        compress = current_process_params.get('compress') == 'on'

        if not runfolder_name:
            yield "data: ERROR: Run folder name was not found.\n\n"
            yield "data: __PROCESS_FAILED__\n\n"
            process_running = False
            return

        try:
            yield "data: Process starting, please wait for the container to initialize...\n\n"

            input_path_in_container = posixpath.join(CONTAINER_MOUNT_POINT, runfolder_name)
            output_path_in_container = posixpath.join(input_path_in_container, 'bcl2fastq_output')

            # Using aggressive limits to prevent system freeze
            cmd = [
                "docker", "run", "--rm",
                "--user", "0:0",
                "--memory", "4g",
                "-v", f"{os.path.abspath(DATA_ROOT)}:{CONTAINER_MOUNT_POINT}",
                BCL2FASTQ_IMAGE_NAME,
                "-i", input_path_in_container,
                "-o", output_path_in_container
            ]
            if compress:
                cmd.append("-c")

            command_string = ' '.join(cmd)
            yield f"data: 🏃 Running command: {command_string}\n\n"

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)

            # Start a background thread to read the process output
            q = Queue()
            t = Thread(target=enqueue_output, args=(process.stdout, q))
            t.daemon = True
            t.start()

            # Main loop: send output from queue or send a heartbeat
            while t.is_alive() or not q.empty():
                try:
                    line = q.get(timeout=15)  # Wait up to 15 seconds for a line
                    yield f"data: {line.strip()}\n\n"
                except Empty:
                    # No output for 15s, send a heartbeat to keep connection alive
                    yield ": heartbeat\n\n"

            t.join() # Wait for the thread to finish
            return_code = process.wait()

            if return_code == 0:
                results_url = url_for('results_page', run_folder_name=runfolder_name)
                yield f"data: __RESULTS_URL__:{results_url}\n\n"
            else:
                yield f"data: --- Worker process failed with exit code: {return_code} ---\n\n"
                yield "data: __PROCESS_FAILED__\n\n"

        except Exception as e:
            error_message = f"An application error occurred: {str(e)}"
            yield f"data: {error_message}\n\n"
            yield "data: __PROCESS_FAILED__\n\n"
        finally:
            process_running = False
            current_process_params = {}

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    print("Starting Flask server...")
    print(f"Data is being read from and written to the local '{DATA_ROOT}' directory.")
    print("Please open http://127.0.0.1:5000/ in your browser.")
    app.run(debug=True, host='0.0.0.0', port=5000)