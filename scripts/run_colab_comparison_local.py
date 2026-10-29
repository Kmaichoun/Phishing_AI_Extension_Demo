"""Execute the shipped notebook in an isolated local kernel, preserving outputs.

This is local CPU validation, never a claim of a Google Colab execution.
Install the notebook libraries plus nbformat/nbclient/ipykernel in a task venv.
"""
from pathlib import Path
import argparse
import json
import os
import sys


def main():
    import nbformat
    from nbclient import NotebookClient

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['QUICK', 'DEMO'], default='DEMO')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / 'output' / 'colab-rf-dl-20261023'
    kernel_root = root / 'tmp' / 'colab-demo-jupyter'
    spec = kernel_root / 'kernels' / 'phish-radar-demo'
    spec.mkdir(parents=True, exist_ok=True)
    (spec / 'kernel.json').write_text(json.dumps({
        'argv': [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}'],
        'display_name': 'Phish Radar local CPU verification', 'language': 'python',
    }), encoding='utf-8')
    # The spec is task-local; no global kernel installation or user config change.
    os.environ['JUPYTER_PATH'] = str(kernel_root) + os.pathsep + os.environ.get('JUPYTER_PATH', '')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'
    os.environ['MPLBACKEND'] = 'module://matplotlib_inline.backend_inline'
    os.environ['MPLCONFIGDIR'] = str(root / 'tmp' / 'colab-demo-matplotlib-cache')
    notebook = nbformat.read(output / 'Phish_Radar_RF_vs_DL_Colab.ipynb', as_version=4)
    injected = nbformat.v4.new_code_cell(
        '# Local verification overrides: no hosted Colab session was used.\n'
        f'DATA_ZIP_OVERRIDE = {str(output / "data" / "demo_dataset.zip")!r}\n'
        f'RUN_DIR_OVERRIDE = {str(output / "local_cpu_results")!r}\n'
        f'MODE_OVERRIDE = {args.mode!r}\n'
        'USE_GPU_OVERRIDE = False\n'
        'RUN_CONTEXT_OVERRIDE = "Local CPU verification (not Google Colab)"\n'
        'SKIP_INSTALL = True\n'
        'SKIP_DOWNLOAD = True\n',
        metadata={'tags': ['local-verification-only']})
    notebook.cells.insert(1, injected)
    notebook.metadata.kernelspec = {'display_name': 'Phish Radar local CPU verification',
                                  'language': 'python', 'name': 'phish-radar-demo'}
    destination = output / f'Phish_Radar_RF_vs_DL_LOCAL_CPU_{args.mode}_executed.ipynb'
    client = NotebookClient(notebook, timeout=1800, kernel_name='phish-radar-demo',
        resources={'metadata': {'path': str(output)}})

    def progress(cell, cell_index, **kwargs):
        if cell.cell_type == 'code':
            print(f'Executing cell {cell_index}: {cell.metadata.get("tags", [])}', flush=True)

    client.on_cell_start = progress
    executed_ok = False
    try:
        client.execute()
        executed_ok = True
    finally:
        # Retain diagnostics if execution fails; filename explicitly says local CPU.
        notebook.metadata['local_verification'] = {
            'complete': executed_ok, 'mode': args.mode, 'google_colab_verified': False}
        nbformat.write(notebook, destination)
    nbformat.validate(notebook)
    print('Executed and validated:', destination, flush=True)
    print((output / 'local_cpu_results' / 'summary_TH.txt').read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
